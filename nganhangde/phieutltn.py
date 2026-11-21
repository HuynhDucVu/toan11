"""Phiếu trả lời trắc nghiệm THPT QG 2025 (mẫu của Bộ GD&ĐT: 40 câu nhiều lựa chọn · 8 câu Đúng/Sai · 6 câu trả lời ngắn).

Dùng đúng file phiếu gốc (PDF, DATA\\Phiếu TLTN THPT QG 2025 (1 mặt).pdf) và vẽ thêm các ô tròn đen lên đúng vị trí:
  * phiếu khoá: tô sẵn đáp án từng mã đề (để in đối chiếu / thử bằng phần mềm chấm);
  * có thể tô mã đề (3 chữ số) và số báo danh (6 chữ số).
Toạ độ các ô đo từ chính file phiếu (trang A4 595,3 × 841,8 pt, gốc ở góc trên trái, đơn vị pt).
"""
from __future__ import annotations

import os

PAGE_H = 841.824
RADIUS = 4.3                      # bán kính ô tô (ô in có đường kính ≈ 10 pt)
K = 1.3                           # toạ độ đo ở ảnh tỉ lệ 1,3 (px) → pt


def _pt(v: float) -> float:
    return v / K


# ---- Phần I: 4 khối × 10 câu × 4 cột (A–D)
P1_X = [[83.9, 108.5, 133.0, 157.0], [206.0, 230.6, 255.0, 279.5], [328.5, 353.0, 377.5, 401.5],
        [451.0, 475.5, 500.0, 524.0]]
P1_Y = [322.0 + 12.5 * i for i in range(10)]
# ---- Phần II: 4 khối × 2 câu × (Đúng, Sai) × 4 ý a–d
P2_Y = [504.5, 517.0, 530.0, 542.5]
# ---- Phần III: 6 câu, mỗi câu 4 cột; hàng: dấu «−», dấu «,», rồi chữ số 0–9
P3_X = [[80.0, 96.5, 113.5, 130.5], [158.0, 174.9, 191.5, 208.5], [236.0, 253.0, 270.0, 287.0],
        [314.5, 332.0, 349.0, 365.5], [393.5, 410.0, 427.0, 444.0], [471.5, 488.0, 505.0, 522.0]]
P3_MINUS_Y = _pt(802.1)
P3_COMMA_Y = _pt(818.4)
P3_DIGIT_Y = [_pt(v) for v in (836.6, 852.8, 870.4, 887.2, 903.8, 920.4, 937.3, 953.6, 971.1, 988.0)]
# ---- Số báo danh (6 cột) và mã đề (3 cột): 10 hàng chữ số 0–9
SBD_X = [_pt(v) for v in (568, 583, 597, 612, 627, 642)]
MADE_X = [_pt(v) for v in (678, 693, 707)]
DIGIT_ROWS_Y = [_pt(v) for v in (122.2, 143.6, 164.5, 185.9, 207.4, 228.2, 249.6, 271.0, 291.8, 313.3)]


def template_path() -> str:
    """File phiếu gốc: DATA\\Phiếu TLTN THPT QG 2025 (1 mặt).pdf trong thư mục phần mềm, không có thì bản đi kèm."""
    from .appdirs import PHIEU_PDF, PKG, home
    cand = os.path.join(home(), "DATA", PHIEU_PDF.replace("_", " "))
    return cand if os.path.isfile(cand) else os.path.join(PKG, "data", PHIEU_PDF)


def marks_for(version, *, sbd: str = "") -> tuple[list[tuple[float, float]], list[str]]:
    """Danh sách tâm các ô cần tô (pt, gốc trên trái) và cảnh báo (đáp án không tô được)."""
    from .exporter import plain_answer
    pts: list[tuple[float, float]] = []
    warn: list[str] = []
    for i, q in enumerate(version.sections.get("TN") or []):
        if i >= 40:
            warn.append("Phiếu chỉ có 40 câu trắc nghiệm.")
            break
        letter = (q.answer_text or "").strip().upper()[:1]
        if letter in "ABCD" and letter:
            pts.append((P1_X[i // 10][("ABCD").index(letter)], P1_Y[i % 10]))
    for i, q in enumerate(version.sections.get("DS") or []):
        if i >= 8:
            warn.append("Phiếu chỉ có 8 câu Đúng/Sai.")
            break
        blk, side = i // 2, i % 2
        for k, ok in enumerate((q.correct or [])[:4]):
            pts.append((P1_X[blk][2 * side + (0 if ok else 1)], P2_Y[k]))
    for i, q in enumerate(version.sections.get("KQ") or []):
        if i >= 6:
            warn.append("Phiếu chỉ có 6 câu trả lời ngắn.")
            break
        s = plain_answer(q.answer_text).replace(" ", "").replace(".", ",")
        if len(s) > 4:
            warn.append(f"Câu trả lời ngắn {i + 1} «{s}» dài hơn 4 ký tự – không tô được.")
            continue
        for j, ch in enumerate(s):
            x = P3_X[i][j]
            if ch == "-" and j == 0:
                pts.append((x, P3_MINUS_Y))
            elif ch == "," and j in (1, 2):
                pts.append((x, P3_COMMA_Y))
            elif ch.isdigit():
                pts.append((x, P3_DIGIT_Y[int(ch)]))
            else:
                warn.append(f"Câu trả lời ngắn {i + 1} «{s}»: ký tự «{ch}» ở ô {j + 1} không có trên phiếu.")
                break
    code = "".join(c for c in version.code if c.isdigit())
    if code:
        if len(code) > 3:
            warn.append(f"Mã đề {version.code} dài hơn 3 chữ số – phiếu chỉ tô 3 chữ số cuối ({code[-3:]}).")
            code = code[-3:]
        for j, ch in enumerate(code.rjust(3, "0")):
            pts.append((MADE_X[j], DIGIT_ROWS_Y[int(ch)]))
    for j, ch in enumerate((sbd or "")[:6]):
        if ch.isdigit():
            pts.append((SBD_X[j], DIGIT_ROWS_Y[int(ch)]))
    return pts, warn


def _circle_ops(x: float, y_top: float, r: float) -> str:
    y = PAGE_H - y_top
    c = 0.5523 * r
    return (f"{x + r:.2f} {y:.2f} m "
            f"{x + r:.2f} {y + c:.2f} {x + c:.2f} {y + r:.2f} {x:.2f} {y + r:.2f} c "
            f"{x - c:.2f} {y + r:.2f} {x - r:.2f} {y + c:.2f} {x - r:.2f} {y:.2f} c "
            f"{x - r:.2f} {y - c:.2f} {x - c:.2f} {y - r:.2f} {x:.2f} {y - r:.2f} c "
            f"{x + c:.2f} {y - r:.2f} {x + r:.2f} {y - c:.2f} {x + r:.2f} {y:.2f} c f\n")


def fill_pdf(points: list[tuple[float, float]], out_path: str, template: str | None = None) -> str:
    """Vẽ các ô tròn đen lên phiếu gốc và ghi ra out_path (PDF)."""
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, NameObject
    w = PdfWriter()
    w.append(PdfReader(template or template_path()))
    page = w.pages[0]
    st = DecodedStreamObject()
    st.set_data(("q\n0 g\n" + "".join(_circle_ops(x, y, RADIUS) for x, y in points) + "Q\n").encode("ascii"))
    ref = w._add_object(st)
    contents = page.get("/Contents")
    old = contents.get_object() if contents is not None else None
    new = ArrayObject()
    if isinstance(old, ArrayObject):
        new.extend(old)
    elif contents is not None:
        new.append(contents)
    new.append(ref)
    page[NameObject("/Contents")] = new
    with open(out_path, "wb") as f:
        w.write(f)
    return out_path


def export_sheets(versions, out_dir: str) -> tuple[list[str], list[str]]:
    """Mỗi mã đề một phiếu khoá phieu_khoa_<mã>.pdf (+ phieu_trang.pdf = bản gốc để in). Trả về (file, cảnh báo)."""
    os.makedirs(out_dir, exist_ok=True)
    files, warns = [], []
    import shutil
    blank = os.path.join(out_dir, "phieu_trang_TLTN2025.pdf")
    shutil.copyfile(template_path(), blank)
    files.append(blank)
    for v in versions:
        pts, w = marks_for(v)
        warns += [f"Mã {v.code}: {x}" for x in w]
        files.append(fill_pdf(pts, os.path.join(out_dir, f"phieu_khoa_{v.code}.pdf")))
    return files, warns
