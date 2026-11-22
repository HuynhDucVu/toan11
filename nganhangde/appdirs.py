"""Thư mục làm việc của phần mềm – bố cục giống MyLT 2026 (mọi thứ cạnh file chạy):

    NganHangDe\\
    ├── NganHangDe.exe
    ├── config.ini            cài đặt (thay cho Registry) – chép cả thư mục sang máy khác là giữ nguyên
    ├── DATA\\
    │   ├── BANK\\            kho câu hỏi nganhang.db (+ SAO LUU\\ bản sao lưu)
    │   ├── DE\\              đề đã trộn (de_*.tex, loigiai_*.tex, đáp án, PDF…)
    │   ├── EXAM\\            bài làm online, trình chiếu
    │   ├── AUTO\\            câu đổi số / câu sinh tự động
    │   ├── MA TRAN DE\\      ma trận đề (.json, .xlsx)
    │   ├── TUONG TU\\        đề tương tự
    │   ├── WORD2EXTEST\\     Word → TeX (ex_test)      EXTEST2WORD\\  TeX → Word      PDF2TEX\\  PDF → TeX
    │   ├── MOODLE XML\\  MFORMS\\ (Google Forms/Blogger)  PDF QUIZ\\
    │   ├── LOC ID\\  LOC TIKZ\\  IMG\\
    │   └── Phiếu TLTN THPT QG 2025 (1 mặt).pdf
    ├── TEMPLATE\\            file mẫu đề de_thi.tex (sửa được), gói ex_test rút gọn
    ├── Map ID (DPS)\\        danh mục ID (Map ID) dạng .tex
    ├── TEMP\\                file tạm khi biên dịch (xoá thoải mái)
    └── LOG\\                 nhật kí lỗi

Thư mục gốc: biến môi trường NHD_HOME → thư mục chứa file .exe (bản đóng gói) → thư mục hiện tại (chạy mã nguồn).
Nếu không ghi được (vd cài trong Program Files) thì dùng %LOCALAPPDATA%\\NganHangDe.
Bản cũ dùng tên du_lieu, mau_de, de_xuat… vẫn chạy: thư mục cũ còn thì dùng tiếp, không tự di chuyển dữ liệu.
"""
from __future__ import annotations

import os
import shutil
import sys

# khoá nội bộ → (thư mục theo bố cục MyLT 2026, tên thư mục cũ của các bản trước, mô tả)
LAYOUT = {
    "du_lieu": ("DATA/BANK", "du_lieu", "Kho câu hỏi (nganhang.db) và bản sao .bak khi nâng cấp"),
    "sao_luu": ("DATA/BANK/SAO LUU", "sao_luu", "Bản sao lưu kho câu hỏi"),
    "de_xuat": ("DATA/DE", "de_xuat", "Đề đã trộn: de_*.tex, loigiai_*.tex, đáp án Excel, PDF…"),
    "exam": ("DATA/EXAM", "online", "Bài làm online, trình chiếu"),
    "online": ("DATA/EXAM", "online", "Bài làm online, trình chiếu"),
    "auto": ("DATA/AUTO", "", "Câu đổi số / câu sinh tự động"),
    "ma_tran": ("DATA/MA TRAN DE", "", "Ma trận đề (.json, .xlsx)"),
    "tuong_tu": ("DATA/TUONG TU", "", "Đề tương tự"),
    "word2extest": ("DATA/WORD2EXTEST", "", "File Word và kết quả chuyển Word → TeX"),
    "extest2word": ("DATA/EXTEST2WORD", "", "Kết quả chuyển TeX → Word"),
    "pdf2tex": ("DATA/PDF2TEX", "", "File PDF và kết quả chuyển PDF → TeX"),
    "moodle": ("DATA/MOODLE XML", "", "File Moodle XML"),
    "mforms": ("DATA/MFORMS", "", "Google Forms / Blogger"),
    "pdf_quiz": ("DATA/PDF QUIZ", "", "Bài trắc nghiệm PDF (gói exerquiz)"),
    "loc_id": ("DATA/LOC ID", "", "Câu lọc theo ID"),
    "loc_tikz": ("DATA/LOC TIKZ", "", "Hình TikZ tách từ đề"),
    "anh": ("DATA/IMG", "anh", "Ảnh PNG xuất từ hình TikZ / câu hỏi"),
    "mau_de": ("TEMPLATE", "mau_de", "File mẫu đề de_thi.tex (sửa theo trường), gói ex_test rút gọn"),
    "map_id": ("Map ID (DPS)", "map_id", "Danh mục ID (Map ID) dạng .tex"),
    "goi_lenh": ("TEMPLATE/GOI LENH", "", "Gói lệnh LaTeX dùng khi biên dịch: chép ex_test.sty (bản mới nhất) và các gói riêng vào đây"),
    "pandoc": ("pandoc", "", "pandoc.exe (tải bằng Công cụ → Tải pandoc) – chuyển LaTeX → Word"),
    "tam": ("TEMP", "tam", "File tạm khi biên dịch xem trước – xoá thoải mái"),
    "nhat_ky": ("LOG", "nhat_ky", "Nhật kí lỗi (nhat_ky.txt) – gửi cho người hỗ trợ khi phần mềm báo lỗi"),
}
SUBDIRS = {k: v[2] for k, v in LAYOUT.items()}        # tương thích tên cũ
PKG = os.path.dirname(os.path.abspath(__file__))
PHIEU_PDF = "Phieu_TLTN_THPT_QG_2025_1_mat.pdf"


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


def folder(key: str, root: str | None = None) -> str:
    """Thư mục theo khoá (vd 'de_xuat' → DATA\\DE). Máy đang dùng thư mục tên cũ (de_xuat…) thì giữ dùng tiếp."""
    root = root or home()
    if key not in LAYOUT:
        return os.path.join(root, key)                   # tên lạ: dùng nguyên
    new, old, _ = LAYOUT[key]
    newp = os.path.join(root, *new.split("/"))
    oldp = os.path.join(root, old) if old else ""
    if oldp and os.path.isdir(oldp) and not os.path.isdir(newp):
        return oldp
    return newp


def path(sub: str, *parts: str) -> str:
    return os.path.join(folder(sub), *parts)


def ensure_layout(root: str | None = None) -> str:
    """Tạo các thư mục con và chép sẵn file mẫu (không ghi đè file giáo viên đã sửa)."""
    root = root or home()
    for key in LAYOUT:
        os.makedirs(folder(key, root), exist_ok=True)
    readme = os.path.join(root, "DOC_TOI.txt")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write("THƯ MỤC PHẦN MỀM NGÂN HÀNG ĐỀ THI (bố cục giống MyLT 2026)\n\n"
                    "config.ini  – cài đặt của phần mềm (giữ lại khi chép sang máy khác)\n"
                    + "".join(f"{LAYOUT[k][0].replace('/', chr(92)) + chr(92):<26} – {LAYOUT[k][2]}\n"
                              for k in dict.fromkeys(LAYOUT) if k not in ("online",)) +
                    "\nChép nguyên thư mục này (kể cả file .exe) sang máy khác/USB là dùng được ngay, giữ đủ kho và cài đặt.\n")
    readme_pk = os.path.join(folder("goi_lenh", root), "DOC_TOI.txt")
    if not os.path.exists(readme_pk):
        try:
            with open(readme_pk, "w", encoding="utf-8") as f:
                f.write("GÓI LỆNH LATEX DÙNG KHI BIÊN DỊCH\n\n"
                        "Chép vào đây ex_test.sty (bản mới nhất) và các gói/lớp riêng (.sty, .cls, .def…).\n"
                        "- Biên dịch trong phần mềm: dùng các gói ở đây (có ex_test.sty thật thì không dùng gói rút gọn).\n"
                        "- Mọi file xuất ra (đề, lời giải, quyển chuyên đề…) được chép kèm các gói này, nên mở bằng\n"
                        "  TeXstudio/Overleaf/máy khác vẫn biên dịch được ngay.\n"
                        "Cách chép nhanh: menu Công cụ → «Cài gói ex_test / gói lệnh LaTeX…».\n")
        except OSError:
            pass
    copies = [(os.path.join(PKG, "templates", "de_thi.tex"), os.path.join(folder("mau_de", root), "de_thi.tex")),
              (os.path.join(PKG, "templates", "nhd_extest.sty"), os.path.join(folder("mau_de", root), "ex_test_rut_gon.sty")),
              (os.path.join(PKG, "templates", "Header_MyLT.tex"), os.path.join(folder("mau_de", root), "Header_MyLT.tex")),
              (os.path.join(PKG, "data", "map_id_toan_6_12.tex"), os.path.join(folder("map_id", root), "Map_ID_Toan_6_12.tex")),
              (os.path.join(PKG, "data", "Map_ID_Moi.tex"), os.path.join(folder("map_id", root), "Map_ID_Moi.tex")),
              (os.path.join(PKG, "data", PHIEU_PDF), os.path.join(root, "DATA", PHIEU_PDF.replace("_", " ")))]
    if not os.environ.get("NHD_NO_BUNDLED_PKG"):
        # gói ex_test mới nhất (v3.1, 21/10/2024 – Trần Anh Tuấn, Dương Phước Sang) vào thư mục gói lệnh: biên dịch dùng bản này,
        # file xuất ra được chép kèm. (Thư mục gói lệnh đã có ex_test.sty của người dùng thì giữ nguyên.)
        copies.append((os.path.join(PKG, "data", "ex_test.sty"), os.path.join(folder("goi_lenh", root), "ex_test.sty")))
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
    new = os.path.join(folder("du_lieu", root), "nganhang.db")
    return old if os.path.exists(old) and not os.path.exists(new) else new


def settings_file(root: str | None = None) -> str:
    return os.path.join(root or home(), "config.ini")
