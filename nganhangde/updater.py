"""Tự cập nhật phiên bản từ trang Releases trên GitHub.

1. latest_release(): đọc bản phát hành mới nhất (số phiên bản, ghi chú, link file NganHangDe.exe, mã SHA-256).
2. download(): tải file exe mới vào thư mục tạm, kiểm tra SHA-256 (chống file hỏng/giả).
3. apply_update(): Windows không cho ghi đè file exe đang chạy ⇒ tạo một file .bat nhỏ:
   chờ phần mềm thoát → sao lưu bản cũ (NganHangDe_cu.exe) → thay bằng bản mới → mở lại phần mềm.
   Phần mềm gọi .bat (chạy ẩn) rồi tự thoát.
Chỉ áp dụng cho bản đóng gói .exe; chạy từ mã nguồn thì dùng «git pull».
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass

REPO = "HuynhDucVu/toan11"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "NganHangDe.exe"


class UpdateError(RuntimeError):
    pass


@dataclass
class Release:
    version: str
    notes: str
    page: str
    exe_url: str = ""
    size: int = 0
    sha256: str = ""


def parse_version(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    return parse_version(latest) > parse_version(current)


def _get_json(url: str, timeout: int = 15) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "NganHangDe-updater",
                                               "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise UpdateError(f"Không kiểm tra được bản mới (cần Internet): {e}") from None


def latest_release(fetch=_get_json) -> Release:
    d = fetch(API_LATEST)
    rel = Release(d.get("tag_name", "").lstrip("v"), d.get("body", "") or "", d.get("html_url", ""))
    for a in d.get("assets", []):
        if a.get("name") == ASSET_NAME:
            rel.exe_url = a.get("browser_download_url", "")
            rel.size = int(a.get("size", 0) or 0)
            dg = a.get("digest") or ""
            rel.sha256 = dg.split(":", 1)[1] if dg.startswith("sha256:") else ""
    return rel


def download(rel: Release, dest_dir: str | None = None, progress=None, should_stop=None) -> str:
    if not rel.exe_url:
        raise UpdateError("Bản phát hành chưa có file NganHangDe.exe")
    dest_dir = dest_dir or tempfile.mkdtemp(prefix="nhd_update_")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"NganHangDe_{rel.version}.exe")
    h = hashlib.sha256()
    req = urllib.request.Request(rel.exe_url, headers={"User-Agent": "NganHangDe-updater"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length") or rel.size or 0)
            done = 0
            while True:
                if should_stop and should_stop():
                    raise UpdateError("Đã huỷ tải")
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
    except UpdateError:
        raise
    except Exception as e:  # noqa: BLE001
        raise UpdateError(f"Tải bản mới thất bại: {e}") from None
    if rel.size and os.path.getsize(dest) != rel.size:
        raise UpdateError("File tải về không đủ dung lượng – thử lại")
    if rel.sha256 and h.hexdigest().lower() != rel.sha256.lower():
        os.remove(dest)
        raise UpdateError("Mã kiểm tra SHA-256 không khớp – file tải về bị hỏng, đã xoá")
    return dest


def current_exe() -> str | None:
    return sys.executable if getattr(sys, "frozen", False) else None


def update_script(pid: int, new_exe: str, target: str) -> str:
    """Nội dung file .bat thay exe sau khi phần mềm thoát (Windows).
    Không dùng tasklist/find (khi chạy ngầm chúng mở cửa sổ đen và có thể treo): chỉ thử chép đè exe, đang chạy thì
    Windows từ chối ⇒ chờ 1 giây rồi thử lại, tối đa ~90 giây."""
    backup = os.path.splitext(target)[0] + "_cu.exe"
    return f"""@echo off
rem Cap nhat Ngan hang de thi (phan mem dang chay co PID {pid}) - tu dong tao boi phan mem
set /a n=0
copy /Y "{target}" "{backup}" >nul 2>&1
:try
copy /Y "{new_exe}" "{target}" >nul 2>&1
if not errorlevel 1 goto ok
set /a n+=1
if %n% GEQ 90 goto fail
ping -n 2 127.0.0.1 >nul
goto try
:ok
del "{new_exe}" >nul 2>&1
start "" "{target}"
goto end
:fail
start "" "{target}"
:end
del "%~f0"
"""


def apply_update(new_exe: str) -> None:
    """Chạy file .bat thay exe (ẩn) – sau đó phần mềm phải tự thoát ngay."""
    target = current_exe()
    if not target or os.name != "nt":
        raise UpdateError("Tự cập nhật chỉ dùng cho bản NganHangDe.exe trên Windows "
                          "(chạy từ mã nguồn thì dùng git pull).")
    folder = os.path.dirname(target)
    if not os.access(folder, os.W_OK):
        raise UpdateError(f"Không có quyền ghi vào {folder} – chép NganHangDe.exe ra thư mục khác "
                          "(vd D:\\NganHangDe) rồi cập nhật lại.")
    bat = os.path.join(tempfile.gettempdir(), "capnhat_nganhangde.bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(update_script(os.getpid(), new_exe, target))
    flags = 0x08000000                       # CREATE_NO_WINDOW (không DETACHED_PROCESS: nếu không, mỗi lệnh con mở một cửa sổ đen)
    subprocess.Popen(["cmd", "/c", bat], creationflags=flags, close_fds=True)
