"""Biên dịch PDF: chuẩn bị file, hộp kết quả, hộp cài đặt."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

if TYPE_CHECKING:
    from ..main_window import MainWindow


def prepare_tex_for_pdf(paths, template_path=None) -> list[str]:
    """File chỉ có câu hỏi (không có \\documentclass) ⇒ bọc vào mẫu đề (bản lời giải) thành file _pdf.tex."""
    from ...exporter import fill, load_template
    out = []
    for p in paths:
        with open(p, encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if "\\documentclass" in text:
            out.append(p)
            continue
        q = os.path.splitext(p)[0] + "_pdf.tex"
        with open(q, "w", encoding="utf-8") as f:
            f.write(fill(load_template(template_path), MODE="loigiai", NOI_DUNG=text,
                         TEN_DE=os.path.basename(os.path.splitext(p)[0]), MA_DE="—"))
        out.append(q)
    return out


class PdfResultDialog(QDialog):
    def __init__(self, parent, results):
        super().__init__(parent)
        self.setWindowTitle("Kết quả biên dịch PDF")
        self.resize(820, 420)
        self.results = results
        lay = QVBoxLayout(self)
        ok = sum(r.ok for r in results)
        lay.addWidget(QLabel(f"<b>{ok}/{len(results)} file biên dịch thành công.</b> Nhấp đúp một dòng để mở PDF "
                             "(file lỗi mở trong TeXstudio đúng dòng lỗi, nếu máy có TeXstudio)."
                             + ("<br><i>Có file dùng gói ex_test rút gọn đi kèm vì máy chưa cài ex_test – cài ex_test "
                                "thật (hoặc chỉ thư mục chứa ex_test.sty trong Cài đặt) để có bản in chuẩn.</i>"
                                if any(r.used_lite for r in results) else "")))
        t = QTableWidget(len(results), 3)
        t.setHorizontalHeaderLabels(["File", "Kết quả", "Lỗi (nếu có)"])
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.verticalHeader().setVisible(False)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r_, res in enumerate(results):
            vals = (os.path.basename(res.tex), "✔ " + f"{res.seconds:.1f}s" if res.ok else "✘ lỗi",
                    " | ".join(res.errors[:4]))
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setToolTip("\n".join(res.errors) or res.pdf or "")
                if c == 1:
                    it.setForeground(QColor("#0b7a0b" if res.ok else "#c00000"))
                t.setItem(r_, c, it)
        t.doubleClicked.connect(self.open_row)
        lay.addWidget(t)
        self.t = t
        self.ai_out = QLabel()
        self.ai_out.setWordWrap(True)
        self.ai_out.setTextInteractionFlags(self.ai_out.textInteractionFlags() | Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.ai_out)
        from PySide6.QtWidgets import QHBoxLayout
        row = QHBoxLayout()
        if any(not r.ok for r in results):
            a = QPushButton("🤖 Hỏi AI cách sửa lỗi (dòng đang chọn)")
            a.clicked.connect(self.ask_ai)
            row.addWidget(a)
        row.addStretch()
        b = QPushButton("Đóng")
        b.clicked.connect(self.accept)
        row.addWidget(b)
        lay.addLayout(row)

    def ask_ai(self):
        from ... import aitasks
        from ..workers import TaskWorker
        from .ai_settings import ensure_client
        bad = [r for r in self.results if not r.ok]
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        r = self.results[rows[0]] if rows and not self.results[rows[0]].ok else bad[0]
        win = self.parent()
        while win is not None and not hasattr(win, "settings"):
            win = win.parent()
        client = ensure_client(win) if win is not None else None
        if client is None:
            return
        self.ai_out.setText("<i>Đang hỏi AI…</i>")
        w = TaskWorker(aitasks.diagnose_log, client, r.errors or ["lỗi không rõ"], r.tex)
        w.finished.connect(lambda: self._show_ai(w, r))
        self._w = w
        w.start()

    def _show_ai(self, w, r):
        import html
        if w.error:
            self.ai_out.setText(f"<span style='color:#c00000'>{html.escape(w.error)}</span>")
            return
        d = w.result or {}
        fix = (f"<br><b>Sửa dòng {d['dong']} thành:</b> <code>{html.escape(d.get('sua_thanh', ''))}</code>"
               if d.get("dong") and d.get("sua_thanh") else "")
        self.ai_out.setText(f"<b>{html.escape(os.path.basename(r.tex))}</b> – <b>Nguyên nhân:</b> "
                            f"{html.escape(d.get('nguyen_nhan', ''))}<br><b>Cách sửa:</b> "
                            f"{html.escape(d.get('cach_sua', ''))}{fix}")

    def open_row(self, idx):
        from ...editor import first_error_line, open_in_texstudio
        r = self.results[idx.row()]
        if r.ok and r.pdf:
            QDesktopServices.openUrl(QUrl.fromLocalFile(r.pdf))
            return
        win = self.parent()
        while win is not None and not hasattr(win, "settings"):
            win = win.parent()
        custom = win.settings.value("pdf/texstudio", "") if win is not None else ""
        if not open_in_texstudio(r.tex, first_error_line(r.errors), custom):
            QDesktopServices.openUrl(QUrl.fromLocalFile(r.tex))


class PdfSettingsDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win, st = win, win.settings
        self.setWindowTitle("Cài đặt biên dịch PDF")
        self.resize(640, 380)
        f = QFormLayout(self)
        self.cb_eng = QComboBox()
        for t, d in (("Tự động (pdflatex → xelatex → lualatex)", "auto"), ("pdflatex", "pdflatex"),
                     ("xelatex", "xelatex"), ("lualatex", "lualatex")):
            self.cb_eng.addItem(t, d)
        self.cb_eng.setCurrentIndex(max(0, self.cb_eng.findData(st.value("pdf/engine", "auto"))))
        self.e_custom = self._path(st.value("pdf/custom", ""), False, "Đường dẫn pdflatex.exe/xelatex.exe (để trống = tự tìm)")
        self.e_extest = self._path(st.value("pdf/extest", ""), True, "Thư mục chứa ex_test.sty (để trống = dùng gói đã cài)")
        self.sp_runs = QSpinBox()
        self.sp_runs.setRange(1, 3)
        self.sp_runs.setValue(int(st.value("pdf/runs", 2)))
        self.c_clean = QCheckBox("Xoá file phụ (.aux, .log…) sau khi biên dịch thành công")
        self.c_clean.setChecked(str(st.value("pdf/clean", True)).lower() == "true")
        self.e_texstudio = self._path(st.value("pdf/texstudio", ""), False,
                                      "Đường dẫn texstudio.exe (để trống = tự tìm)")
        self.c_open = QCheckBox("Tự mở PDF khi biên dịch 1 file")
        self.c_open.setChecked(str(st.value("pdf/open", True)).lower() == "true")
        f.addRow("Trình biên dịch", self.cb_eng)
        f.addRow("Chỉ định file chạy", self.e_custom[1])
        f.addRow("Gói ex_test", self.e_extest[1])
        f.addRow("Số lượt chạy", self.sp_runs)
        f.addRow("", self.c_clean)
        f.addRow("", self.c_open)
        f.addRow("TeXstudio", self.e_texstudio[1])
        self.info = QLabel()
        self.info.setWordWrap(True)
        f.addRow(self.info)
        row = QHBoxLayout()
        b = QPushButton("Kiểm tra")
        b.clicked.connect(self.check)
        ok = QPushButton("Lưu")
        ok.setObjectName("primary")
        ok.clicked.connect(self.save)
        row.addWidget(b)
        row.addStretch()
        row.addWidget(ok)
        f.addRow(row)
        self.check()

    def _path(self, value, folder, ph):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        e = QLineEdit(value)
        e.setPlaceholderText(ph)
        b = QPushButton("…")
        b.setFixedWidth(40)

        def pick():
            p = QFileDialog.getExistingDirectory(self, "Chọn thư mục", e.text()) if folder else \
                QFileDialog.getOpenFileName(self, "Chọn file chạy LaTeX", e.text())[0]
            if p:
                e.setText(p)
        b.clicked.connect(pick)
        h.addWidget(e)
        h.addWidget(b)
        return e, w

    def check(self):
        from ...pdfbuild import EngineMissing, find_engine, has_package
        try:
            eng = find_engine(self.cb_eng.currentData(), self.e_custom[0].text())
        except EngineMissing as e:
            self.info.setText(f"<span style='color:#c00000'>{e}</span><br>Tải MiKTeX: <b>miktex.org/download</b> "
                              "(cài xong khởi động lại phần mềm).")
            return
        ext = has_package(eng, "ex_test.sty", [self.e_extest[0].text()])
        vn = has_package(eng, "vietnam.sty")
        from ...editor import find_texstudio
        ts = find_texstudio(self.e_texstudio[0].text())
        self.info.setText(f"<span style='color:#0b7a0b'>✔ Tìm thấy: {eng}</span><br>"
                          + ("✔ Có gói ex_test" if ext else "⚠ Chưa thấy gói ex_test – sẽ dùng gói rút gọn đi kèm "
                             "(đủ để xem/in thử; nên cài ex_test thật để in chính thức)") + "<br>"
                          + ("✔ Có gói tiếng Việt vntex (pdflatex)" if vn else
                             "⚠ Chưa thấy gói vietnam (vntex) – với pdflatex cần cài; xelatex thì dùng phông Times New Roman")
                          + "<br>" + (f"✔ TeXstudio: {ts}" if ts else "⚠ Chưa thấy TeXstudio (texstudio.org) – "
                                      "file .tex sẽ mở bằng chương trình mặc định"))

    def save(self):
        st = self.win.settings
        st.setValue("pdf/engine", self.cb_eng.currentData())
        st.setValue("pdf/custom", self.e_custom[0].text())
        st.setValue("pdf/extest", self.e_extest[0].text())
        st.setValue("pdf/runs", self.sp_runs.value())
        st.setValue("pdf/clean", self.c_clean.isChecked())
        st.setValue("pdf/open", self.c_open.isChecked())
        st.setValue("pdf/texstudio", self.e_texstudio[0].text())
        self.accept()
