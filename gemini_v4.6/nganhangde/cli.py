import argparse
import sys
from pathlib import Path
from .core.db import QuestionBankDB
from .core.idmap_builtin import export_id6_lookup_html
from .core.parser import parse_tex_questions
from .core.review import audit_question


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="nganhangde", description="CLI Ngân hàng đề Toán toan11 v1.0 (MyLT 2026)")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("gui", help="Mở giao diện đồ họa (gộp v0.9.0 + MyLT 2026)")

    p_imp = sub.add_parser("import", help="Nhập tệp .tex vào cơ sở dữ liệu FTS5")
    p_imp.add_argument("tex_file", help="Đường dẫn tệp .tex")
    p_imp.add_argument("--db", default="nganhang_mylt2026.db")

    p_aud = sub.add_parser("audit", help="Rà soát lỗi CV 1239 cho tệp .tex")
    p_aud.add_argument("tex_file", help="Đường dẫn tệp .tex")

    p_id6 = sub.add_parser("export-id6", help="Xuất trang tra cứu ID6 Toán 6-12 dạng HTML")
    p_id6.add_argument("--out", default="tra_cuu_id6_gdpt2018.html")

    args = ap.parse_args(argv)
    if args.cmd in (None, "gui"):
        from .ui.main_window import main as gui_main
        return gui_main(sys.argv)

    if args.cmd == "import":
        p = Path(args.tex_file)
        qs = parse_tex_questions(p.read_text(encoding="utf-8", errors="ignore"), auto_normalize=True)
        db = QuestionBankDB(args.db)
        st = db.bulk_import(qs, asset_base_dir=str(p.parent))
        db.close()
        print(f"Đã nhập {st['added']} câu mới, bỏ qua {st['duplicates']} câu trùng.")
        return 0

    if args.cmd == "audit":
        p = Path(args.tex_file)
        qs = parse_tex_questions(p.read_text(encoding="utf-8", errors="ignore"))
        total_err = 0
        for i, q in enumerate(qs, 1):
            for iss in audit_question(q, base_dir=str(p.parent)):
                print(f"Câu {i} [{q.primary_id or q.qtype}] ({iss.level}): {iss.message}")
                if iss.level == "ERROR":
                    total_err += 1
        print(f"Tổng số lỗi ERROR: {total_err}")
        return 1 if total_err else 0

    if args.cmd == "export-id6":
        out = export_id6_lookup_html(args.out)
        print(f"Đã xuất trang tra cứu ID6 tại: {out}")
        return 0

    return 0
