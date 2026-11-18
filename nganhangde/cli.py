"""Giao diện dòng lệnh.

    python -m nganhangde import  de1.tex de2.tex      # nạp câu hỏi vào kho
    python -m nganhangde list --id "0H9*" --type TN   # lọc câu
    python -m nganhangde stats                        # thống kê theo chương/mức độ
    python -m nganhangde check de1.tex                # soát lỗi soạn thảo
    python -m nganhangde make ma_tran.json -n 4 -o out # sinh 4 mã đề
    python -m nganhangde export --id "0D8*" -o chuong8.tex
    python -m nganhangde shuffle de.tex -n 4 -o out   # trộn trực tiếp 1 file đề
    python -m nganhangde shuffle de.tex --chuan-2026 -o out   # 24 mã 0101…0124 + đáp án TNMaker
    python -m nganhangde idmap --load map_id.txt      # nạp giải nghĩa ID
    python -m nganhangde backup saoluu.db             # sao lưu kho
    python -m nganhangde idmap --load Map_ID.tex      # nạp Map ID (định dạng gạch ngang)
    python -m nganhangde suggest-id de.tex --scope 0 --auto 0.45 -o de_ganID.tex
    python -m nganhangde review de.tex --fix theo-loi-giai --add-conclusion --remove-errors -o de_sach.tex
    python -m nganhangde gui                          # mở giao diện cửa sổ
"""
from __future__ import annotations

import argparse
import json
import sys

from .db import Bank
from .exporter import export_questions, export_versions
from .generator import NotEnoughQuestions, Rule, make_versions
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


def _exam_opts(a):
    from .exporter import ExportOptions
    from .generator import MixOptions
    std = getattr(a, "chuan_2026", False)
    mix = MixOptions(shuffle_q=not getattr(a, "keep_order", False),
                     shuffle_ds=not (std or getattr(a, "no_ds", False)),
                     balance=not getattr(a, "no_balance", False))
    exp = ExportOptions(renumber=std, official_titles=std, scoring=std,
                        tnmaker_layout=a.tnmaker_layout, ds_style=a.tnmaker_ds,
                        online_html=a.online, moodle=a.moodle, word=a.word)
    return mix, exp


def _maybe_pdf(a, files):
    if not getattr(a, "pdf", False):
        return
    from .pdfbuild import compile_tex, find_engine
    eng = find_engine()
    for f in files:
        if f.endswith(".tex"):
            print("  PDF:", compile_tex(f, eng).summary())


def _add_exam_flags(p):
    p.add_argument("--chuan-2026", action="store_true",
                   help="chuẩn đề tốt nghiệp: 24 mã 0101…0124, giữ ý Đúng/Sai, đánh số lại, lời dẫn, thang điểm")
    p.add_argument("--tnmaker-layout", choices=["doc", "ngang"], default="doc", help="bố cục file đáp án Excel")
    p.add_argument("--tnmaker-ds", choices=["gop", "tach"], default="gop", help="phần II: gộp ĐSĐS hay tách 4 ô")
    p.add_argument("--online", action="store_true", help="thêm bài làm online (HTML) cho mỗi mã đề")
    p.add_argument("--moodle", action="store_true", help="thêm file Moodle XML")
    p.add_argument("--word", action="store_true", help="thêm file Word .docx mỗi mã đề (cần pandoc)")
    p.add_argument("--pdf", action="store_true", help="biên dịch luôn các file đề/lời giải ra PDF")


def cmd_make(bank: Bank, a):
    with open(a.matrix, encoding="utf-8") as f:
        cfg = json.load(f)
    rules = [Rule.from_dict(r) for r in cfg["rules"]]
    from .generator import THPT_2026, check_structure, make_codes
    mix, exp = _exam_opts(a)
    codes = cfg.get("ma_de")
    if a.chuan_2026:
        for d in check_structure(rules):
            print("! Lệch cấu trúc 2026:", d)
        codes = codes or make_codes(THPT_2026["so_ma"], 101, 4)
    try:
        vs = make_versions(bank, rules, a.n, codes=codes, seed=a.seed, options=mix,
                           same_questions=not a.different, prefer_unused=a.prefer_unused)
    except NotEnoughQuestions as e:
        sys.exit(f"Không đủ câu:\n{e}")
    files = export_versions(vs, a.out, template_path=a.template or cfg.get("template"),
                            ten_de=cfg.get("ten_de", "ĐỀ KIỂM TRA"),
                            truong=cfg.get("truong", ""), thoi_gian=cfg.get("thoi_gian", 90), options=exp)
    bank.mark_used({q.db_id for v in vs for q in v.all_questions()})
    for p in files:
        print("Đã ghi", p)
    _maybe_pdf(a, files)


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
    from .generator import THPT_2026, make_codes
    if a.codes:
        codes = a.codes.split(",")
    elif a.chuan_2026:
        codes = make_codes(THPT_2026["so_ma"], 101, 4)
    else:
        codes = make_codes(a.n)
    mix, exp = _exam_opts(a)
    vs, files = shuffle_file(a.file, [c.strip() for c in codes], a.out, seed=a.seed, options=mix,
                             template_path=a.template, export_options=exp)
    for v in vs:
        print(f"Mã {v.code}: đáp án TN {answer_distribution(v)}")
    print(f"Đã ghi {len(files)} file vào {a.out}")
    _maybe_pdf(a, files)


def cmd_review(bank: Bank, a):
    from . import review as rv
    if a.files:
        src = [(f"{path} câu {i}", q, path) for path in a.files for i, q in enumerate(parse_file(path), 1)]
    else:
        src = [(f"kho #{q.db_id}", q, None) for q in bank.search()]
    bad, fixes = [], []
    n_err = n_warn = 0
    for label, q, path in src:
        if a.fix:
            nq, done = rv.fix_question(q, rv.THEO_DAP_AN if a.fix == "theo-dap-an" else rv.THEO_LOI_GIAI)
            if a.add_conclusion:
                nq2, added = rv.add_conclusion(nq)
                if added:
                    nq, done = nq2, done + ["Thêm câu kết luận"]
            if done:
                print(f"[Sửa] {label}: {'; '.join(done)}")
                fixes.append((q, nq, path))
                q = nq
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
    if fixes and not a.files:
        for old, nq, _ in fixes:
            bank.update(old.db_id, nq)
        print(f"Đã sửa {len(fixes)} câu trong kho")
    if (a.remove_errors and bad) or (fixes and a.files):
        if a.files:
            if not a.out:
                sys.exit("Cần -o FILE_MOI.tex để lưu file đã sửa/bỏ câu lỗi (file gốc giữ nguyên)")
            texts = []
            for path in a.files:
                with open(path, encoding="utf-8") as f:
                    t, _ = rv.replace_questions_text(f.read(), [(o.raw, nq.to_latex()) for o, nq, p in fixes if p == path])
                    if a.remove_errors:
                        t, _ = rv.remove_questions_text(t, [q.to_latex() if q.raw == "" else q.raw for q, p in bad
                                                            if p == path] + [nq.to_latex() for o, nq, p in fixes
                                                            if p == path and any(b is nq for b, _ in bad)])
                texts.append(t)
            with open(a.out, "w", encoding="utf-8") as f:
                f.write("\n".join(texts))
            print(f"Đã sửa {len(fixes)} câu" + (f", bỏ {len(bad)} câu lỗi" if a.remove_errors else "")
                  + f", lưu thành {a.out}")
        elif a.remove_errors:
            bank.delete([q.db_id for q, _ in bad])
            print(f"Đã xoá {len(bad)} câu lỗi khỏi kho")


def cmd_suggest_id(bank: Bank, a):
    """Gợi ý ID cho câu (thiếu ID) trong file; --auto NGƯỠNG -o FILE để ghi ID gợi ý có độ giống ≥ ngưỡng."""
    from . import review as rv
    from .idsuggest import MapSuggester, Suggester, combine
    m = bank.idmap()
    bs = Suggester([q for q in bank.search() if q.id_code.startswith(a.scope)])
    ms = MapSuggester(m, a.scope)
    if not len(bs) and not len(ms):
        sys.exit("Kho chưa có câu có ID và chưa có Map ID – nạp Map ID trước: idmap --load Map_ID.tex")
    with open(a.file, encoding="utf-8") as f:
        text = f.read()
    pairs = []
    for i, q in enumerate(parse_file(a.file), 1):
        if q.id_code and not a.all:
            continue
        idc = parse_id(q.id_code) if q.id_code else None
        sg = combine(bs.suggest(q, 3) if len(bs) else [], ms.suggest(q, idc.muc_do if idc else a.level, 3), 3)
        stem = " ".join(q.stem.split())[:60]
        print(f"Câu {i:>3} [{q.id_code or '—'}] {stem}")
        for s_ in sg:
            print(f"        {s_.id_code:<10} {s_.score:4.0%}  {s_.sample[:70]}")
        if a.auto is not None and sg and sg[0].score >= a.auto:
            old = q.raw
            q.set_id(sg[0].id_code)
            pairs.append((old, q.raw))
    if a.auto is not None:
        if not a.out:
            sys.exit("Cần -o FILE_MOI.tex để lưu (file gốc giữ nguyên)")
        text, n = rv.replace_questions_text(text, pairs)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Đã gán ID gợi ý cho {n} câu (độ giống ≥ {a.auto:.0%}), lưu thành {a.out}. Hãy kiểm tra lại!")


def cmd_word2tex(bank, a):
    from .wordconv import import_docx
    tex = import_docx(a.file, a.tag)
    out = a.out or a.file.rsplit(".", 1)[0] + "_tuWord.tex"
    with open(out, "w", encoding="utf-8") as f:
        f.write(tex)
    print(f"Đã nhận dạng {tex.count(chr(92) + 'begin{ex}')} câu → {out}")


def cmd_tex2word(bank, a):
    from .wordconv import export_questions_docx
    out = a.out or a.file.rsplit(".", 1)[0] + ".docx"
    export_questions_docx(parse_file(a.file), out, mark_answers=not a.no_answers, with_solution=not a.no_answers)
    print("Đã ghi", out)


def cmd_pdf(bank, a):
    from .pdfbuild import compile_tex, find_engine
    eng = find_engine(a.engine)
    ok = True
    for f in a.files:
        r = compile_tex(f, eng, runs=a.runs, extest_dir=a.extest or "")
        print(r.summary())
        for e in r.errors[1:6]:
            print("     ", e)
        ok &= r.ok
    if not ok:
        sys.exit(1)


def cmd_ai_id(bank: Bank, a):
    """Gán ID bằng Gemini cho các câu trong file .tex (khoá API lấy từ biến môi trường GEMINI_API_KEY)."""
    import os
    from . import aiid
    from . import review as rv
    key = os.environ.get("GEMINI_API_KEY", "")
    client = aiid.GeminiClient(key, a.model)
    qs = [q for q in parse_file(a.file) if a.all or not q.id_code]
    res = aiid.classify(client, qs, bank.idmap(), scope=a.scope, default_level=a.level, batch=a.batch,
                        progress=lambda i, n: print(f"  {i}/{n} câu…"))
    pairs = []
    for r in res:
        q = qs[r.index]
        stem = " ".join(q.stem.split())[:60]
        print(f"[{r.id_code or '—':<10}] {r.score:4.0%}  {stem}\n             {r.reason}")
        if r.id_code and r.score >= a.min_score:
            old = q.raw
            q.set_id(r.id_code)
            pairs.append((old, q.raw))
    if a.out:
        with open(a.file, encoding="utf-8") as f:
            text, n = rv.replace_questions_text(f.read(), pairs)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"Đã gán ID cho {n} câu (tin cậy ≥ {a.min_score:.0%}) → {a.out}. Hãy kiểm tra lại!")


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
    _add_exam_flags(p)
    p = sub.add_parser("review", help="rà soát đáp án/lời giải/LaTeX của kho hoặc file .tex")
    p.add_argument("files", nargs="*", help="bỏ trống = rà soát cả kho")
    p.add_argument("--only-errors", action="store_true", help="chỉ in câu có lỗi")
    p.add_argument("--remove-errors", action="store_true", help="xoá câu có lỗi (kho) / bỏ khỏi file mới")
    p.add_argument("-o", "--out", help="file mới khi sửa/bỏ câu trong file .tex")
    p.add_argument("--fix", choices=["theo-loi-giai", "theo-dap-an"],
                   help="tự sửa đáp án lệch lời giải (tin lời giải / tin đáp án)")
    p.add_argument("--add-conclusion", action="store_true", help="thêm câu kết luận còn thiếu vào lời giải")
    p = sub.add_parser("suggest-id", help="gợi ý ID cho câu thiếu ID trong file .tex (kho + Map ID)")
    p.add_argument("file")
    p.add_argument("--scope", default="", help="giới hạn phạm vi, vd 0 (lớp 10), 2D")
    p.add_argument("--level", default="N", choices=list("NHVC"), help="mức độ cho câu chưa có ID")
    p.add_argument("--all", action="store_true", help="gợi ý cả câu đã có ID")
    p.add_argument("--auto", type=float, help="tự gán ID gợi ý có độ giống ≥ ngưỡng (0..1)")
    p.add_argument("-o", "--out")
    p = sub.add_parser("word2tex", help="nhận dạng câu hỏi từ file Word (.docx) → .tex (cần pandoc)")
    p.add_argument("file")
    p.add_argument("-o", "--out")
    p.add_argument("--tag", default="", help="nhãn nguồn gắn cho các câu")
    p = sub.add_parser("tex2word", help="file .tex → Word .docx (công thức Word gốc, cần pandoc)")
    p.add_argument("file")
    p.add_argument("-o", "--out")
    p.add_argument("--no-answers", action="store_true", help="không đánh dấu đáp án, không kèm lời giải")
    p = sub.add_parser("pdf", help="biên dịch file .tex ra PDF (pdflatex/xelatex), báo lỗi kèm số dòng")
    p.add_argument("files", nargs="+")
    p.add_argument("--engine", default="auto", choices=["auto", "pdflatex", "xelatex", "lualatex"])
    p.add_argument("--runs", type=int, default=2)
    p.add_argument("--extest", help="thư mục chứa ex_test.sty")
    p = sub.add_parser("ai-id", help="gán ID bằng Gemini (đặt GEMINI_API_KEY; cần Map ID trong kho)")
    p.add_argument("file")
    p.add_argument("-o", "--out", help="file mới đã gán ID (bỏ trống = chỉ in gợi ý)")
    p.add_argument("--scope", default="", help="giới hạn Map ID, vd 0 (lớp 10)")
    p.add_argument("--level", default="N", choices=list("NHVC"))
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--batch", type=int, default=10)
    p.add_argument("--min-score", type=float, default=0.0, help="chỉ gán khi Gemini tin cậy ≥ ngưỡng (0..1)")
    p.add_argument("--all", action="store_true", help="gán lại cả câu đã có ID")
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
    _add_exam_flags(p)

    a = ap.parse_args(argv)
    if a.cmd == "gui":
        try:
            from .gui_qt import run          # giao diện Qt (PySide6)
        except ImportError:
            from .gui import run             # dự phòng: Tkinter
        return run(a.db)
    bank = Bank(a.db or "nganhang.db")
    from .aiid import AIError
    try:
        {"import": cmd_import, "list": cmd_list, "stats": cmd_stats, "check": cmd_check,
         "make": cmd_make, "export": cmd_export, "idmap": cmd_idmap, "shuffle": cmd_shuffle,
         "backup": cmd_backup, "review": cmd_review, "suggest-id": cmd_suggest_id,
         "word2tex": cmd_word2tex, "tex2word": cmd_tex2word, "pdf": cmd_pdf, "ai-id": cmd_ai_id}[a.cmd](bank, a)
    except AIError as e:
        sys.exit(f"Lỗi: {e}")
    finally:
        bank.close()


if __name__ == "__main__":
    main()
