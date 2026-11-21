"""Khởi động ứng dụng."""
from __future__ import annotations

import os
import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication
from .common import APP_NAME, STYLE
from .main_window import MainWindow
from .workers import UpdateWorker


def _setup_log():
    """Ghi lỗi bất ngờ vào nhat_ky\\nhat_ky.txt (giống thư mục LOG của MyLT) và báo cho người dùng."""
    import logging
    import traceback
    from ..appdirs import ensure_layout, path
    try:
        ensure_layout()
        logging.basicConfig(filename=path("nhat_ky", "nhat_ky.txt"), level=logging.INFO, encoding="utf-8",
                            format="%(asctime)s %(levelname)s %(message)s")
    except OSError:
        return
    old = sys.excepthook

    def hook(t, v, tb):
        logging.error("Lỗi không mong muốn:\n%s", "".join(traceback.format_exception(t, v, tb)))
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(None, "Lỗi", f"{v}\n\nĐã ghi chi tiết vào nhat_ky\\nhat_ky.txt – gửi file này "
                                            "cho người hỗ trợ nếu lỗi lặp lại.")
        except Exception:  # noqa: BLE001
            pass
        old(t, v, tb)
    sys.excepthook = hook


def run(db_path: str | None = None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    icon = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "app.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    _setup_log()
    w = MainWindow(db_path)
    from .dialogs.appearance import apply_theme
    apply_theme(app, w.settings)
    w.show()
    from PySide6.QtCore import QTimer as _T
    _T.singleShot(400, w.welcome_if_empty)
    auto = str(w.settings.value("update/auto", True)).lower() == "true"
    if auto and (getattr(sys, "frozen", False) or os.environ.get("NHD_UPDATE_CHECK")):
        from PySide6.QtCore import QTimer
        chk = UpdateWorker("check")
        w._update_worker = chk                    # giữ tham chiếu tới khi xong

        def checked():
            if chk.result:
                if not w.update_panel.on_startup(chk.result):       # chưa bật «tự tải»: hiện hộp thông báo như trước
                    w.check_update(silent=True, rel=chk.result)
        chk.finished.connect(checked)
        QTimer.singleShot(3000, chk.start)        # đợi phần mềm mở xong rồi mới kiểm tra
    return app.exec()
