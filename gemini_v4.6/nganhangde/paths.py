import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def app_root_dir() -> Path:
    """Thư mục cài đặt của ứng dụng (thư mục chứa NganHangDe.exe hoặc gốc dự án)."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def resource_path(rel_path: str) -> Path:
    cand = bundle_root() / rel_path
    if cand.exists():
        return cand
    return Path(__file__).resolve().parent / rel_path


def user_data_dir(app_name: str = "NganHangDe_Toan11") -> Path:
    """Lưu dữ liệu mặc định (nganhang.db, config.ini, output) ngay trong thư mục NganHangDe."""
    target = app_root_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return target
    except Exception:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or str(Path.home())
        fallback = Path(base) / app_name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
