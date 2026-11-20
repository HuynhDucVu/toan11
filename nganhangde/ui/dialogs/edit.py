"""Hộp thoại thêm/sửa một câu hỏi bằng mã LaTeX."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout)
from ...parser import parse_tex, validate
from ..common import MAU_CAU, TEN_LOAI, latex_editor
from ..dialogs.pdf import PdfResultDialog

if TYPE_CHECKING:
    from ..main_window import MainWindow


class EditDialog(QDialog):
    """Thêm/sửa 1 câu bằng mã LaTeX, có mẫu sẵn cho 4 loại câu."""

    def __init__(self, win: MainWindow, db_id: int | None):
        super().__init__(win)
        self.win, self.db_id = win, db_id
        self.setWindowTitle(f"Sửa câu #{db_id}" if db_id else "Thêm câu mới")
        self.resize(900, 620)
        lay = QVBoxLayout(self)
        if not db_id:
            row = QHBoxLayout()
            row.addWidget(QLabel("Chèn mẫu:"))
            for k, v in TEN_LOAI.items():
                b = QPushButton(v)
                b.clicked.connect(lambda _=False, k=k: self.editor.setPlainText(MAU_CAU[k]))
                row.addWidget(b)
            row.addStretch()
            lay.addLayout(row)
        self.editor = latex_editor()
        self.editor.setPlainText(win.bank.get(db_id).to_latex() if db_id else MAU_CAU["TN"])
        lay.addWidget(self.editor)
        self.msg = QLabel()
        lay.addWidget(self.msg)
        self.editor.textChanged.connect(self.check)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        b_pdf = bb.addButton("📄 Xem PDF", QDialogButtonBox.ButtonRole.ActionRole)
        b_pdf.clicked.connect(self.preview_pdf)
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Huỷ")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.check()

    def preview_pdf(self):
        from ...pdfbuild import preview_questions
        q, n = self._parse()
        if not q:
            QMessageBox.warning(self, "Xem PDF", f"Cần đúng 1 khối câu hỏi (đang có {n}).")
            return
        eng = self.win.engine()
        if not eng:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            r = preview_questions([q], engine=eng, extest_dir=self.win.pdf_opts()["extest_dir"],
                                  template_path=self.win.gen_panel.e_tpl[0].text() or None)
        finally:
            QApplication.restoreOverrideCursor()
        if r.pdf:
            QDesktopServices.openUrl(QUrl.fromLocalFile(r.pdf))
        if not r.ok:
            PdfResultDialog(self, [r]).exec()

    def _parse(self):
        qs = parse_tex(self.editor.toPlainText())
        return qs[0] if len(qs) == 1 else None, len(qs)

    def check(self):
        q, n = self._parse()
        if not q:
            self.msg.setText(f"<span style='color:#c00000'>Cần đúng 1 khối \\begin{{ex}}…\\end{{ex}} (đang có {n})</span>")
            return
        ws = validate(q)
        self.msg.setText(f"<b>{TEN_LOAI[q.qtype]}</b> • ID {q.id_code or '?'} • Đáp án: <b>{q.answer_text or '—'}</b> • "
                         + (f"<span style='color:#c00000'>{'; '.join(ws)}</span>" if ws
                            else "<span style='color:#0b7a0b'>hợp lệ</span>"))

    def save(self):
        q, n = self._parse()
        if not q:
            QMessageBox.warning(self, "Lỗi", f"Cần đúng 1 khối câu hỏi (đang có {n}).")
            return
        ws = validate(q)
        if ws and QMessageBox.question(self, "Cảnh báo", "\n".join(ws) + "\n\nVẫn lưu?") != QMessageBox.StandardButton.Yes:
            return
        if self.db_id:
            self.win.bank.update(self.db_id, q)
        elif self.win.bank.add(q, "nhap-tay") is None:
            QMessageBox.warning(self, "Trùng", "Câu này đã có trong kho.")
            return
        self.accept()
