"""Hộp thoại cập nhật phần mềm."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressDialog,
    QPushButton, QTextBrowser, QVBoxLayout)
from ... import __version__
from ..workers import UpdateWorker

if TYPE_CHECKING:
    from ..main_window import MainWindow


class UpdateDialog(QDialog):
    def __init__(self, win: MainWindow, rel):
        super().__init__(win)
        from ... import updater
        self.win, self.rel = win, rel
        self.setWindowTitle(f"Có bản mới {rel.version}")
        self.resize(720, 560)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(f"<h3>Đã có bản {rel.version}</h3>Bạn đang dùng bản {__version__}. "
                             f"Dung lượng tải: {rel.size / 1048576:.1f} MB."))
        notes = QTextBrowser()
        notes.setMarkdown(rel.notes.split("\n## Bản ")[0] if rel.notes else "(không có ghi chú)")
        lay.addWidget(notes, 1)
        self.bar = QLabel()
        lay.addWidget(self.bar)
        row = QHBoxLayout()
        self.c_auto = QCheckBox("Tự kiểm tra bản mới mỗi khi mở phần mềm")
        self.c_auto.setChecked(str(win.settings.value("update/auto", True)).lower() == "true")
        row.addWidget(self.c_auto)
        row.addStretch()
        skip = QPushButton("Bỏ qua bản này")
        skip.clicked.connect(self.skip)
        page = QPushButton("Mở trang tải")
        page.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(rel.page)))
        self.b_go = QPushButton("⬇ Tải và cập nhật ngay")
        self.b_go.setObjectName("primary")
        self.b_go.clicked.connect(self.go)
        can = bool(updater.current_exe()) and os.name == "nt" and bool(rel.exe_url)
        if not can:
            self.b_go.setEnabled(False)
            self.b_go.setToolTip("Tự cập nhật chỉ dùng với bản NganHangDe.exe trên Windows – "
                                 "bản chạy từ mã nguồn dùng «git pull».")
        for b in (skip, page, self.b_go):
            row.addWidget(b)
        lay.addLayout(row)

    def done(self, r):
        self.win.settings.setValue("update/auto", self.c_auto.isChecked())
        super().done(r)

    def skip(self):
        self.win.settings.setValue("update/skip", self.rel.version)
        self.reject()

    def go(self):
        from ... import updater
        dlg = QProgressDialog("Đang tải bản mới…", "Huỷ", 0, 100, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        w = UpdateWorker("download", self.rel)
        w.progress.connect(lambda d, t: (dlg.setValue(int(100 * d / t) if t else 0),
                                         dlg.setLabelText(f"Đã tải {d / 1048576:.1f}/{t / 1048576:.1f} MB")))
        dlg.canceled.connect(w.requestInterruption)
        w.start()
        while w.isRunning():
            QApplication.processEvents()
            w.wait(50)
        dlg.close()
        if w.error:
            QMessageBox.warning(self, "Cập nhật", w.error)
            return
        if QMessageBox.question(self, "Cập nhật", "Đã tải và kiểm tra xong bản mới (SHA-256 khớp).\n"
                                "Phần mềm sẽ đóng, thay bản mới rồi tự mở lại (bản cũ lưu thành NganHangDe_cu.exe).\n"
                                "Tiếp tục?") != QMessageBox.StandardButton.Yes:
            return
        try:
            updater.apply_update(w.result)
        except updater.UpdateError as e:
            QMessageBox.warning(self, "Cập nhật", str(e))
            return
        QApplication.quit()
