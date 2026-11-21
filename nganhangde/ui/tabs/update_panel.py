"""Tab «Cập nhật»: kiểm tra bản mới trên GitHub, xem ghi chú, tải và cài; tuỳ chọn tự kiểm tra / tự tải khi mở phần mềm."""
from __future__ import annotations

import os
import time

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QLabel, QMessageBox, QProgressBar, QPushButton,
                               QTextBrowser, QVBoxLayout, QWidget)
from ... import __version__
from ..workers import UpdateWorker


class UpdatePanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win, self.st = win, win.settings
        self.rel = None
        self._w = None
        lay = QVBoxLayout(self)
        self.head = QLabel()
        self.head.setWordWrap(True)
        lay.addWidget(self.head)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.b_check = QPushButton("🔄 Kiểm tra bản mới")
        self.b_go = QPushButton("⬇ Tải và cập nhật")
        self.b_go.setObjectName("primary")
        self.b_skip = QPushButton("Bỏ qua bản này")
        self.b_page = QPushButton("Mở trang Releases")
        for b in (self.b_check, self.b_go, self.b_skip, self.b_page):
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        self.c_auto = QCheckBox("Tự kiểm tra bản mới mỗi khi mở phần mềm")
        self.c_install = QCheckBox("Tự tải bản mới về ngay khi có (cài khi bạn đồng ý khởi động lại)")
        self.c_auto.setChecked(str(self.st.value("update/auto", True)).lower() == "true")
        self.c_install.setChecked(str(self.st.value("update/autoinstall", False)).lower() == "true")
        self.c_auto.toggled.connect(lambda v: self.st.setValue("update/auto", v))
        self.c_install.toggled.connect(lambda v: self.st.setValue("update/autoinstall", v))
        lay.addWidget(self.c_auto)
        lay.addWidget(self.c_install)
        lay.addWidget(QLabel("<b>Ghi chú bản mới nhất</b>"))
        self.notes = QTextBrowser()
        self.notes.setOpenExternalLinks(True)
        lay.addWidget(self.notes, 1)
        self.b_check.clicked.connect(lambda: self.check())
        self.b_go.clicked.connect(self.download)
        self.b_skip.clicked.connect(self.skip)
        self.b_page.clicked.connect(self.open_page)
        self._refresh_head()
        self._set_buttons()

    # ------------------------------------------------------------ hiển thị
    def _refresh_head(self):
        last = str(self.st.value("update/last_check", "") or "")
        self.head.setText(f"<h3>Bạn đang dùng bản {__version__}</h3>"
                          + (f"Lần kiểm tra gần nhất: {last}" if last else "Chưa kiểm tra bản mới."))

    def can_apply(self) -> bool:
        from ... import updater
        return bool(updater.current_exe()) and os.name == "nt" and bool(self.rel and self.rel.exe_url)

    def _set_buttons(self, busy=False):
        from ... import updater
        newer = bool(self.rel and updater.is_newer(self.rel.version, __version__))
        self.b_check.setEnabled(not busy)
        self.b_go.setEnabled(newer and self.can_apply() and not busy)
        self.b_skip.setEnabled(newer and not busy)
        self.b_page.setEnabled(bool(self.rel and self.rel.page))
        if newer and not self.can_apply():
            self.b_go.setToolTip("Tự cập nhật chỉ dùng với bản NganHangDe.exe trên Windows – bản chạy từ mã nguồn dùng «git pull».")
        else:
            self.b_go.setToolTip("")

    def apply_release(self, rel, *, auto=False):
        """Hiện thông tin bản phát hành vừa kiểm tra."""
        from ... import updater
        self.rel = rel
        self.st.setValue("update/last_check", time.strftime("%d/%m/%Y %H:%M"))
        self._refresh_head()
        self.notes.setMarkdown((rel.notes or "(không có ghi chú)").split("\n## Bản ")[0] if rel.notes else "(không có ghi chú)")
        if updater.is_newer(rel.version, __version__):
            self.status.setText(f"<b style='color:#b35f00'>Có bản mới {rel.version}</b> "
                                f"({rel.size / 1048576:.1f} MB). Bấm «Tải và cập nhật».")
        else:
            self.status.setText(f"<b style='color:#2e7d32'>Bạn đang dùng bản mới nhất ({__version__}).</b>")
        self._set_buttons()

    # ------------------------------------------------------------ kiểm tra
    def check(self, silent=False):
        self.status.setText("Đang kiểm tra bản mới…")
        self._set_buttons(busy=True)
        w = UpdateWorker("check")
        self._w = w

        def done():
            self._set_buttons()
            if w.error:
                self.status.setText(f"<span style='color:#c00000'>{w.error}</span>")
                return
            self.apply_release(w.result)
        w.finished.connect(done)
        w.start()

    def on_startup(self, rel):
        """Kết quả kiểm tra lúc mở phần mềm (đã chạy ở luồng nền). Trả về True nếu panel tự xử lý."""
        from ... import updater
        self.apply_release(rel, auto=True)
        if not updater.is_newer(rel.version, __version__) or self.st.value("update/skip", "") == rel.version:
            return True
        if self.c_install.isChecked() and self.can_apply():
            self.win.main_tabs.setCurrentWidget(self)
            self.download()
            return True
        return False

    # ------------------------------------------------------------ tải và cài
    def download(self):
        from ... import updater
        if not self.rel or not self.can_apply():
            return
        self.bar.setVisible(True)
        self.bar.setValue(0)
        self._set_buttons(busy=True)
        w = UpdateWorker("download", self.rel)
        self._w = w
        w.progress.connect(lambda d, t: (self.bar.setValue(int(100 * d / t) if t else 0),
                                         self.status.setText(f"Đang tải {d / 1048576:.1f}/{t / 1048576:.1f} MB…")))

        def done():
            self.bar.setVisible(False)
            self._set_buttons()
            if w.error:
                self.status.setText(f"<span style='color:#c00000'>{w.error}</span>")
                return
            self.status.setText("Đã tải xong và kiểm tra SHA-256 khớp.")
            if QMessageBox.question(self, "Cập nhật", "Đã tải xong bản mới.\nPhần mềm sẽ đóng, thay bản mới rồi tự mở lại "
                                    "(bản cũ lưu thành NganHangDe_cu.exe).\nKhởi động lại để cập nhật ngay?") \
                    != QMessageBox.StandardButton.Yes:
                self.status.setText("Đã tải xong – bấm «Tải và cập nhật» lần nữa khi muốn cài.")
                return
            try:
                updater.apply_update(w.result)
            except updater.UpdateError as e:
                QMessageBox.warning(self, "Cập nhật", str(e))
                return
            QApplication.quit()
        w.finished.connect(done)
        w.start()

    def skip(self):
        if self.rel:
            self.st.setValue("update/skip", self.rel.version)
            self.status.setText(f"Đã bỏ qua bản {self.rel.version} (lần mở sau không nhắc nữa).")

    def open_page(self):
        if self.rel and self.rel.page:
            QDesktopServices.openUrl(QUrl(self.rel.page))
