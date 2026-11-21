"""Thư mục gói lệnh LaTeX của phần mềm: TEMPLATE\\GOI LENH.

Chép vào đây ex_test.sty (bản mới nhất) và các gói/lớp riêng (.sty, .cls, .def, .cfg…). Phần mềm:
* dùng thư mục này khi biên dịch (TEXINPUTS) – có ex_test.sty thật ở đây thì KHÔNG dùng gói rút gọn đi kèm;
* chép các gói này cạnh mọi file xuất ra (đề, lời giải, quyển chuyên đề…) để mở bằng TeXstudio/Overleaf/máy khác
  vẫn biên dịch được ngay, không cần cài thêm.
"""
from __future__ import annotations

import os
import shutil

EXT = (".sty", ".cls", ".def", ".cfg", ".clo", ".ldf", ".fd", ".bst", ".bbx", ".cbx", ".lbx")


def package_dir() -> str:
    from .appdirs import folder
    d = folder("goi_lenh")
    os.makedirs(d, exist_ok=True)
    return d


def list_packages() -> list[str]:
    d = package_dir()
    return sorted(f for f in os.listdir(d) if f.lower().endswith(EXT) and os.path.isfile(os.path.join(d, f)))


def has_extest() -> bool:
    return "ex_test.sty" in list_packages()


def install_package(src: str) -> str:
    """Chép một file gói vào thư mục gói lệnh (ghi đè bản cũ). Trả về đường dẫn mới."""
    if not src.lower().endswith(EXT):
        raise ValueError("Chỉ chép file gói LaTeX (.sty, .cls, .def…).")
    dst = os.path.join(package_dir(), os.path.basename(src))
    if os.path.abspath(src) != os.path.abspath(dst):
        shutil.copyfile(src, dst)
    return dst


def copy_packages(dest_dir: str) -> list[str]:
    """Chép các gói trong thư mục gói lệnh cạnh file xuất ra. Không làm gì nếu thư mục gói lệnh trống
    (không bao giờ chép gói rút gọn – tránh che mất ex_test thật cài trên máy)."""
    out = []
    try:
        names = list_packages()
    except OSError:
        return out
    if not names:
        return out
    os.makedirs(dest_dir, exist_ok=True)
    src_dir = package_dir()
    for n in names:
        dst = os.path.join(dest_dir, n)
        if os.path.abspath(os.path.join(src_dir, n)) == os.path.abspath(dst):
            continue
        try:
            shutil.copyfile(os.path.join(src_dir, n), dst)
            out.append(dst)
        except OSError:
            pass
    return out
