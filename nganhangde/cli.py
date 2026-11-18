"""Giao diện dòng lệnh.

    python -m nganhangde import  de1.tex de2.tex      # nạp câu hỏi vào kho
    python -m nganhangde list --id "0H9*" --type TN   # lọc câu
    python -m nganhangde stats                        # thống kê theo chương/mức độ
    python -m nganhangde check de1.tex                # soát lỗi soạn thảo
    python -m nganhangde make ma_tran.json -n 4 -o out # sinh 4 mã đề
    python -m nganhangde export --id "0D8*" -o chuong8.tex
    python -m nganhangde shuffle de.tex -n 4 -o out   # trộn trực tiếp 1 file đề
    python -m nganhangde idmap --load map_id.txt      # nạp giải nghĩa ID
    python -m nganhangde backup saoluu.db             # sao lưu kho
    python -m nganhangde review de.tex --remove-errors -o de_sach.tex   # rà soát, bỏ câu lỗi
    python -m nganhangde gui                          # mở giao diện cửa sổ
"""
from __future__ import annotations

import argparse
import json
import sys

from .db import Bank
from .exporter import export_questions, export_versions
from .generator import MixOptions, NotEnoughQuestions, Rule, make_versions
from .idcode import parse_id
from .parser import parse_file, validate


def cmd_import(bank: Bank, a):
    for path in a.files:
        qs = parse_file(path)
        added = dup = 0
        for q in qs:
            for w in validate(q):
                print(f"  ! {path} [{q.id_code or '?'}] {w}")
            if bank.add(q, path):
                added += 1
            else:
                dup += 1
        print(f"{path}: {len(qs)} câu, thêm {added}, trùng {dup}")


def _filters(a):
    return dict(qtype=a.type, id_like=a.id, muc_do=a.muc_do, text=a.text)


def cmd_list(bank: Bank, a):
    for q in bank.search(**_filters(a)):
        stem = " ".join(q.stem.split())[:80]
        print(f"#{q.db_id:<5} {q.qtype} {q.id_code:<10} {q.answer_text:<8} {stem}")


def cmd_stats(bank: Bank, a):
    print(f"Tổng số câu: {bank.count()}")
    print(f"{'Lớp':<4}{'Môn':<4}{'Ch':<4}{'Loại':<6}{'Mức':<5}{'Số câu':>6}")
    for r in bank.stats():
        print(f"{r['lop']:<4}{r['mon']:<4}{r['chuong']:<4}{r['qtype']:<6}{r['muc_do']:<5}{r['n']:>6}")


def cmd_check(bank, a):
    for path in a.files:
        for i, q in enumerate(parse_file(path), 1):
            ws = validate(q)
            idc = parse_id(q.id_code) if q.id_code else None
            info = idc.describe() if idc else "không có ID"
            dup = bank.find_duplicate(q)
            if dup:
                ws.append(f"Trùng với câu #{dup} trong kho")
            print(f"Câu {i:>2} {q.qtype} {q.id_code:<10} {info}")
            for w in ws:
                print(f"         ! {w}")


def cmd_make(bank: Bank, a):
    with open(a.matrix, encoding="utf-8") as f:
        cfg = json.load(f)
    rules = [Rule.from_dict(r) for r in cfg["rules"]]
    try:
        vs = make_versions(bank, rules, a.n, codes=cfg.get("ma_de"), seed=a.seed,
                           same_questions=not a.different, prefer_unused=a.prefer_unused)
    except NotEnoughQuestions as e:
        sys.exit(f"Không đủ câu:\n{e}")
    files = export_versions(vs, a.out, template_path=a.template or cfg.get("template"),
                            ten_de=cfg.get("ten_de", "ĐỀ KIỂM TRA"),
                            truong=cfg.get("truong", ""), thoi_gian=cfg.get("thoi_gian", 90))
    bank.mark_used({q.db_id for v in vs for q in v.all_questions()})
    for p in files:
        print("Đã ghi", p)


def cmd_idmap(bank: Bank, a):
    from .idmap import load_map, save_map
    if a.load:
        m = load_map(a.load)
        bank.set_idmap(m, replace=a.replace)
        print(f"Đã nạp {len(m)} mục giải nghĩa ID")
    if a.save:
        save_map(bank.idmap(), a.save)
        print(f"Đã xuất ra {a.save}")
    if not a.load and not a.save:
        for k, v in bank.idmap().items():
            print(f"{k:<10}= {v}")


def cmd_shuffle(bank, a):
    from .tools import shuffle_file
    from .generator import answer_distribution
    codes = a.codes.split(",") if a.codes else [str(101 + i) for i in range(a.n)]
    opt = MixOptions(shuffle_q=not a.keep_order, shuffle_ds=not a.no_ds, balance=not a.no_balance)
    vs, files = shuffle_file(a.file, [c.strip() for c in codes], a.out, seed=a.seed, options=opt,
                             template_path=a.template)
    for v in vs:
        print(f"Mã {v.code}: đáp án TN {answer_distribution(v)}")
    print(f"Đã ghi {len(files)} file vào {a.out}")


def cmd_review(bank: Bank, a):
    from . import review as rv
    if a.files:
        src = [(f"{path} câu {i}", q, path) for path in a.files for i, q in enumerate(parse_file(path), 1)]
    else:
        src = [(f"kho #{q.db_id}", q, None) for q in bank.search()]
    bad = []
    n_err = n_warn = 0
    for label, q, path in src:
        iss = rv.review_question(q)
        lv = rv.worst(iss)
        n_err += lv == rv.LOI
        n_warn += lv == rv.CANH_BAO
        if lv == rv.LOI or (lv and not a.only_errors):
            print(f"[{lv}] {label} {q.qtype} {q.id_code}")
            for i in iss:
                print(f"     - {i.level}: {i.msg}")
        if lv == rv.LOI:
            bad.append((q, path))
    print(f"\nTổng {len(src)} câu: {n_err} lỗi, {n_warn} cảnh báo, {len(src) - n_err - n_warn} đạt")
    if a.remove_errors and bad:
        if a.files:
            if not a.out:
                sys.exit("Cần -o FILE_MOI.tex để lưu file đã bỏ câu lỗi (file gốc giữ nguyên)")
            texts = []
            for path in a.files:
                with open(path, encoding="utf-8") as f:
                    t, _ = rv.remove_questions_text(f.read(), [q.raw for q, p in bad if p == path])
                texts.append(t)
            with open(a.out, "w", encoding="utf-8") as f:
                f.write("\n".join(texts))
            print(f"Đã bỏ {len(bad)} câu lỗi, lưu thành {a.out}")
        else:
            bank.delete([q.db_id for q, _ in bad])
            print(f"Đã xoá {len(bad)} câu lỗi khỏi kho")


def cmd_backup(bank: Bank, a):
    bank.backup(a.dest)
    print(f"Đã sao lưu {bank.count()} câu ra {a.dest}")


def cmd_export(bank: Bank, a):
    qs = bank.search(**_filters(a))
    export_questions(qs, a.out, not a.no_solution)
    print(f"Đã xuất {len(qs)} câu ra {a.out}")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="nganhangde", description="Quản lý ngân hàng đề thi LaTeX")
    ap.add_argument("--db", default=None, help="file cơ sở dữ liệu (mặc định nganhang.db)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("import"); p.add_argument("files", nargs="+")
    p = sub.add_parser("check"); p.add_argument("files", nargs="+")
    sub.add_parser("stats")
    sub.add_parser("gui")
    for name in ("list", "export"):
        p = sub.add_parser(name)
        p.add_argument("--type", choices=["TN", "DS", "KQ", "TL"])
        p.add_argument("--id", help="mẫu ID, dùng * và ?, vd 0D2?1-*")
        p.add_argument("--muc-do", choices=list("NHVC"))
        p.add_argument("--text", help="tìm theo nội dung")
        if name == "export":
            p.add_argument("-o", "--out", required=True)
            p.add_argument("--no-solution", action="store_true")
    p = sub.add_parser("idmap", help="giải nghĩa ID: nạp/xuất file .txt")
    p.add_argument("--load")
    p.add_argument("--save")
    p.add_argument("--replace", action="store_true")
    p = sub.add_parser("shuffle", help="trộn trực tiếp 1 file đề .tex thành nhiều mã đề")
    p.add_argument("file")
    p.add_argument("-n", type=int, default=4)
    p.add_argument("--codes", help="vd 132,209,357,485")
    p.add_argument("-o", "--out", default="de_tron")
    p.add_argument("--seed", type=int)
    p.add_argument("--template")
    p.add_argument("--keep-order", action="store_true", help="không trộn thứ tự câu")
    p.add_argument("--no-ds", action="store_true", help="không trộn ý câu Đúng/Sai")
    p.add_argument("--no-balance", action="store_true", help="không cân bằng đáp án A/B/C/D")
    p = sub.add_parser("review", help="rà soát đáp án/lời giải/LaTeX của kho hoặc file .tex")
    p.add_argument("files", nargs="*", help="bỏ trống = rà soát cả kho")
    p.add_argument("--only-errors", action="store_true", help="chỉ in câu có lỗi")
    p.add_argument("--remove-errors", action="store_true", help="xoá câu có lỗi (kho) / bỏ khỏi file mới")
    p.add_argument("-o", "--out", help="file mới khi --remove-errors với file .tex")
    p = sub.add_parser("backup")
    p.add_argument("dest")
    p = sub.add_parser("make")
    p.add_argument("matrix", help="file ma trận .json")
    p.add_argument("-n", type=int, default=4, help="số mã đề")
    p.add_argument("-o", "--out", default="de_xuat")
    p.add_argument("--seed", type=int)
    p.add_argument("--template")
    p.add_argument("--different", action="store_true", help="mỗi mã đề một bộ câu khác nhau")
    p.add_argument("--prefer-unused", action="store_true", help="ưu tiên câu ít được dùng")

    a = ap.parse_args(argv)
    if a.cmd == "gui":
        try:
            from .gui_qt import run          # giao diện Qt (PySide6)
        except ImportError:
            from .gui import run             # dự phòng: Tkinter
        return run(a.db)
    bank = Bank(a.db or "nganhang.db")
    try:
        {"import": cmd_import, "list": cmd_list, "stats": cmd_stats, "check": cmd_check,
         "make": cmd_make, "export": cmd_export, "idmap": cmd_idmap, "shuffle": cmd_shuffle,
         "backup": cmd_backup, "review": cmd_review}[a.cmd](bank, a)
    finally:
        bank.close()


if __name__ == "__main__":
    main()
