"""Điểm chạy khi đóng gói .exe (PyInstaller).

    NganHangDe.exe              mở giao diện
    NganHangDe.exe --selftest   kiểm tra nhanh bản đóng gói (đọc mẫu đề, tạo kho tạm)
"""
import sys


def selftest() -> int:
    import os
    import tempfile

    from nganhangde.db import Bank
    from nganhangde.exporter import load_template
    from nganhangde.parser import parse_tex

    tpl = load_template()
    q = parse_tex("\\begin{ex}%[0D1N1-1]\nA\n\\choice{\\True 1}{2}{3}{4}\n\\loigiai{x}\n\\end{ex}")[0]
    with tempfile.TemporaryDirectory() as d:
        b = Bank(os.path.join(d, "t.db"))
        b.add(q)
        n = b.count()
        b.close()
    import openpyxl  # noqa: F401  – cần cho file đáp án TNMaker
    import pypdf  # noqa: F401  – PDF → LaTeX (cắt trang)
    import anthropic  # noqa: F401  – nhà cung cấp AI Claude
    import pypdfium2  # noqa: F401  – hoá ảnh hình TikZ
    import access_parser  # noqa: F401  – nhập ngân hàng MyLT (Bank.mylt)
    from nganhangde.idmap import builtin_map
    nmap = len(builtin_map())
    import os as _os
    from nganhangde.online import mathjax_local
    nmap = nmap if _os.path.getsize(mathjax_local()) > 1_000_000 else 0     # MathJax đi kèm
    ok = "<<NOI_DUNG>>" in tpl and n == 1 and q.answer_text == "A" and nmap > 1000
    print("SELFTEST", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from nganhangde.gui_qt import run
    sys.exit(run())
