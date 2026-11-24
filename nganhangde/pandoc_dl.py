"""Tải pandoc (chuyển LaTeX → Word) về thư mục phần mềm: <thư mục phần mềm>\\pandoc\\pandoc.exe (không cần quyền quản trị)."""
from __future__ import annotations

import json
import os
import tempfile
import urllib.request
import zipfile

API = "https://api.github.com/repos/jgm/pandoc/releases/latest"
FALLBACK_URL = "https://github.com/jgm/pandoc/releases/download/3.6.4/pandoc-3.6.4-windows-x86_64.zip"
UA = {"User-Agent": "NganHangDe"}


class PandocDownloadError(RuntimeError):
    pass


def target_dir() -> str:
    from .appdirs import folder
    return folder("pandoc")


def latest_url(timeout: int = 20) -> str:
    """Địa chỉ file zip Windows 64-bit của bản pandoc mới nhất; không hỏi được GitHub thì dùng bản ghim sẵn."""
    try:
        req = urllib.request.Request(API, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        for a in data.get("assets", []):
            if a.get("name", "").endswith("windows-x86_64.zip"):
                return a["browser_download_url"]
    except Exception:  # noqa: BLE001 – mất mạng, hết lượt gọi API…
        pass
    return FALLBACK_URL


def download_pandoc(dest_dir: str | None = None, url: str | None = None, *, progress=None, should_stop=None) -> str:
    """Tải file zip, giải nén pandoc.exe vào dest_dir; trả về đường dẫn pandoc.exe. progress(đã_tải_MB, tổng_MB hoặc 0)."""
    dest_dir = dest_dir or target_dir()
    url = url or latest_url()
    os.makedirs(dest_dir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="nhd_pandoc_")
    zpath = os.path.join(tmp, "pandoc.zip")
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r, open(zpath, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done // 1048576, total // 1048576)
                if should_stop and should_stop():
                    raise PandocDownloadError("Đã dừng theo yêu cầu.")
        with zipfile.ZipFile(zpath) as z:
            names = [n for n in z.namelist() if n.lower().endswith("pandoc.exe")]
            if not names:
                raise PandocDownloadError("File tải về không chứa pandoc.exe.")
            out = os.path.join(dest_dir, "pandoc.exe")
            with z.open(names[0]) as src, open(out, "wb") as dst:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    dst.write(chunk)
        return out
    except PandocDownloadError:
        raise
    except Exception as e:  # noqa: BLE001
        raise PandocDownloadError(f"Không tải được pandoc ({e}). Kiểm tra mạng, hoặc tải thủ công tại "
                                  "https://pandoc.org/installing.html rồi chép pandoc.exe vào thư mục «pandoc» "
                                  "cạnh phần mềm.") from e
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
