"""Giao diện & Mathpix: màu chủ đạo, màu nhấn, cỡ chữ, khoá Mathpix (lưu trong config.ini)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QColorDialog, QDialog, QDialogButtonBox, QFormLayout, QLineEdit, QPushButton, QSpinBox)

DEFAULT_MAIN, DEFAULT_ACCENT, DEFAULT_FONT = "#1f4e79", "#e07b00", 10


def themed_style(style: str, main: str, accent: str) -> str:
    """Thay hai màu gốc của STYLE bằng màu người dùng chọn."""
    return style.replace(DEFAULT_MAIN, main).replace(DEFAULT_ACCENT, accent)


def apply_theme(app, st):
    from ..common import STYLE
    main = str(st.value("theme/main", DEFAULT_MAIN))
    acc = str(st.value("theme/accent", DEFAULT_ACCENT))
    app.setStyleSheet(themed_style(STYLE, main if QColor(main).isValid() else DEFAULT_MAIN,
                                   acc if QColor(acc).isValid() else DEFAULT_ACCENT))
    app.setFont(QFont("Segoe UI", int(st.value("theme/font", DEFAULT_FONT) or DEFAULT_FONT)))


class AppearanceDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.st = win, win.settings
        self.setWindowTitle("Giao diện & Mathpix")
        f = QFormLayout(self)
        self.main = str(self.st.value("theme/main", DEFAULT_MAIN))
        self.acc = str(self.st.value("theme/accent", DEFAULT_ACCENT))
        self.b_main, self.b_acc = QPushButton(), QPushButton()
        for b, which in ((self.b_main, "main"), (self.b_acc, "acc")):
            b.clicked.connect(lambda _=False, w=which: self.pick(w))
            self.paint(b, getattr(self, which))
        self.sp = QSpinBox()
        self.sp.setRange(8, 16)
        self.sp.setValue(int(self.st.value("theme/font", DEFAULT_FONT) or DEFAULT_FONT))
        self.e_id = QLineEdit(str(self.st.value("mathpix/app_id", "")))
        self.e_key = QLineEdit(str(self.st.value("mathpix/app_key", "")))
        self.e_key.setEchoMode(QLineEdit.EchoMode.Password)
        f.addRow("Màu chủ đạo (thanh tab chính)", self.b_main)
        f.addRow("Màu nhấn (tab con)", self.b_acc)
        f.addRow("Cỡ chữ", self.sp)
        f.addRow("Mathpix app_id", self.e_id)
        f.addRow("Mathpix app_key", self.e_key)
        rs = QPushButton("Khôi phục màu mặc định")
        rs.clicked.connect(self.reset)
        f.addRow(rs)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.ok)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    @staticmethod
    def paint(b: QPushButton, color: str):
        b.setText(color)
        b.setStyleSheet(f"background:{color}; color:white; font-weight:600;")

    def pick(self, which):
        c = QColorDialog.getColor(QColor(getattr(self, which)), self, "Chọn màu")
        if c.isValid():
            setattr(self, which, c.name())
            self.paint(self.b_main if which == "main" else self.b_acc, c.name())

    def reset(self):
        self.main, self.acc = DEFAULT_MAIN, DEFAULT_ACCENT
        self.paint(self.b_main, self.main)
        self.paint(self.b_acc, self.acc)

    def ok(self):
        for k, v in (("theme/main", self.main), ("theme/accent", self.acc), ("theme/font", self.sp.value()),
                     ("mathpix/app_id", self.e_id.text().strip()), ("mathpix/app_key", self.e_key.text().strip())):
            self.st.setValue(k, v)
        from PySide6.QtWidgets import QApplication
        apply_theme(QApplication.instance(), self.st)
        self.accept()
