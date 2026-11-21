"""Thư mục làm việc của phần mềm (giống cách MyLT để mọi thứ cạnh file chạy):

    NganHangDe\\
    ├── NganHangDe.exe
    ├── config.ini          cài đặt (thay cho Registry) – chép cả thư mục sang máy khác là giữ nguyên cài đặt
    ├── du_lieu\\            kho câu hỏi nganhang.db (+ bản .bak khi nâng cấp)
    ├── mau_de\\             file mẫu đề de_thi.tex (sửa được), gói ex_test rút gọn
    ├── map_id\\             danh mục ID (Map ID) dạng .tex
    ├── de_xuat\\            đề đã trộn (mỗi đợt một thư mục con theo ngày giờ nếu muốn)
    ├── sao_luu\\            bản sao lưu kho
    ├── anh\\                ảnh PNG xuất từ hình TikZ, ảnh câu hỏi
    ├── online\\             bài online, trình chiếu, Google Forms
    ├── tam\\                file tạm khi biên dịch xem trước (xoá thoải mái)
    └── nhat_ky\\            nhật kí lỗi

Thư mục gốc: biến môi trường NHD_HOME → thư mục chứa file .exe (bản đóng gói) → thư mục hiện tại (chạy mã nguồn).
Nếu không ghi được (vd cài trong Program Files) thì dùng %LOCALAPPDATA%\\NganHangDe.
"""
from __future__ import annotations

import os
import shutil
import sys

SUBDIRS = {
    "du_lieu": "Kho câu hỏi (nganhang.db) và bản sao .bak khi nâng cấp",
    "mau_de": "File mẫu đề de_thi.tex (sửa theo trường), gói ex_test rút gọn",
    "map_id": "Danh mục ID (Map ID) dạng .tex",
    "de_xuat": "Đề đã trộn: de_*.tex, loigiai_*.tex, đáp án Excel, PDF…",
    "sao_luu": "Bản sao lưu kho câu hỏi",
    "anh": "Ảnh PNG xuất từ hình TikZ / câu hỏi",
    "online": "Bài làm online, trình chiếu, file Google Forms",
    "tam": "File tạm khi biên dịch xem trước – xoá thoải mái",
    "nhat_ky": "Nhật kí lỗi (nhat_ky.txt) – gửi cho người hỗ trợ khi phần mềm báo lỗi",
}
PKG = os.path.dirname(os.path.abspath(__file__))


def _writable(d: str) -> bool:
    try:
        os.makedirs(d, exist_ok=True)
        t = os.path.join(d, ".nhd_thu_ghi")
        with open(t, "w") as f:
            f.write("x")
        os.remove(t)
        return True
    except OSError:
        return False


def home() -> str:
    env = os.environ.get("NHD_HOME")
    if env:
        return os.path.abspath(env)
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
    if _writable(base):
        return base
    alt = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "NganHangDe")
    os.makedirs(alt, exist_ok=True)
    return alt


def path(sub: str, *parts: str) -> str:
    return os.path.join(home(), sub, *parts)


def ensure_layout(root: str | None = None) -> str:
    """Tạo các thư mục con và chép sẵn file mẫu (không ghi đè file giáo viên đã sửa)."""
    root = root or home()
    for d in SUBDIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    readme = os.path.join(root, "DOC_TOI.txt")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write("THƯ MỤC PHẦN MỀM NGÂN HÀNG ĐỀ THI\n\n"
                    "config.ini  – cài đặt của phần mềm (giữ lại khi chép sang máy khác)\n"
                    + "".join(f"{k + chr(92):<12} – {v}\n" for k, v in SUBDIRS.items()) +
                    "\nChép nguyên thư mục này (kể cả file .exe) sang máy khác/USB là dùng được ngay, giữ đủ kho và cài đặt.\n")
    copies = [(os.path.join(PKG, "templates", "de_thi.tex"), os.path.join(root, "mau_de", "de_thi.tex")),
              (os.path.join(PKG, "templates", "nhd_extest.sty"), os.path.join(root, "mau_de", "ex_test_rut_gon.sty")),
              (os.path.join(PKG, "data", "map_id_toan_6_12.tex"), os.path.join(root, "map_id", "Map_ID_Toan_6_12.tex"))]
    for src, dst in copies:
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copyfile(src, dst)
            except OSError:
                pass
    return root


def default_db(root: str | None = None) -> str:
    """Kho mặc định: du_lieu\\nganhang.db; máy đang dùng bố cục cũ (nganhang.db cạnh exe) thì giữ nguyên kho cũ."""
    root = root or home()
    old = os.path.join(root, "nganhang.db")
    new = os.path.join(root, "du_lieu", "nganhang.db")
    return old if os.path.exists(old) and not os.path.exists(new) else new


def settings_file(root: str | None = None) -> str:
    return os.path.join(root or home(), "config.ini")
