"""Khởi động ứng dụng."""
from __future__ import annotations

import os
import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from .common import APP_NAME, STYLE
from .main_window import MainWindow
from .workers import UpdateWorker


def run(db_path: str | None = None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    w = MainWindow(db_path)
    w.show()
    auto = str(w.settings.value("update/auto", True)).lower() == "true"
    if auto and (getattr(sys, "frozen", False) or os.environ.get("NHD_UPDATE_CHECK")):
        from PySide6.QtCore import QTimer
        chk = UpdateWorker("check")
        w._update_worker = chk                    # giữ tham chiếu tới khi xong

        def checked():
            if chk.result:
                w.check_update(silent=True, rel=chk.result)
        chk.finished.connect(checked)
        QTimer.singleShot(3000, chk.start)        # đợi phần mềm mở xong rồi mới kiểm tra
    return app.exec()
