"""PDF → LaTeX ex_test. Ba cách đọc, cùng một bộ tách câu:

* «Chữ trong PDF» (miễn phí, không cần mạng): lấy lớp chữ của file PDF gốc. Công thức thường bị mất hay đổi ký tự,
  hợp với đề ít công thức; bản chụp/scan không có lớp chữ thì không đọc được.
* «Mathpix» (cần app_id/app_key): từng trang được vẽ thành ảnh rồi gửi Mathpix, trả về chữ + công thức LaTeX.
* «AI» (Gemini/Claude): dùng aitasks.pdf_to_latex.

Bộ tách câu nhận 3 phần của đề mới (I trắc nghiệm A–D · II Đúng/Sai a–d · III trả lời ngắn) và tự luận.
"""
from __future__ import annotations

import re
from collections import Counter

from .parser import parse_tex

CAU_RE = re.compile(r"^\s*(?:\*\*)?(?:Câu|CÂU|Bài|BÀI)\s*(\d+)\s*[.:)]?\s*(?:\*\*)?\s*(.*)$")
PHAN_RE = re.compile(r"^\s*(?:PHẦN|Phần)\s*(I{1,3}|IV|1|2|3|4)\b[^\n]*$|^\s*()(?:B\.\s*)?TỰ\s+LUẬN\s*[.:]?\s*$", re.IGNORECASE)
ABCD_RE = re.compile(r"^\s*([A-D])\s*[.)]\s*(.*)$")
ABCD_INLINE = re.compile(r"(?:(?<=\s)|^)([A-D])\s*[.)]\s+")
ABCD_STRICT_INLINE = re.compile(r"(?:(?<=\s)|^)([A-D])\.\s")
ABCD_L_RE = re.compile(r"^\s*([a-d])\s*[.)]\s*(.*)$")
KEY_RE = re.compile(r"(?<!\d)(\d{1,2})\s*[-.:)]?\s*([ABCD])(?![A-Za-zÀ-ỹ])")
PHAN_NAME = {"I": "TN", "1": "TN", "II": "DS", "2": "DS", "III": "KQ", "3": "KQ", "IV": "TL", "4": "TL", "": "TL"}


def extract_text(path: str, *, progress=None) -> str:
    """Lớp chữ của PDF, mỗi trang cách nhau một dòng trống."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    out = []
    try:
        for i in range(len(doc)):
            if progress:
                progress(i, len(doc))
            tp = doc[i].get_textpage()
            out.append(tp.get_text_range().replace("\r\n", "\n").replace("\r", "\n"))
            tp.close()
    finally:
        doc.close()
    return "\n\n".join(out)


def mathpix_text(path: str, app_id: str, app_key: str, *, progress=None, should_stop=None, scale: float = 2.0) -> str:
    """Từng trang → ảnh PNG → Mathpix → chữ có công thức $…$."""
    import io

    import pypdfium2 as pdfium

    from .mathpix import image_to_latex
    doc = pdfium.PdfDocument(path)
    out = []
    try:
        for i in range(len(doc)):
            if should_stop and should_stop():
                break
            if progress:
                progress(i, len(doc))
            img = doc[i].render(scale=scale).to_pil()
            buf = io.BytesIO()
            img.save(buf, "PNG")
            out.append(image_to_latex(f"trang{i + 1}.png", app_id, app_key, data=buf.getvalue()))
    finally:
        doc.close()
    return "\n\n".join(out)


def _clean_lines(text: str) -> list[str]:
    lines = []
    for ln in text.split("\n"):
        ln = ln.replace("\u00a0", " ").replace("\ufeff", "").rstrip()
        lines.append(ln)
    return lines


def parse_answer_key(text: str) -> dict[int, str]:
    """Bảng đáp án trắc nghiệm ở cuối đề: «1. A  2. C …» hoặc «1-A 2-C»; chỉ xét đoạn sau chữ ĐÁP ÁN/BẢNG ĐÁP ÁN."""
    m = None
    for m in re.finditer(r"(?i)(?:bảng\s+)?đáp\s*án", text):
        pass
    if not m:
        return {}
    seg = text[m.end():]
    out: dict[int, str] = {}
    for n, a in KEY_RE.findall(seg):
        out.setdefault(int(n), a)
    return out if len(out) >= 3 else {}


def _split_inline_choices(buf: list[str]) -> list[str]:
    """Phương án nằm chung một dòng «A. … B. … C. … D. …» → tách thành các dòng riêng (chỉ khi đủ A,B,C,D theo thứ tự)."""
    out = []
    for ln in buf:
        marks = [m for m in ABCD_STRICT_INLINE.finditer(ln)]
        letters = [m.group(1) for m in marks]
        if len(marks) >= 2 and letters == list("ABCD")[:len(letters)] and letters[0] == "A":
            start = [0] + [m.start() for m in marks]
            parts = [ln[start[0]:start[1]]] + [ln[start[k]:start[k + 1]] for k in range(1, len(marks))] + [ln[start[-1]:]]
            out.extend(p for p in (x.rstrip() for x in parts if x.strip()))
        else:
            out.append(ln)
    return out


def _wrap(s: str) -> str:
    return " ".join(s.split())


def text_to_ex(text: str, *, tag: str = "") -> tuple[str, list[str]]:
    """Tách văn bản đề thành các khối ex_test. Trả về (nội dung .tex, ghi chú)."""
    key = parse_answer_key(text)
    notes: list[str] = []
    lines = _clean_lines(text)
    blocks: list[tuple[int, str, list[str]]] = []          # (số câu, phần, dòng)
    part, cur = "", None
    for ln in lines:
        mp = PHAN_RE.match(ln)
        if mp:
            part = PHAN_NAME.get((mp.group(1) or mp.group(2) or "").upper(), part)
            cur = None
            continue
        mc = CAU_RE.match(ln)
        if mc:
            cur = (int(mc.group(1)), part, [mc.group(2)])
            blocks.append(cur)
            continue
        if re.match(r"(?i)^\s*(?:bảng\s+)?đáp\s*án", ln):
            cur = None                       # hết đề: phần sau là bảng đáp án
        elif cur is not None:
            cur[2].append(ln)
    out = []
    tag_s = f"%[{tag}]" if tag else ""
    n_tn = n_ds = n_kq = n_tl = 0
    for num, ph, buf in blocks:
        buf = _split_inline_choices([b for b in buf])
        stem, abcd, abcd_l, mode = [], {}, {}, "stem"
        last = None
        for ln in buf:
            ma, ml = ABCD_RE.match(ln), ABCD_L_RE.match(ln)
            if ma and (abcd or ma.group(1) == "A"):
                abcd[ma.group(1)] = [ma.group(2)]
                last, mode = ("A", ma.group(1)), "A"
            elif ml and (abcd_l or ml.group(1) == "a"):
                abcd_l[ml.group(1)] = [ml.group(2)]
                last, mode = ("a", ml.group(1)), "a"
            elif mode == "A" and last:
                abcd[last[1]].append(ln)
            elif mode == "a" and last:
                abcd_l[last[1]].append(ln)
            else:
                stem.append(ln)
        st = _wrap(" ".join(stem))
        if len(abcd) == 4 and ph != "DS":
            ch = [_wrap(" ".join(abcd[k])) for k in "ABCD"]
            ans = key.get(num, "")
            body = "\n".join("\t{" + ("\\True " if ans == k else "") + c + "}" for k, c in zip("ABCD", ch))
            warn = "" if ans else "%[CHƯA CÓ ĐÁP ÁN – đánh dấu \\True vào phương án đúng]"
            out.append(f"\\begin{{ex}}{tag_s}{warn}\n\t{st}\n\t\\choice\n{body}\n\\end{{ex}}")
            n_tn += 1
        elif len(abcd_l) == 4:
            ch = [_wrap(" ".join(abcd_l[k])) for k in "abcd"]
            body = "\n".join("\t{" + c + "}" for c in ch)
            out.append(f"\\begin{{ex}}{tag_s}%[CHƯA CÓ ĐÁP ÁN – đánh dấu \\True vào ý đúng]\n\t{st}\n\t\\choiceTF\n{body}\n\\end{{ex}}")
            n_ds += 1
        elif ph == "KQ":
            out.append(f"\\begin{{ex}}{tag_s}%[CHƯA CÓ ĐÁP ÁN]\n\t{st}\n\t\\shortans{{}}\n\\end{{ex}}")
            n_kq += 1
        else:
            body = _wrap(" ".join(stem + [x for k in "ABCD" for x in abcd.get(k, [])]))
            out.append(f"\\begin{{bt}}{tag_s}\n\t{body}\n\\end{{bt}}")
            n_tl += 1
    if not blocks:
        notes.append("Không thấy dòng «Câu N» nào – kiểm tra file có lớp chữ không (bản chụp/scan cần Mathpix hoặc AI).")
    if key:
        notes.append(f"Đọc được bảng đáp án trắc nghiệm ({len(key)} câu).")
    elif n_tn:
        notes.append("Không thấy bảng đáp án ở cuối file: các câu trắc nghiệm chưa có \\True – điền trước khi nhập kho.")
    notes.append(f"{len(blocks)} câu: {n_tn} trắc nghiệm, {n_ds} Đúng/Sai, {n_kq} trả lời ngắn, {n_tl} tự luận.")
    return "\n\n".join(out) + ("\n" if out else ""), notes


def pdf_to_tex(path: str, engine: str = "text", *, tag: str = "", settings=None, client=None,
               progress=None, should_stop=None) -> tuple[str, list[str]]:
    """engine: 'text' | 'mathpix' | 'ai'. Trả về (.tex, ghi chú)."""
    if engine == "ai":
        from . import aitasks
        props = aitasks.pdf_to_latex(client, path, progress=progress, should_stop=should_stop)
        tex = "\n\n".join(p.question.to_latex(True) for p in props) + "\n"
        return tex, [f"AI đọc được {len(props)} câu (hình vẽ đánh dấu %[HINH: …])."]
    if engine == "mathpix":
        i = str(settings.value("mathpix/app_id", "")) if settings is not None else ""
        k = str(settings.value("mathpix/app_key", "")) if settings is not None else ""
        text = mathpix_text(path, i, k, progress=progress, should_stop=should_stop)
    else:
        text = extract_text(path, progress=progress)
        if len(text.strip()) < 20:
            return "", ["PDF không có lớp chữ (bản chụp/scan) – dùng Mathpix hoặc AI."]
    tex, notes = text_to_ex(text, tag=tag)
    if engine == "text":
        notes.append("Công thức trong PDF thường bị mất hoặc đổi ký tự – hãy soát lại bằng «Soát lỗi» (hoặc dùng Mathpix/AI).")
    return tex, notes


def count_questions(tex: str) -> Counter:
    return Counter(q.qtype for q in parse_tex(tex))
