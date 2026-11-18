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
    ok = "<<NOI_DUNG>>" in tpl and n == 1 and q.answer_text == "A"
    print("SELFTEST", "OK" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from nganhangde.gui_qt import run
    sys.exit(run())
