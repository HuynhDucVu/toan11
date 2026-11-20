"""Hộp thoại cài đặt AI: chọn nhà cung cấp (Gemini, Claude, OpenAI, DeepSeek, Grok), khoá API, mô hình."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QSpinBox)

if TYPE_CHECKING:
    from ..main_window import MainWindow


class AiSettingsDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        from ... import ai
        self.win, st = win, win.settings
        self.setWindowTitle("Cài đặt AI")
        self.resize(660, 360)
        f = QFormLayout(self)
        self.cb_prov = QComboBox()
        for k, name in ai.PROVIDERS:
            self.cb_prov.addItem(name, k)
        self.cb_prov.setCurrentIndex(max(0, self.cb_prov.findData(st.value("ai/provider", "gemini"))))
        f.addRow("Nhà cung cấp", self.cb_prov)
        self.help = QLabel()
        self.help.setWordWrap(True)
        f.addRow(self.help)
        self.e_key = QLineEdit()
        self.e_key.setEchoMode(QLineEdit.EchoMode.Password)
        show = QCheckBox("Hiện khoá")
        show.toggled.connect(lambda v: self.e_key.setEchoMode(QLineEdit.EchoMode.Normal if v
                                                              else QLineEdit.EchoMode.Password))
        self.cb_model = QComboBox()
        self.cb_model.setEditable(True)
        self.cb_effort = QComboBox()
        for e in ("low", "medium", "high"):
            self.cb_effort.addItem(e, e)
        self.cb_effort.setCurrentIndex(max(0, self.cb_effort.findData(st.value("ai/claude_effort", "medium"))))
        self.cb_effort.setToolTip("Claude: mức suy nghĩ – cao hơn thì kĩ hơn nhưng chậm và tốn hơn")
        self.sp_batch = QSpinBox()
        self.sp_batch.setRange(1, 30)
        self.sp_batch.setValue(int(st.value("ai/batch", 10)))
        f.addRow("Khoá API", self.e_key)
        f.addRow("", show)
        f.addRow("Mô hình", self.cb_model)
        self.l_effort = QLabel("Mức suy nghĩ (Claude)")
        f.addRow(self.l_effort, self.cb_effort)
        f.addRow("Số câu mỗi lần gửi (gán ID)", self.sp_batch)
        self.info = QLabel()
        self.info.setWordWrap(True)
        f.addRow(self.info)
        note = QLabel("<i>Khoá lưu trên máy này. Nội dung câu hỏi được gửi tới máy chủ của nhà cung cấp đã chọn. "
                      "Chuyển PDF → LaTeX và chấm bài từ file PDF chỉ dùng được với Gemini hoặc Claude.</i>")
        note.setWordWrap(True)
        f.addRow(note)
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
        self._keys = {}
        self._prev = self.cb_prov.currentData()
        self.cb_prov.currentIndexChanged.connect(self._switch)
        self._load(self._prev)

    def _load(self, p):
        from ... import ai
        st = self.win.settings
        self.e_key.setText(self._keys.get(p, (st.value(ai._k(p, "key"), ""), ""))[0])
        self.cb_model.clear()
        self.cb_model.addItem(self._keys.get(p, ("", ""))[1] or st.value(ai._k(p, "model"), "") or ai.default_model(p))
        self.help.setText(f"Lấy khoá API tại <b>{ai.KEY_HELP[p]}</b>, dán vào ô dưới.")
        self.l_effort.setVisible(p == "claude")
        self.cb_effort.setVisible(p == "claude")
        self.info.setText("")

    def _switch(self):
        self._keys[self._prev] = (self.e_key.text().strip(), self.cb_model.currentText().strip())
        self._prev = self.cb_prov.currentData()
        self._load(self._prev)

    def client(self):
        from ... import ai
        p = self.cb_prov.currentData()
        kw = {"effort": self.cb_effort.currentData()} if p == "claude" else {}
        return ai.make_client(p, self.e_key.text(), self.cb_model.currentText(), **kw)

    def check(self):
        from ...aiid import AIError
        from ... import ai
        try:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            models = self.client().list_models()
        except AIError as e:
            self.info.setText(f"<span style='color:#c00000'>{e}</span>")
            return
        finally:
            QApplication.restoreOverrideCursor()
        cur = self.cb_model.currentText()
        self.cb_model.clear()
        self.cb_model.addItems(models)
        dm = ai.default_model(self.cb_prov.currentData())
        self.cb_model.setCurrentText(cur if cur in models else (dm if dm in models else cur))
        self.info.setText(f"<span style='color:#0b7a0b'>✔ Kết nối được – {len(models)} mô hình dùng được.</span>")

    def save(self):
        from ... import ai
        st = self.win.settings
        self._keys[self.cb_prov.currentData()] = (self.e_key.text().strip(), self.cb_model.currentText().strip())
        for p, (k, m) in self._keys.items():
            st.setValue(ai._k(p, "key"), k)
            st.setValue(ai._k(p, "model"), m)
        st.setValue("ai/provider", self.cb_prov.currentData())
        st.setValue("ai/claude_effort", self.cb_effort.currentData())
        st.setValue("ai/batch", self.sp_batch.value())
        self.accept()


GeminiSettingsDialog = AiSettingsDialog       # tên cũ (tương thích)


def ensure_client(win):
    """Client theo cài đặt; chưa có khoá thì mở hộp cài đặt. Trả về None nếu người dùng bỏ qua."""
    from ... import ai
    from ...aiid import AIError
    for _ in range(2):
        try:
            return ai.client_from_settings(win.settings)
        except AIError:
            if not AiSettingsDialog(win).exec():
                return None
    return None
