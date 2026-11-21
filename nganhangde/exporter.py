"""Xuất đề thi, lời giải, bảng đáp án."""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass

from .generator import SECTION_ORDER, SECTION_TITLE, ExamVersion
from .parser import Question

DEFAULT_TEMPLATE = "de_thi.tex"

# Lời dẫn theo mẫu đề thi tốt nghiệp THPT (số câu điền tự động)
OFFICIAL_TITLE = {
    "TN": ("PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn.",
           "Thí sinh trả lời từ câu 1 đến câu {n}. Mỗi câu hỏi thí sinh chỉ chọn một phương án."),
    "DS": ("PHẦN II. Câu trắc nghiệm đúng sai.",
           "Thí sinh trả lời từ câu 1 đến câu {n}. Trong mỗi ý a), b), c), d) ở mỗi câu, thí sinh chọn đúng hoặc sai."),
    "KQ": ("PHẦN III. Câu trắc nghiệm trả lời ngắn.", "Thí sinh trả lời từ câu 1 đến câu {n}."),
    "TL": ("PHẦN IV. Tự luận.", ""),
}
# Thang điểm theo quy chế thi tốt nghiệp THPT từ 2025 (môn Toán)
SCORING = {"TN": 0.25, "KQ": 0.5, "DS": {1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}}


@dataclass
class ExportOptions:
    """Tuỳ chọn khi xuất đề."""
    renumber: bool = False            # đánh số lại từ Câu 1 ở mỗi phần (\setcounter{ex}{0})
    official_titles: bool = False     # tiêu đề + lời dẫn theo mẫu đề thi tốt nghiệp
    scoring: bool = False             # in thang điểm trong file lời giải
    answers_xlsx: bool = True         # đáp án Excel (dùng cho TNMaker / phần mềm chấm)
    tnmaker_layout: str = "mylt"       # 'doc': mỗi dòng một câu, mỗi cột một mã đề; 'ngang': mỗi dòng một mã đề
    ds_style: str = "gop"             # 'gop': 1 ô «ĐSĐS» / câu; 'tach': 4 ô a,b,c,d
    ds_symbols: str = "ĐS"            # 'ĐS' | 'TF' | '10'
    kq_decimal: str = ","             # dấu thập phân phần trả lời ngắn
    show_id: bool = False             # in ID nhỏ sau mỗi câu trong file lời giải (bản cho giáo viên)
    make_zip: bool = False            # nén cả thư mục kết quả thành .zip
    header: dict | None = None        # thông tin đầu đề: SO_GD, KY_THI, MON_THI, GIAO_VIEN, NAM_HOC
    online_html: bool = False         # mỗi mã đề một file HTML làm bài online (chấm điểm ngay)
    online_solution: bool = True      # bài online: hiện lời giải sau khi nộp
    moodle: bool = False              # file Moodle XML (bộ câu của đề)
    word: bool = False                # file Word .docx mỗi mã đề (cần pandoc)
    diem: dict | None = None          # thang điểm tuỳ chỉnh (xem scoring.Scoring.from_dict)
    omr_profile: str = "tnmaker"      # mẫu file đáp án phần mềm chấm: tnmaker | ngang | mau (theo file mẫu)
    omr_template: str = ""            # file .xlsx mẫu đáp án của phần mềm chấm (khi omr_profile = 'mau')
    ans_toggle: bool = False          # đưa bảng đáp án vào \ifshowans … \fi (tắt/bật bằng \showansfalse / \showanstrue)
    qr_answers: bool = False          # in mã QR chứa đáp án trong file lời giải
    qr_format: str = "gon"            # gon | md | json – kiểu chuỗi trong mã QR
    omr_capacity: str = "bgd2025"     # mẫu phiếu để kiểm tra sức chứa (omr.PROFILES)
    gas: bool = False                 # file Apps Script (.gs) tạo Google Form cho mỗi mã đề
    gas_images: bool = False          # Google Form dạng ảnh: mỗi câu thành ảnh PNG (cần LaTeX) + file .gs
    online_style: dict | None = None  # màu bài online / Blogger (online.version_html)
    gform: dict | None = None         # Google Form nhận kết quả bài online
    per_folder: bool = False          # mỗi mã đề một thư mục con (de_101.tex, loigiai_101.tex… trong thư mục 101)
    answers_end: bool = False         # in bảng đáp án ở cuối chính file đề
    even_pages: bool = False          # chèn trang trống để mỗi đề có số trang chẵn (in 2 mặt không dính đề sau)
    answer_sheet: bool = False        # file phiếu trả lời: phiếu trắng + phiếu tô sẵn đáp án từng mã (phiếu khoá)
    slides: bool = False              # trình chiếu HTML (mã đề đầu tiên, mỗi câu một trang)

    def scoring_obj(self):
        from .scoring import Scoring
        return Scoring.from_dict(self.diem)


def plain_answer(a: str) -> str:
    """Bỏ kí hiệu LaTeX khỏi đáp án trả lời ngắn: '$0{,}92$' → '0,92', '$-4$' → '-4'."""
    a = a.replace("{,}", ",").replace("\\dfrac", "").replace("\\frac", "")
    return a.replace("$", "").replace("{", "").replace("}", "").strip()


def load_template(path: str | None = None) -> str:
    """Mẫu đề: file chỉ định → mau_de\\de_thi.tex trong thư mục phần mềm (giáo viên sửa được) → mẫu đi kèm."""
    if not path and os.environ.get("NHD_USE_APP_TEMPLATE", "1") == "1":
        try:
            from .appdirs import path as app_path
            cand = app_path("mau_de", "de_thi.tex")
            if os.path.isfile(cand):
                path = cand
        except OSError:
            pass
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read()
    default = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", DEFAULT_TEMPLATE)
    with open(default, encoding="utf-8") as f:
        return f.read()


def questions_to_tex(qs: list[Question], with_solution: bool = True, show_id: bool = False) -> str:
    out = []
    for q in qs:
        t = q.to_latex(with_solution)
        if show_id and q.id_code:
            t = t.replace("\\end{" + q.env + "}", "\\hfill{\\scriptsize[" + q.id_code + "]}\n\\end{" + q.env + "}", 1)
        out.append(t)
    return "\n".join(out) + "\n"


def section_heading(s: str, n: int, opt: "ExportOptions | None") -> str:
    if opt and opt.official_titles:
        head, lead = OFFICIAL_TITLE[s]
        lead = lead.format(n=n)
        return f"\\noindent\\textbf{{{head}}} {lead}\\par\\smallskip"
    return f"\\section*{{{SECTION_TITLE[s]}}}"


def version_body(v: ExamVersion, with_solution: bool, opt: "ExportOptions | None" = None, heading=None) -> str:
    parts = []
    for s in SECTION_ORDER:
        qs = v.sections.get(s) or []
        if not qs:
            continue
        parts.append(heading(s, len(qs)) if heading else section_heading(s, len(qs), opt))
        if opt and opt.renumber:
            parts.append("\\setcounter{ex}{0}")
        parts.append(questions_to_tex(qs, with_solution, bool(opt and opt.show_id and with_solution)))
    return "\n".join(parts)


def scoring_tex(v: ExamVersion, sc=None) -> str:
    from .scoring import DEFAULT
    n = {s: len(v.sections.get(s) or []) for s in SECTION_ORDER}
    return "\\section*{Thang điểm}\n" + "\\\\\n".join((sc or DEFAULT).lines(n)) + "\n"


def score_ds(n_correct: int, sc=None) -> float:
    from .scoring import DEFAULT
    return (sc or DEFAULT).ds_score(n_correct)


# ---------------------------------------------------------------- file header kiểu MyLT
HEADER_TITLE_MACROS = {"tentruong": "TRUONG", "tengv": "GIAO_VIEN", "tenkythi": "KY_THI", "tenmonthi": "MON_THI",
                       "thoigian": "THOI_GIAN"}
HEADER_PART = {"TN": ("tieudea", "I"), "DS": ("tieudeb", "II"), "KQ": ("tieudec", "III"), "TL": ("tieuded", "IV")}


def is_header(template: str) -> bool:
    """File header kiểu MyLT: phần khai báo (gói, lệnh \\tieude, \\tentruong…) kết thúc bằng \\begin{document},
    không có chỗ trống <<NOI_DUNG>>."""
    return "<<NOI_DUNG>>" not in template and "\\begin{document}" in template


def _defines(tpl: str, name: str) -> bool:
    import re as _re
    return bool(_re.search(r"\\(newcommand|renewcommand|def)\*?\s*\{?\\" + name + r"\b", tpl))


def fill_header(tpl: str, v: ExamVersion, mode: str, with_solution: bool, opt: "ExportOptions | None",
                values: dict) -> str:
    """Dựng file đề từ header: đặt tuỳ chọn ex_test (dethi/loigiai), thay tên trường/kì thi… theo thông tin đề,
    gọi \\tieude{số trang}{số câu}{mã đề}, \\chantrang, tiêu đề từng phần \\tieudea…\\tieuded nếu header có."""
    import re as _re
    head, _, _rest = tpl.partition("\\begin{document}")
    if _re.search(r"\\usepackage(\[[^\]]*\])?\{ex_test\}", head):
        head = _re.sub(r"\\usepackage(\[[^\]]*\])?\{ex_test\}",
                       lambda m: "\\usepackage[" + ",".join([o for o in (m.group(1) or "[]")[1:-1].split(",")
                                                            if o.strip() and o.strip() not in ("dethi", "loigiai")]
                                                           + [mode]) + "]{ex_test}", head, count=1)
    for macro, key in HEADER_TITLE_MACROS.items():
        val = str(values.get(key, "") or "").strip()
        if val and _defines(head, macro):
            head = _re.sub(r"(\\newcommand\s*\{\\" + macro + r"\}\s*)\{[^{}]*\}",
                           lambda m: m.group(1) + "{" + val.replace("\\", r"\\") + "}", head, count=1)
    if "lastpage" not in head:
        head += "\\usepackage{lastpage}\n"
    head += ("\\providecommand{\\heva}[1]{\\left\\{\\begin{aligned}#1\\end{aligned}\\right.}\n"
             "\\providecommand{\\hoac}[1]{\\left[\\begin{aligned}#1\\end{aligned}\\right.}\n")
    n = sum(len(v.sections.get(s) or []) for s in SECTION_ORDER)
    top = []
    if _defines(head, "tieude"):
        top.append(f"\\tieude{{\\pageref{{LastPage}}}}{{{n}}}{{{v.code}}}")
    if _defines(head, "chantrang"):
        top.append(f"\\chantrang{{\\pageref{{LastPage}}}}{{{v.code}}}")

    def heading(s, k):
        macro, roman = HEADER_PART[s]
        if _defines(head, macro):
            return (f"\\{macro}{{{roman}}}{{{k}}}" if s != "TL" else f"\\{macro}{{{roman}}}") + "\\par\\smallskip"
        return section_heading(s, k, opt)
    body = version_body(v, with_solution, opt, heading)
    end = "\n\\hetde\n" if _defines(head, "hetde") else "\n\\begin{center}--- HẾT ---\\end{center}\n"
    return head + "\\begin{document}\n" + "\n".join(top) + "\n" + body + end + "\\end{document}\n"


def fill(template: str, **kw) -> str:
    import re as _re
    for k, val in kw.items():
        template = template.replace(f"<<{k}>>", str(val))
    return _re.sub(r"<<[A-Z_]+>>", "", template)       # chỗ trống không có thông tin ⇒ để trống


def answer_table_tex(v: ExamVersion) -> str:
    rows = []
    for s in SECTION_ORDER:
        key = [(i, q.answer_text) for i, q in enumerate(v.sections.get(s) or [], 1)]
        if not key or s == "TL":
            continue
        rows.append(f"\\noindent\\textbf{{{SECTION_TITLE[s]}}}\\\\")
        rows.append("\\begin{tabular}{|" + "c|" * len(key) + "}\\hline")
        rows.append(" & ".join(str(i) for i, _ in key) + "\\\\\\hline")
        rows.append(" & ".join(a for _, a in key) + "\\\\\\hline")
        rows.append("\\end{tabular}\\par\\medskip")
    return "\n".join(rows)


def toggle_wrap(tex: str) -> str:
    """Gói phần đáp án vào môi trường bật/tắt bằng một lệnh: đổi \\showanstrue ↔ \\showansfalse ở đầu."""
    return ("\\newif\\ifshowans\\showanstrue % đổi thành \\showansfalse để ẨN toàn bộ đáp án\n"
            "\\ifshowans\n" + tex + "\n\\fi")


def export_versions(versions: list[ExamVersion], out_dir: str, *, template_path: str | None = None,
                    ten_de: str = "ĐỀ KIỂM TRA", truong: str = "", thoi_gian: int = 90,
                    options: ExportOptions | None = None) -> list[str]:
    opt = options or ExportOptions()
    os.makedirs(out_dir, exist_ok=True)
    tpl = load_template(template_path)
    files = []
    for v in versions:
        common = dict(TEN_DE=ten_de, TRUONG=truong, THOI_GIAN=thoi_gian, MA_DE=v.code, **(opt.header or {}))
        vdir = os.path.join(out_dir, v.code) if opt.per_folder else out_dir
        os.makedirs(vdir, exist_ok=True)
        for mode, prefix, sol in (("dethi", "de", False), ("loigiai", "loigiai", True)):
            if is_header(tpl):
                text = fill_header(tpl, v, mode, sol, opt, common)
                if sol:
                    ans = ("\\section*{Bảng đáp án}\n" + answer_table_tex(v)
                           + ("\n" + scoring_tex(v, opt.scoring_obj()) if opt.scoring else ""))
                    text = text.replace("\\end{document}", (toggle_wrap(ans) if opt.ans_toggle else ans)
                                        + "\n\\end{document}", 1)
                path = os.path.join(vdir, f"{prefix}_{v.code}.tex")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                files.append(path)
                continue
            body = version_body(v, sol, opt)
            if not sol and opt.answers_end:
                tail = "\\section*{Đáp án}\n" + answer_table_tex(v)
                body += "\n\\newpage\n" + (toggle_wrap(tail) if opt.ans_toggle else tail)
            if not sol and opt.even_pages:
                body += "\n\\clearpage\\ifodd\\value{page}\\else\\hbox{}\\thispagestyle{empty}\\newpage\\fi\n"
            if sol:
                tail = "\\section*{Bảng đáp án}\n" + answer_table_tex(v)
                if opt.qr_answers:
                    from .omr import qr_tex
                    tail += "\n" + qr_tex(v, opt.qr_format)
                if opt.scoring:
                    tail += "\n" + scoring_tex(v, opt.scoring_obj())
                body += "\n" + (toggle_wrap(tail) if opt.ans_toggle else tail)
            path = os.path.join(vdir, f"{prefix}_{v.code}.tex")
            text = fill(tpl, MODE=mode, NOI_DUNG=body, **common)
            if "\\qrcode" in body and "{qrcode}" not in text:
                text = text.replace("\\begin{document}", "\\usepackage{qrcode}\n\\begin{document}", 1)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            files.append(path)
    csv_path = os.path.join(out_dir, "dap_an.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Mã đề", "Phần", "Câu", "Đáp án", "ID gốc"])
        for v in versions:
            for s in SECTION_ORDER:
                for i, q in enumerate(v.sections.get(s) or [], 1):
                    w.writerow([v.code, s, i, plain_answer(q.answer_text), q.id_code])
    files.append(csv_path)
    # bảng đáp án dạng ngang (mỗi mã đề một dòng) – tiện dán vào phần mềm chấm thi/Excel
    wide_path = os.path.join(out_dir, "dap_an_bang.csv")
    with open(wide_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        cols = [(s, i) for s in SECTION_ORDER if s != "TL"
                for i in range(1, max((len(v.sections.get(s) or []) for v in versions), default=0) + 1)]
        w.writerow(["Mã đề"] + [f"{s}{i}" for s, i in cols])
        for v in versions:
            row = [v.code]
            for s, i in cols:
                qs = v.sections.get(s) or []
                row.append(plain_answer(qs[i - 1].answer_text) if i <= len(qs) else "")
            w.writerow(row)
    files.append(wide_path)
    if opt.answers_xlsx:
        from .tnmaker import write_answer_xlsx
        try:
            if opt.omr_profile == "mau" and opt.omr_template:
                from .omr import fill_template
                files.append(fill_template(versions, opt.omr_template,
                                           os.path.join(out_dir, "dap_an_phieu_cham.xlsx"), opt))
            else:
                files.append(write_answer_xlsx(versions, os.path.join(out_dir, "dap_an_TNMaker.xlsx"), opt))
        except ImportError:
            pass        # thiếu openpyxl: vẫn có 2 file CSV
    if opt.online_html:
        from .online import export_html
        files += export_html(versions, out_dir, ten_de=ten_de, thoi_gian=int(thoi_gian),
                             show_solution=opt.online_solution, scoring=opt.scoring_obj(),
                             style=opt.online_style, gform=opt.gform)
    if opt.moodle and versions:
        from .online import export_moodle
        files.append(export_moodle(list(versions[0].all_questions()), os.path.join(out_dir, "moodle.xml"),
                                   category=ten_de, scoring=opt.scoring_obj(),
                                   base_dir=os.path.dirname(os.path.abspath(template_path)) if template_path
                                   else out_dir))
    if opt.gas_images and versions:
        from .gas import export_gas_images
        try:
            files += export_gas_images(versions, out_dir, ten_de=ten_de, scoring=opt.scoring_obj())
        except (RuntimeError, ImportError) as e:
            p = os.path.join(out_dir, "LOI_google_form_anh.txt")
            with open(p, "w", encoding="utf-8") as f:
                f.write(str(e) + "\n")
            files.append(p)
    if opt.answer_sheet and versions:
        from .omr import sheet_document
        for name, vs_ in (("phieu_tra_loi_trang.tex", None), ("phieu_dap_an_to_san.tex", versions)):
            p = os.path.join(out_dir, name)
            with open(p, "w", encoding="utf-8") as f:
                f.write(sheet_document(vs_, {s: len(versions[0].sections.get(s) or [])
                                             for s in ("TN", "DS", "KQ")} if vs_ is None else None))
            files.append(p)
    if opt.gas:
        from .gas import export_gas
        files += export_gas(versions, out_dir, ten_de=ten_de, scoring=opt.scoring_obj())
    if opt.slides and versions:
        from .slides import export_slides
        files.append(export_slides(list(versions[0].all_questions()), os.path.join(out_dir, "trinh_chieu.html"),
                                   f"{ten_de} – mã {versions[0].code}"))
    if opt.word:
        from .wordconv import export_docx, PandocMissing
        for v in versions:
            try:
                files.append(export_docx(v, os.path.join(out_dir, f"de_{v.code}.docx"), ten_de=ten_de,
                                         thoi_gian=thoi_gian, header=opt.header or {}, truong=truong))
            except PandocMissing:
                break
    if opt.make_zip:
        from .tools import zip_dir
        files.append(zip_dir(out_dir))
    return files


def matrix_spec(bank, rules, path: str) -> str:
    """In ma trận đặc tả: mỗi dòng ma trận kèm tên chương/bài/dạng, mức độ, số câu, số câu kho có.

    Đuôi .xlsx ⇒ Excel; còn lại ⇒ bảng LaTeX.
    """
    from .idmap import split_key
    names = bank.idmap()
    level = {"N": "Nhận biết", "H": "Thông hiểu", "V": "Vận dụng", "C": "Vận dụng cao", None: "Mọi mức"}
    part = {"TN": "I. Trắc nghiệm", "DS": "II. Đúng/Sai", "KQ": "III. Trả lời ngắn", "TL": "IV. Tự luận"}
    rows = []
    for r in rules:
        pat = r.id.upper()
        base = pat.split("*")[0].split("?")[0].split("[")[0]
        key = base[:3] + (base[4:] if len(base) > 4 else "")
        label = " › ".join(names[k] for k in ("".join(split_key(key)[:n]) for n in (3, 4))
                           if k in names) if len(base) >= 3 else ""
        if "-" in key and key in names:
            label += " › " + names[key]
        have = len(bank.search(qtype=r.qtype, id_like=r.id, muc_do=r.muc_do, text=r.text))
        rows.append([part[r.qtype], r.id, label or "—", level.get(r.muc_do, r.muc_do), r.count, have])
    total = sum(x[4] for x in rows)
    if path.lower().endswith(".xlsx"):
        from openpyxl import Workbook
        from openpyxl.styles import Font
        wb = Workbook()
        ws = wb.active
        ws.title = "Ma trận đặc tả"
        ws.append(["Phần", "Mẫu ID", "Nội dung (chương › bài › dạng)", "Mức độ", "Số câu", "Kho có"])
        for c in ws[1]:
            c.font = Font(bold=True)
        for x in rows:
            ws.append(x)
        ws.append(["Tổng", "", "", "", total, ""])
        for col, wd in zip("ABCDEF", (18, 14, 70, 14, 8, 8)):
            ws.column_dimensions[col].width = wd
        wb.save(path)
    else:
        body = "\n".join(" & ".join(str(c).replace("&", "\\&").replace("_", "\\_") for c in x) + "\\\\ \\hline"
                         for x in rows)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\\begin{center}\\textbf{MA TRẬN ĐẶC TẢ}\\end{center}\n"
                    "\\begin{tabular}{|l|l|p{7cm}|l|c|c|}\\hline\n"
                    "Phần & Mẫu ID & Nội dung & Mức độ & Số câu & Kho có\\\\ \\hline\n" + body +
                    f"\n\\multicolumn{{4}}{{|r|}}{{Tổng}} & {total} & \\\\ \\hline\n\\end{{tabular}}\n")
    return path


def export_questions(qs: list[Question], path: str, with_solution: bool = True):
    """Xuất các câu đã chọn ra 1 file .tex (giữ nguyên định dạng ex)."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(questions_to_tex(qs, with_solution))
