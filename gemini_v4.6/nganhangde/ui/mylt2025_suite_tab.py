from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from ..core.config_manager import ConfigManager
from ..exporters.phieu_tltn_2025 import append_phieu_to_pdf, inject_phieu_into_tex
from ..exporters.tikz2pic import Tikz2PicConfig, export_tikz_to_png
from ..exporters.blogger_form_exporter import GoogleFormConfig, export_blogger_form_html


class _TaskWorker(QThread):
    ok = Signal(str)
    err = Signal(str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.ok.emit(str(self.fn()))
        except Exception as exc:
            self.err.emit(str(exc))


class MyLT2025SuiteTab(QWidget):
    """Tab tích hợp Phiếu TLTN 2025, Tikz2Pic, Blogger Form và Cấu hình config.ini."""

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.cfg = ConfigManager()
        self._worker: _TaskWorker | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # 1. Phiếu TLTN 2025
        g_phieu = QGroupBox("1. Ghép mẫu Phiếu TLTN THPT QG 2025 (dongke)")
        r_phieu = QHBoxLayout(g_phieu)
        self.cbo_phieu = QComboBox()
        self.cbo_phieu.addItem("Mẫu 1 mặt (phieu_2025_1mat.pdf)", "1mat")
        self.cbo_phieu.addItem("Mẫu đầy đủ 2 trang (phieu_2025_full.pdf)", "full")
        b_tex = QPushButton("Nhúng Phiếu vào .tex")
        b_tex.clicked.connect(self._on_inject_tex)
        b_pdf = QPushButton("Ghép Phiếu vào cuối .pdf")
        b_pdf.clicked.connect(self._on_append_pdf)
        r_phieu.addWidget(self.cbo_phieu, 1)
        r_phieu.addWidget(b_tex)
        r_phieu.addWidget(b_pdf)
        root.addWidget(g_phieu)

        # 2. Tikz2Pic & Blogger Form
        g_tools = QGroupBox("2. Tikz2Pic (PNG 150 DPI) & Xuất Blogger Google Form")
        f_tools = QFormLayout(g_tools)
        self.ed_blogger_title = QLineEdit("Đề kiểm tra Toán — GDPT 2018")
        self.spn_minutes = QSpinBox()
        self.spn_minutes.setRange(5, 180)
        self.spn_minutes.setValue(45)
        r_btn = QHBoxLayout()
        b_t2p = QPushButton("Chạy Tikz2Pic từ tệp .tex")
        b_t2p.clicked.connect(self._on_tikz2pic)
        b_blog = QPushButton("Xuất HTML Blogger + Google Form")
        b_blog.clicked.connect(self._on_blogger)
        r_btn.addWidget(b_t2p)
        r_btn.addWidget(b_blog)
        r_btn.addStretch()
        f_tools.addRow("Tiêu đề Blogger:", self.ed_blogger_title)
        f_tools.addRow("Thời gian (phút):", self.spn_minutes)
        f_tools.addRow("", r_btn)
        root.addWidget(g_tools)

        # 3. Cấu hình config.ini
        g_cfg = QGroupBox("3. Cấu hình config.ini (API, Tikz2Pic, Google Form)")
        f_cfg = QFormLayout(g_cfg)
        self.ed_gemini = QLineEdit(self.cfg.get("API", "gemini_api_key"))
        self.ed_gemini.setEchoMode(QLineEdit.Password)
        self.ed_dpi = QLineEdit(self.cfg.get("Tikz2Pic", "dpi", "150"))
        self.ed_qcol = QLineEdit(self.cfg.get("Tikz2Pic", "question_color", "#006666"))
        self.ed_scol = QLineEdit(self.cfg.get("Tikz2Pic", "solution_color", "#80FF80"))
        self.ed_furl = QLineEdit(self.cfg.get("BloggerForm", "form_action_url"))
        b_save = QPushButton("Lưu config.ini")
        b_save.clicked.connect(self._on_save_cfg)
        f_cfg.addRow("Gemini API Key:", self.ed_gemini)
        f_cfg.addRow("Tikz2Pic DPI:", self.ed_dpi)
        f_cfg.addRow("Màu hình đề:", self.ed_qcol)
        f_cfg.addRow("Màu hình lời giải:", self.ed_scol)
        f_cfg.addRow("Google Form Action URL:", self.ed_furl)
        f_cfg.addRow("", b_save)
        root.addWidget(g_cfg)

        self.lbl_info = QLabel(f"Tệp cấu hình: {self.cfg.ini_path}")
        root.addWidget(self.lbl_info)
        root.addStretch()

    def _run_bg(self, fn):
        self.lbl_info.setText("Đang xử lý...")
        self._worker = _TaskWorker(fn)
        self._worker.ok.connect(
            lambda m: (self.lbl_info.setText("Hoàn tất."), QMessageBox.information(self, "Thành công", m))
        )
        self._worker.err.connect(
            lambda e: (self.lbl_info.setText("Lỗi."), QMessageBox.critical(self, "Lỗi", e))
        )
        self._worker.start()

    def _on_inject_tex(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn tệp đề .tex", "", "LaTeX (*.tex)")
        if not path:
            return
        src = Path(path)
        tpl_key = self.cbo_phieu.currentData()
        out_tex = src.with_name(f"{src.stem}_kem_phieu2025.tex")
        updated = inject_phieu_into_tex(src.read_text(encoding="utf-8"), tpl_key, copy_to_dir=src.parent)
        out_tex.write_text(updated, encoding="utf-8")
        QMessageBox.information(self, "Phiếu TLTN 2025", f"Đã tạo tệp .tex kèm phiếu:\n{out_tex}")

    def _on_append_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn tệp đề .pdf", "", "PDF (*.pdf)")
        if not path:
            return
        tpl_key = self.cbo_phieu.currentData()
        out = append_phieu_to_pdf(Path(path), template_key=tpl_key)
        QMessageBox.information(self, "Phiếu TLTN 2025", f"Đã ghép phiếu 2025 vào cuối tệp:\n{out}")

    def _on_tikz2pic(self):
        path, _ = QFileDialog.getOpenFileName(self, "Chọn tệp .tex chứa TikZ", "", "LaTeX (*.tex)")
        if not path:
            return
        src = Path(path)
        out_dir = src.parent / f"{src.stem}_images"
        cfg = Tikz2PicConfig(
            dpi=int(self.ed_dpi.text().strip() or "150"),
            question_color=self.ed_qcol.text().strip() or "#006666",
            solution_color=self.ed_scol.text().strip() or "#80FF80",
        )

        def task():
            items, _ = export_tikz_to_png(src.read_text(encoding="utf-8"), out_dir, cfg)
            ok = sum(1 for x in items if x.ok)
            return f"Đã xuất {ok}/{len(items)} hình PNG vào:\n{out_dir}"

        self._run_bg(task)

    def _on_blogger(self):
        out_html, _ = QFileDialog.getSaveFileName(self, "Lưu tệp Blogger HTML", "de_thi_blogger.html", "HTML (*.html)")
        if not out_html:
            return
        questions: list[dict] = []
        if self.db is not None and hasattr(self.db, "search"):
            try:
                rows = self.db.search(limit=50)
                for q in rows:
                    opts = getattr(q, "choices", None) or []
                    if len(opts) >= 2:
                        questions.append({
                            "stem": getattr(q, "stem", ""),
                            "options": [getattr(c, "text", str(c)) for c in opts[:4]],
                            "correct_index": next((i for i, c in enumerate(opts[:4]) if getattr(c, "is_true", False)), 0),
                        })
            except Exception:
                pass
        fcfg = GoogleFormConfig(
            form_action_url=self.ed_furl.text().strip(),
            entry_exam_name=self.cfg.get("BloggerForm", "entry_exam_name"),
            entry_sbd=self.cfg.get("BloggerForm", "entry_sbd"),
            entry_student_name=self.cfg.get("BloggerForm", "entry_student_name"),
            entry_class=self.cfg.get("BloggerForm", "entry_class"),
            entry_score=self.cfg.get("BloggerForm", "entry_score"),
            entry_answers=self.cfg.get("BloggerForm", "entry_answers"),
            entry_duration=self.cfg.get("BloggerForm", "entry_duration"),
        )
        export_blogger_form_html(
            exam_title=self.ed_blogger_title.text().strip(),
            questions=questions,
            output_html=Path(out_html),
            duration_minutes=self.spn_minutes.value(),
            form_cfg=fcfg,
        )
        QMessageBox.information(self, "Blogger Form", f"Đã xuất tệp HTML ({len(questions)} câu):\n{out_html}")

    def _on_save_cfg(self):
        self.cfg.set("API", "gemini_api_key", self.ed_gemini.text().strip())
        self.cfg.set("Tikz2Pic", "dpi", self.ed_dpi.text().strip() or "150")
        self.cfg.set("Tikz2Pic", "question_color", self.ed_qcol.text().strip() or "#006666")
        self.cfg.set("Tikz2Pic", "solution_color", self.ed_scol.text().strip() or "#80FF80")
        self.cfg.set("BloggerForm", "form_action_url", self.ed_furl.text().strip())
        self.cfg.save()
        QMessageBox.information(self, "Cấu hình", f"Đã lưu cấu hình vào:\n{self.cfg.ini_path}")
