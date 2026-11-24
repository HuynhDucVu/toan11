from dataclasses import dataclass
from pathlib import Path


@dataclass
class RenderedPdfPage:
    samples: bytes
    width: int
    height: int
    stride: int
    page_count: int


def render_pdf_page_buffer(pdf_path: str, page_index: int = 0, zoom: float = 1.6) -> RenderedPdfPage:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Thiếu PyMuPDF. Chạy: pip install pymupdf") from exc
    doc = fitz.open(pdf_path)
    try:
        total = len(doc)
        pix = doc[max(0, min(page_index, total - 1))].get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        return RenderedPdfPage(bytes(pix.samples), pix.width, pix.height, pix.stride, total)
    finally:
        doc.close()


def make_qimage_from_pdf_page(pdf_path: str, page_index: int = 0, zoom: float = 1.6):
    from PySide6.QtGui import QImage
    buf = render_pdf_page_buffer(pdf_path, page_index=page_index, zoom=zoom)
    img = QImage(buf.samples, buf.width, buf.height, buf.stride, QImage.Format_RGB888)
    return img.copy(), buf.page_count


try:
    from PySide6.QtCore import Qt, QThread, Signal
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )
    from ..exporters.pdfbuild import compile_tikz_snippet_to_pdf, open_pdf_file

    class TikzPdfCompileWorker(QThread):
        done = Signal(bool, str, str)  # (ok, pdf_path, err_msg)

        def __init__(self, tikz_code: str, compiler: str = "pdflatex"):
            super().__init__()
            self.tikz_code = tikz_code
            self.compiler = compiler

        def run(self):
            try:
                res = compile_tikz_snippet_to_pdf(self.tikz_code, compiler=self.compiler)
                if res.success and res.pdf_path:
                    self.done.emit(True, res.pdf_path, "")
                else:
                    diag = "\n".join(f"Dòng {d.line_no}: {d.summary} ({d.suggestion_vi})" for d in res.diagnostics[:4])
                    detail = diag or (res.stderr[-600:] if res.stderr else "") or f"Compiler: {res.compiler}"
                    self.done.emit(False, "", detail)
            except Exception as exc:
                self.done.emit(False, "", str(exc))

    class InlinePdfPreviewPanel(QWidget):
        """Khung Xem trước PDF hiển thị trực tiếp bên phải (render bằng PyMuPDF)."""

        def __init__(self, auto_checked: bool = True, parent=None):
            super().__init__(parent)
            self.current_pdf: str | None = None
            self.current_page: int = 0
            self.total_pages: int = 0
            self.zoom: float = 1.8
            self._last_qimage = None
            self._worker: TikzPdfCompileWorker | None = None
            self._build_ui(auto_checked)

        def _build_ui(self, auto_checked: bool):
            lay = QVBoxLayout(self)
            lay.setContentsMargins(0, 0, 0, 0)

            top = QHBoxLayout()
            self.chk_preview = QCheckBox("Xem trước")
            self.chk_preview.setChecked(auto_checked)
            self.lbl_page = QLabel("Chưa có PDF")
            b_prev = QPushButton("◀"); b_prev.setFixedWidth(28); b_prev.clicked.connect(lambda: self._step_page(-1))
            b_next = QPushButton("▶"); b_next.setFixedWidth(28); b_next.clicked.connect(lambda: self._step_page(1))
            b_zout = QPushButton("-"); b_zout.setFixedWidth(26); b_zout.clicked.connect(lambda: self._set_zoom(self.zoom - 0.3))
            b_zin = QPushButton("+"); b_zin.setFixedWidth(26); b_zin.clicked.connect(lambda: self._set_zoom(self.zoom + 0.3))
            b_ext = QPushButton("Mở ngoài"); b_ext.clicked.connect(self._open_external)

            top.addWidget(self.chk_preview)
            top.addStretch()
            top.addWidget(self.lbl_page)
            top.addWidget(b_prev); top.addWidget(b_next)
            top.addWidget(b_zout); top.addWidget(b_zin)
            top.addWidget(b_ext)
            lay.addLayout(top)

            self.scroll = QScrollArea()
            self.scroll.setWidgetResizable(True)
            self.lbl_img = QLabel("Bấm 'Xem PDF' hoặc chọn mẫu (khi tick 'Xem trước') để biên dịch và hiển thị tại đây.")
            self.lbl_img.setAlignment(Qt.AlignCenter)
            self.lbl_img.setWordWrap(True)
            self.lbl_img.setStyleSheet("background: #FFFFFF; border: 1px solid #CBD5E1; padding: 8px;")
            self.scroll.setWidget(self.lbl_img)
            lay.addWidget(self.scroll, 1)

        def is_auto_preview(self) -> bool:
            return self.chk_preview.isChecked()

        def set_status(self, text: str):
            self.lbl_img.setPixmap(QPixmap())
            self.lbl_img.setText(text)
            self.lbl_page.setText(text[:30])

        def compile_and_show_tikz(self, tikz_code: str, compiler: str = "pdflatex"):
            code = tikz_code.strip()
            if not code:
                self.set_status("Chưa có mã TikZ để biên dịch.")
                return
            self.set_status("Đang biên dịch PDF...")
            self._worker = TikzPdfCompileWorker(code, compiler=compiler)
            self._worker.done.connect(self._on_compile_done)
            self._worker.start()

        def _on_compile_done(self, ok: bool, pdf_path: str, err_msg: str):
            if ok and pdf_path and Path(pdf_path).exists():
                self.load_pdf(pdf_path)
            else:
                self.set_status(f"Lỗi biên dịch PDF:\n{err_msg}")

        def load_pdf(self, pdf_path: str):
            self.current_pdf = pdf_path
            self.current_page = 0
            self._render_current()

        def _render_current(self):
            if not self.current_pdf or not Path(self.current_pdf).exists():
                return
            try:
                qimg, total = make_qimage_from_pdf_page(self.current_pdf, page_index=self.current_page, zoom=self.zoom)
                self._last_qimage = qimg
                self.total_pages = total
                self.lbl_img.setText("")
                self.lbl_img.setPixmap(QPixmap.fromImage(qimg))
                self.lbl_page.setText(f"Trang {self.current_page + 1}/{total}")
            except Exception as exc:
                self.set_status(f"Không thể hiển thị PDF:\n{exc}")

        def _step_page(self, delta: int):
            if self.total_pages <= 0:
                return
            nxt = max(0, min(self.current_page + delta, self.total_pages - 1))
            if nxt != self.current_page:
                self.current_page = nxt
                self._render_current()

        def _set_zoom(self, new_zoom: float):
            self.zoom = max(0.6, min(new_zoom, 4.0))
            self._render_current()

        def _open_external(self):
            if self.current_pdf and Path(self.current_pdf).exists():
                open_pdf_file(self.current_pdf)

        def copy_image_to_clipboard(self) -> bool:
            if self._last_qimage is not None:
                QApplication.clipboard().setImage(self._last_qimage)
                return True
            return False

        def clear(self):
            self.current_pdf = None
            self._last_qimage = None
            self.total_pages = 0
            self.lbl_page.setText("Chưa có PDF")
            self.lbl_img.setPixmap(QPixmap())
            self.lbl_img.setText("Đã xoá hình xem trước.")

except Exception:
    pass
