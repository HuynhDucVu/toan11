"""Mở file .tex bằng trình soạn LaTeX bên ngoài (TeXstudio; dự phòng: chương trình mặc định của máy).

TeXstudio hỗ trợ tham số «--line N» để nhảy tới dòng lỗi.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess

NO_WINDOW = {"creationflags": 0x00000008} if os.name == "nt" else {}       # DETACHED_PROCESS


def find_texstudio(custom: str = "") -> str | None:
    if custom and os.path.isfile(custom):
        return custom
    p = shutil.which("texstudio")
    if p:
        return p
    cands = []
    for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(k, "")
        if base:
            cands += [os.path.join(base, "texstudio", "texstudio.exe"),
                      os.path.join(base, "Programs", "texstudio", "texstudio.exe")]
    cands += glob.glob("/Applications/texstudio*.app/Contents/MacOS/texstudio")
    return next((c for c in cands if os.path.isfile(c)), None)


def open_in_texstudio(path: str, line: int | None = None, custom: str = "") -> bool:
    """Mở file trong TeXstudio (nhảy tới dòng `line` nếu có). Trả về False nếu máy không có TeXstudio."""
    exe = find_texstudio(custom)
    if not exe:
        return False
    args = [exe, os.path.abspath(path)]
    if line:
        args += ["--line", str(line)]
    subprocess.Popen(args, close_fds=True, **NO_WINDOW)
    return True


def first_error_line(errors: list[str]) -> int | None:
    """Lấy số dòng từ thông báo lỗi dạng «Dòng 12: …» (do pdfbuild sinh ra)."""
    import re
    for e in errors or []:
        m = re.match(r"Dòng (\d+):", e)
        if m:
            return int(m.group(1))
    return None
