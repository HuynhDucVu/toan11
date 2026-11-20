"""Hộp thoại cài đặt Gemini (khoá API, mô hình)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox)

if TYPE_CHECKING:
    from ..main_window import MainWindow


class GeminiSettingsDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        from ... import aiid
        self.win, st = win, win.settings
        self.setWindowTitle("Cài đặt Gemini (AI)")
        self.resize(620, 300)
        f = QFormLayout(self)
        f.addRow(QLabel("Lấy khoá API miễn phí tại <b>aistudio.google.com/apikey</b> (đăng nhập tài khoản Google → "
                        "<i>Create API key</i>), rồi dán vào ô dưới. Khoá được lưu trên máy này."))
        self.e_key = QLineEdit(st.value("ai/key", ""))
        self.e_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.e_key.setPlaceholderText("AIza…")
        show = QCheckBox("Hiện khoá")
        show.toggled.connect(lambda v: self.e_key.setEchoMode(QLineEdit.EchoMode.Normal if v
                                                              else QLineEdit.EchoMode.Password))
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        self.cb_model.addItem(st.value("ai/model", aiid.DEFAULT_MODEL))
        self.sp_batch = QSpinBox()
        self.sp_batch.setRange(1, 30)
        self.sp_batch.setValue(int(st.value("ai/batch", 10)))
        f.addRow("Khoá API", self.e_key)
        f.addRow("", show)
        f.addRow("Mô hình", self.cb_model)
        f.addRow("Số câu mỗi lần gửi", self.sp_batch)
        self.info = QLabel()
        self.info.setWordWrap(True)
        f.addRow(self.info)
        row = QHBoxLayout()
        b = QPushButton("Kiểm tra kết nối / tải danh sách mô hình")
        b.clicked.connect(self.check)
        ok = QPushButton("Lưu")
        ok.setObjectName("primary")
        ok.clicked.connect(self.save)
        row.addWidget(b)
        row.addStretch()
        row.addWidget(ok)
        f.addRow(row)

    def check(self):
        from ... import aiid
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            models = aiid.GeminiClient(self.e_key.text()).list_models()
        except aiid.AIError as e:
            self.info.setText(f"<span style='color:#c00000'>{e}</span>")
            return
        finally:
            QApplication.restoreOverrideCursor()
        cur = self.cb_model.currentText()
        self.cb_model.clear()
        self.cb_model.addItems(models)
        if cur in models:
            self.cb_model.setCurrentText(cur)
        elif aiid.DEFAULT_MODEL in models:
            self.cb_model.setCurrentText(aiid.DEFAULT_MODEL)
        self.info.setText(f"<span style='color:#0b7a0b'>✔ Kết nối được – {len(models)} mô hình dùng được. "
                          "Nên chọn bản «flash» (nhanh, hạn mức miễn phí rộng).</span>")

    def save(self):
        st = self.win.settings
        st.setValue("ai/key", self.e_key.text().strip())
        st.setValue("ai/model", self.cb_model.currentText().strip())
        st.setValue("ai/batch", self.sp_batch.value())
        self.accept()
