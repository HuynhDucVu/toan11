"""Cửa sổ «HDSD» – hướng dẫn sử dụng từng chức năng (danh mục bên trái, nội dung bên phải)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QSplitter,
                               QTextBrowser, QVBoxLayout)

from ... import hdsd_text


class HdsdDialog(QDialog):
    def __init__(self, win=None, topic: str | None = None):
        super().__init__(win)
        self.setWindowTitle("HDSD – Hướng dẫn sử dụng")
        self.resize(980, 640)
        lay = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.nav = QListWidget()
        self.nav.setMinimumWidth(275)
        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(True)
        split.addWidget(self.nav)
        split.addWidget(self.body)
        split.setStretchFactor(1, 1)
        lay.addWidget(split, 1)
        row = QHBoxLayout()
        row.addWidget(QLabel("Chọn một mục bên trái. Tên nút và tên tab trong hướng dẫn giống phần mềm."))
        row.addStretch()
        b = QPushButton("Đóng")
        b.clicked.connect(self.close)
        row.addWidget(b)
        lay.addLayout(row)
        self._items = []
        group = None
        for g, title, html in hdsd_text.TOPICS:
            if g != group:
                hdr = QListWidgetItem(f"— {g} —")
                hdr.setFlags(Qt.ItemFlag.NoItemFlags)
                self.nav.addItem(hdr)
                group = g
            it = QListWidgetItem(title)
            it.setData(Qt.ItemDataRole.UserRole, (title, html))
            self.nav.addItem(it)
            self._items.append(it)
        self.nav.currentItemChanged.connect(self._show)
        if topic:
            self.open_topic(topic)
        else:
            self.nav.setCurrentItem(self._items[0])

    def _show(self, cur, _prev=None):
        if cur is None or not cur.data(Qt.ItemDataRole.UserRole):
            return
        title, html = cur.data(Qt.ItemDataRole.UserRole)
        self.body.setHtml(f"<h2>{title}</h2>{html}")

    def open_topic(self, title: str):
        """Mở đúng mục theo tiêu đề (dùng từ nút HDSD ở từng tab)."""
        for it in self._items:
            if it.text() == title:
                self.nav.setCurrentItem(it)
                return True
        self.nav.setCurrentItem(self._items[0])
        return False


def show_hdsd(win, topic: str | None = None):
    dlg = HdsdDialog(win, topic)
    dlg.exec()
    return dlg
