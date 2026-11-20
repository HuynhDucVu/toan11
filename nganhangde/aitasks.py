"""Các việc giao cho AI (dùng được với mọi nhà cung cấp trong ai.py).

* similar      – sinh câu tương tự một câu mẫu (giữ dạng câu, ID, mức độ);
* fill_gaps    – bù câu còn thiếu cho từng dòng ma trận;
* pdf_to_latex – chuyển đề PDF (kể cả bản chụp) sang LaTeX ex_test, cắt mỗi lần 10 trang;
* grade_essay  – chấm bài tự luận theo đáp án/barem;
* diagnose_log – đọc lỗi biên dịch LaTeX, chỉ nguyên nhân và cách sửa.

Câu do AI sinh luôn được **rà soát** (review.py) và trả về để giáo viên duyệt, không tự đưa vào kho.
AI có thể giải sai: giáo viên cần kiểm tra lời giải trước khi dùng.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .aiid import AIError
from .parser import Question, parse_tex

FORMAT_GUIDE = r"""Định dạng ex_test bắt buộc (mỗi câu một khối):
- Trắc nghiệm 4 phương án:
\begin{ex}%[ID]
Đề bài...
\choice
{phương án A}
{\True phương án đúng}
{phương án C}
{phương án D}
\loigiai{Lời giải chi tiết... Chọn đáp án B.}
\end{ex}
- Đúng/Sai: \choiceTF với 4 ý, đánh \True trước ý đúng; trong \loigiai dùng \begin{itemchoice} \itemch Đúng. ... \itemch Sai. ... \end{itemchoice}
- Trả lời ngắn: \shortans[oly]{đáp án} – đáp án là số, tối đa 4 kí tự, dùng dấu phẩy thập phân, ví dụ \shortans[oly]{$0{,}5$}
- Tự luận: \begin{bt}%[ID] ... \loigiai{...}\end{bt}
Công thức toán đặt trong $...$. Không dùng gói lệnh lạ, không vẽ hình bằng ảnh (được dùng TikZ)."""

LATEX_LIST_SCHEMA = {
    "type": "object",
    "properties": {"cau_hoi": {"type": "array", "items": {"type": "string"}}},
    "required": ["cau_hoi"], "additionalProperties": False,
}
TYPE_NAME = {"TN": "trắc nghiệm 4 phương án (\\choice)", "DS": "Đúng/Sai 4 ý (\\choiceTF)",
             "KQ": "trả lời ngắn (\\shortans)", "TL": "tự luận (môi trường bt)"}


@dataclass
class Proposal:
    question: Question
    issues: list = field(default_factory=list)
    source: str = ""          # câu mẫu / dòng ma trận / trang PDF

    @property
    def ok(self) -> bool:
        from .review import LOI
        return not any(i.level == LOI for i in self.issues)


def _parse_list(items: list[str], id_code: str = "", source: str = "") -> list[Proposal]:
    from .review import review_question
    out = []
    for latex in items:
        for q in parse_tex(str(latex)):
            if id_code and not q.id_code:
                q.id_code = id_code
            if "AI" not in q.tags:
                q.tags.append("AI")
            out.append(Proposal(q, review_question(q), source))
    return out


def similar(client, q: Question, n: int = 3, harder: bool = False) -> list[Proposal]:
    prompt = (f"Bạn là giáo viên Toán THPT Việt Nam. Hãy soạn {n} câu hỏi MỚI tương tự câu mẫu dưới đây: "
              f"cùng dạng {TYPE_NAME.get(q.qtype, q.qtype)}, cùng kiến thức, "
              f"{'khó hơn một mức' if harder else 'cùng mức độ'}, đổi số liệu/ngữ cảnh, đáp án phải đúng và "
              "có lời giải chi tiết. Không lặp lại câu mẫu.\n\n" + FORMAT_GUIDE +
              "\n\nCÂU MẪU:\n" + q.to_latex(True) +
              '\n\nTrả về JSON: {"cau_hoi": ["<khối LaTeX câu 1>", ...]}')
    data = client.generate_json(prompt, LATEX_LIST_SCHEMA)
    return _parse_list(data.get("cau_hoi", [])[:n], q.id_code, f"tương tự câu #{q.db_id or ''}")


def from_description(client, qtype: str, id_code: str, description: str, n: int, level: str = "") -> list[Proposal]:
    lv = {"N": "nhận biết", "H": "thông hiểu", "V": "vận dụng", "C": "vận dụng cao"}.get(level, "")
    prompt = (f"Bạn là giáo viên Toán THPT Việt Nam (chương trình GDPT 2018). Soạn {n} câu {TYPE_NAME[qtype]} "
              f"về nội dung: «{description}»{', mức độ ' + lv if lv else ''}. Đáp án đúng, lời giải chi tiết, "
              "các câu khác nhau.\n\n" + FORMAT_GUIDE + '\n\nTrả về JSON: {"cau_hoi": ["<khối LaTeX>", ...]}')
    data = client.generate_json(prompt, LATEX_LIST_SCHEMA)
    return _parse_list(data.get("cau_hoi", [])[:n], id_code, f"theo mô tả: {description}")


def gaps(bank, rules) -> list[tuple[int, int]]:
    """[(chỉ số dòng ma trận, số câu còn thiếu)]."""
    out = []
    for i, r in enumerate(rules):
        have = len(bank.search(qtype=r.qtype, id_like=r.id, muc_do=r.muc_do, text=r.text))
        if have < r.count:
            out.append((i, r.count - have))
    return out


def fill_gaps(client, bank, rules, *, progress=None, should_stop=None) -> list[Proposal]:
    """Sinh đủ số câu còn thiếu cho mỗi dòng ma trận (dựa vào câu có sẵn, hoặc tên dạng trong Map ID)."""
    names = bank.idmap()
    out: list[Proposal] = []
    todo = gaps(bank, rules)
    for k, (i, need) in enumerate(todo):
        if should_stop and should_stop():
            break
        if progress:
            progress(k, len(todo))
        r = rules[i]
        pool = bank.search(qtype=r.qtype, id_like=r.id, text=r.text) or bank.search(qtype=r.qtype, id_like=r.id)
        got: list[Proposal] = []
        if pool:
            j = 0
            while len(got) < need and j < need + 3:
                seed = pool[j % len(pool)]
                got += similar(client, seed, min(3, need - len(got)))
                j += 1
        else:
            base = r.id.split("*")[0].split("?")[0].upper()
            key = base[:3] + (base[4:] if len(base) > 4 else "")
            desc = names.get(key) or names.get(key.split("-")[0]) or names.get(base[:3]) or ""
            if not desc:
                raise AIError(f"Dòng {i + 1} ({r.qtype} {r.id}): kho chưa có câu nào và Map ID không có tên dạng – "
                              "không đủ thông tin để AI soạn câu")
            lv = r.muc_do or (base[3] if len(base) > 3 else "")
            full = base if len(base) >= 4 and "-" in base else ""
            got = from_description(client, r.qtype, full, desc, need, lv)
        for p in got[:need]:
            p.source = f"dòng {i + 1} ma trận ({r.qtype} {r.id}): " + p.source
            out.append(p)
    if progress:
        progress(len(todo), len(todo))
    return out


def pdf_chunks(path: str, pages: int = 10) -> list[tuple[str, bytes]]:
    """Cắt PDF thành các phần ≤ `pages` trang (cần pypdf)."""
    import io
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        raise AIError("Thiếu thư viện pypdf – chạy: pip install pypdf") from None
    rd = PdfReader(path)
    n = len(rd.pages)
    out = []
    for a in range(0, n, pages):
        w = PdfWriter()
        for i in range(a, min(n, a + pages)):
            w.add_page(rd.pages[i])
        buf = io.BytesIO()
        w.write(buf)
        out.append((f"trang {a + 1}–{min(n, a + pages)}", buf.getvalue()))
    return out


PDF_PROMPT = ("Đây là một phần đề thi/tài liệu Toán (có thể là bản chụp). Hãy chép lại TẤT CẢ câu hỏi trong các trang "
              "này sang LaTeX đúng định dạng dưới đây, giữ nguyên nội dung, công thức, phương án. Nếu tài liệu có đáp án "
              "hoặc lời giải thì điền vào (\\True, \\shortans, \\loigiai); nếu không có thì để \\loigiai{} trống, "
              "KHÔNG tự bịa đáp án. Hình vẽ: thay bằng chú thích %[HINH: mô tả ngắn]. Câu bị cắt ngang ở mép trang "
              "cuối thì bỏ qua (sẽ có ở phần sau).\n\n" + FORMAT_GUIDE +
              '\n\nTrả về JSON: {"cau_hoi": ["<khối LaTeX câu 1>", ...]}')


def pdf_to_latex(client, path: str, pages: int = 10, *, progress=None, should_stop=None) -> list[Proposal]:
    chunks = pdf_chunks(path, pages)
    out: list[Proposal] = []
    for k, (label, data) in enumerate(chunks):
        if should_stop and should_stop():
            break
        if progress:
            progress(k, len(chunks))
        res = client.generate_from_pdf(data, PDF_PROMPT, LATEX_LIST_SCHEMA)
        for p in _parse_list(res.get("cau_hoi", []), source=label):
            p.question.tags = [t for t in p.question.tags if t != "AI"] + ["PDF"]
            out.append(p)
    if progress:
        progress(len(chunks), len(chunks))
    return out


GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "diem": {"type": "number"},
        "nhan_xet": {"type": "string"},
        "chi_tiet": {"type": "array", "items": {
            "type": "object",
            "properties": {"y": {"type": "string"}, "diem": {"type": "number"}, "ghi_chu": {"type": "string"}},
            "required": ["y", "diem", "ghi_chu"], "additionalProperties": False}},
    },
    "required": ["diem", "nhan_xet", "chi_tiet"], "additionalProperties": False,
}


def grade_essay(client, question_latex: str, rubric: str, max_points: float, *, answer_text: str = "",
                answer_pdf: bytes | None = None) -> dict:
    """Chấm gợi ý một bài tự luận. Giáo viên quyết định điểm cuối cùng."""
    prompt = (f"Bạn là giáo viên Toán chấm bài tự luận, thang điểm tối đa {max_points:g}. Chấm theo đáp án/barem, "
              "cho điểm từng ý, chấp nhận cách giải khác nếu đúng, trừ điểm khi thiếu lập luận. "
              "Điểm làm tròn 0,25.\n\nĐỀ BÀI:\n" + question_latex + "\n\nĐÁP ÁN – BAREM:\n" + (rubric or "(không có)") +
              ("\n\nBÀI LÀM CỦA HỌC SINH:\n" + answer_text if answer_text else
               "\n\nBài làm của học sinh nằm trong tệp PDF đính kèm.") +
              '\n\nTrả về JSON: {"diem": số, "nhan_xet": "...", "chi_tiet": [{"y": "ý 1", "diem": số, "ghi_chu": "..."}]}')
    data = client.generate_from_pdf(answer_pdf, prompt, GRADE_SCHEMA) if answer_pdf else \
        client.generate_json(prompt, GRADE_SCHEMA)
    try:
        d = float(data.get("diem", 0))
    except (TypeError, ValueError):
        d = 0.0
    data["diem"] = max(0.0, min(max_points, round(d * 4) / 4))
    return data


DIAG_SCHEMA = {
    "type": "object",
    "properties": {"nguyen_nhan": {"type": "string"}, "cach_sua": {"type": "string"},
                   "dong": {"type": "integer"}, "sua_thanh": {"type": "string"}},
    "required": ["nguyen_nhan", "cach_sua", "dong", "sua_thanh"], "additionalProperties": False,
}


def diagnose_log(client, errors: list[str], tex_path: str, context: int = 6) -> dict:
    """Đưa AI các lỗi biên dịch + đoạn mã quanh dòng lỗi đầu tiên; trả lời bằng tiếng Việt."""
    import re
    try:
        with open(tex_path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError:
        lines = []
    m = next((re.search(r"(\d+)", e) for e in errors if re.search(r"[Dd]òng\s*\d+|l\.\d+", e)), None)
    ln = int(m.group(1)) if m else 0
    lo, hi = max(1, ln - context), min(len(lines), ln + context) if ln else min(len(lines), 40)
    snippet = "\n".join(f"{i:5d}| {lines[i - 1]}" for i in range(lo, hi + 1)) if lines else "(không đọc được file)"
    prompt = ("Bạn là chuyên gia LaTeX. File .tex (đề thi Toán dùng gói ex_test, có thể dùng TikZ) biên dịch lỗi. "
              "Giải thích ngắn gọn bằng tiếng Việt nguyên nhân và cách sửa cụ thể. Nếu sửa được bằng cách thay một "
              "dòng thì cho số dòng và nội dung dòng mới (sua_thanh), nếu không thì dong = 0 và sua_thanh rỗng.\n\n"
              "LỖI:\n" + "\n".join(errors[:8]) + "\n\nĐOẠN MÃ:\n" + snippet)
    return client.generate_json(prompt, DIAG_SCHEMA)
