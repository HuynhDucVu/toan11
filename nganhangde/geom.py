"""Dựng hình phẳng theo từng bước (như vẽ bằng thước – compa) rồi sinh mã TikZ thuần.

Mỗi bước là một dict {"kind": ..., các tham số}. `build(steps)` tính toạ độ mọi điểm theo thứ tự,
trả về Scene gồm điểm và các nét vẽ; `scene.tikz()` sinh mã, giao diện dùng cùng Scene để xem trước.

Các loại bước (KINDS) – tham số đều là chuỗi để nhập từ ô văn bản:
  diem        ten, x, y                     điểm tự do
  trung_diem  ten, A, B
  chia_doan   ten, A, B, k                  điểm M trên AB với AM = k·AB
  giao        ten, A, B, C, D               giao của đường thẳng AB và CD
  chan_dc     ten, P, A, B                  chân đường vuông góc hạ từ P xuống AB
  trong_tam   ten, A, B, C
  tam_ngoai   ten, A, B, C                  tâm đường tròn ngoại tiếp
  tam_noi     ten, A, B, C                  tâm đường tròn nội tiếp
  quay        ten, P, O, goc                ảnh của P qua phép quay tâm O, góc (độ)
  doan        A, B, net(lien|dut), nhan     đoạn thẳng
  duong       A, B                          đường thẳng (kéo dài qua khung)
  da_giac     ds (vd A,B,C,D), net
  tron        O, r | O, qua (điểm)          đường tròn
  tron_ngoai  A, B, C                       đường tròn ngoại tiếp tam giác
  tron_noi    A, B, C                       đường tròn nội tiếp
  ellipse     O, a, b
  cung        bieu_thuc, tu, den            đồ thị y = f(x) (đường cong)
  goc_vuong   A, B, C                       kí hiệu góc vuông tại B
  goc         A, B, C, nhan                 cung đánh dấu góc ABC
  bang_nhau   A, B, so (1..3)               vạch đánh dấu đoạn bằng nhau
  to_mien     ds, mau                       tô đa giác (vd A,B,C; mau = blue!20)
  chu         x, y, noi_dung                chữ tự do
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .drawgen import FuncError, make_func

KINDS = {
    "diem": ("Điểm tự do", ["ten", "x", "y"]),
    "trung_diem": ("Trung điểm", ["ten", "A", "B"]),
    "chia_doan": ("Điểm chia đoạn AM = k·AB", ["ten", "A", "B", "k"]),
    "giao": ("Giao hai đường thẳng AB, CD", ["ten", "A", "B", "C", "D"]),
    "chan_dc": ("Chân đường vuông góc từ P xuống AB", ["ten", "P", "A", "B"]),
    "trong_tam": ("Trọng tâm tam giác", ["ten", "A", "B", "C"]),
    "tam_ngoai": ("Tâm đường tròn ngoại tiếp", ["ten", "A", "B", "C"]),
    "tam_noi": ("Tâm đường tròn nội tiếp", ["ten", "A", "B", "C"]),
    "quay": ("Ảnh qua phép quay", ["ten", "P", "O", "goc"]),
    "doan": ("Đoạn thẳng", ["A", "B", "net", "nhan"]),
    "duong": ("Đường thẳng", ["A", "B"]),
    "da_giac": ("Đa giác", ["ds", "net"]),
    "tron": ("Đường tròn tâm O bán kính r (hoặc qua điểm)", ["O", "r", "qua"]),
    "tron_ngoai": ("Đường tròn ngoại tiếp", ["A", "B", "C"]),
    "tron_noi": ("Đường tròn nội tiếp", ["A", "B", "C"]),
    "ellipse": ("Elip", ["O", "a", "b"]),
    "cung": ("Đường cong y = f(x)", ["bieu_thuc", "tu", "den"]),
    "goc_vuong": ("Kí hiệu góc vuông tại B", ["A", "B", "C"]),
    "goc": ("Đánh dấu góc ABC", ["A", "B", "C", "nhan"]),
    "bang_nhau": ("Kí hiệu đoạn bằng nhau", ["A", "B", "so"]),
    "to_mien": ("Tô miền đa giác", ["ds", "mau"]),
    "chu": ("Chữ / nhãn tự do", ["x", "y", "noi_dung"]),
}
FIELD_LABEL = {"ten": "Tên điểm", "x": "x", "y": "y", "A": "A", "B": "B", "C": "C", "D": "D", "P": "P", "O": "O",
               "k": "k", "goc": "Góc (độ)", "net": "Nét (lien/dut)", "nhan": "Nhãn", "ds": "Các đỉnh (A,B,C)",
               "r": "Bán kính", "qua": "hoặc qua điểm", "a": "a", "b": "b", "bieu_thuc": "f(x) =", "tu": "x từ",
               "den": "đến", "so": "Số vạch", "mau": "Màu (vd blue!20)", "noi_dung": "Nội dung"}


def _f(v, name="số") -> float:
    try:
        return float(make_func(str(v).replace(",", "."))(0))
    except FuncError:
        raise FuncError(f"«{v}» không phải {name}") from None


@dataclass
class Scene:
    pts: dict = field(default_factory=dict)          # tên → (x, y)
    items: list = field(default_factory=list)        # (loại, dữ liệu)

    def P(self, n):
        n = str(n).strip()
        if n not in self.pts:
            raise FuncError(f"Chưa có điểm {n}")
        return self.pts[n]

    def bbox(self):
        xs = [p[0] for p in self.pts.values()] or [0]
        ys = [p[1] for p in self.pts.values()] or [0]
        for kind, d in self.items:
            if kind in ("circle", "ellipse"):
                (cx, cy), rx, ry = d["c"], d["rx"], d["ry"]
                xs += [cx - rx, cx + rx]
                ys += [cy - ry, cy + ry]
            elif kind == "curve":
                xs += [p[0] for p in d["pts"]]
                ys += [p[1] for p in d["pts"]]
        return min(xs), min(ys), max(xs), max(ys)

    # ------------------------------------------------------------ TikZ
    def tikz(self, labels=True, scale=1.0) -> str:
        def c(p):
            return f"({p[0]:.3f},{p[1]:.3f})"
        L = [f"\\begin{{tikzpicture}}[scale={scale:g},line join=round,line cap=round]"]
        for kind, d in self.items:                       # tô miền trước để nằm dưới
            if kind == "fill":
                L.append(f"\t\\fill[{d['color']}] " + "--".join(c(p) for p in d["pts"]) + "--cycle;")
        x0, y0, x1, y1 = self.bbox()
        for kind, d in self.items:
            st = "dashed" if d.get("dash") else ""
            if kind == "seg":
                lab = f" node[midway,auto,font=\\small]{{${d['label']}$}}" if d.get("label") else ""
                L.append(f"\t\\draw[{st}] {c(d['a'])}--{c(d['b'])}{lab};")
            elif kind == "line":
                (ax, ay), (bx, by) = d["a"], d["b"]
                dx, dy = bx - ax, by - ay
                n = math.hypot(dx, dy) or 1
                ext = max(x1 - x0, y1 - y0) * 0.25 + 0.5
                L.append(f"\t\\draw ({ax - dx / n * ext:.3f},{ay - dy / n * ext:.3f})--"
                         f"({bx + dx / n * ext:.3f},{by + dy / n * ext:.3f});")
            elif kind == "poly":
                L.append(f"\t\\draw[{st}] " + "--".join(c(p) for p in d["pts"]) + "--cycle;")
            elif kind == "circle":
                L.append(f"\t\\draw {c(d['c'])} circle ({d['rx']:.3f});")
            elif kind == "ellipse":
                L.append(f"\t\\draw {c(d['c'])} ellipse ({d['rx']:.3f} and {d['ry']:.3f});")
            elif kind == "curve":
                L.append("\t\\draw[smooth,thick] plot coordinates {" + " ".join(c(p) for p in d["pts"]) + "};")
            elif kind == "right":
                a, b, cc = d["a"], d["b"], d["c"]
                u, v = _unit(b, a, 0.25), _unit(b, cc, 0.25)
                L.append(f"\t\\draw ({b[0] + u[0]:.3f},{b[1] + u[1]:.3f})--({b[0] + u[0] + v[0]:.3f},"
                         f"{b[1] + u[1] + v[1]:.3f})--({b[0] + v[0]:.3f},{b[1] + v[1]:.3f});")
            elif kind == "angle":
                a, b, cc = d["a"], d["b"], d["c"]
                t1 = math.degrees(math.atan2(a[1] - b[1], a[0] - b[0]))
                t2 = math.degrees(math.atan2(cc[1] - b[1], cc[0] - b[0]))
                if (t2 - t1) % 360 > 180:
                    t1, t2 = t2, t1
                t2 = t1 + (t2 - t1) % 360
                lab = f" node[midway,shift={{({math.cos(math.radians((t1 + t2) / 2)) * 0.25:.2f},{math.sin(math.radians((t1 + t2) / 2)) * 0.25:.2f})}},font=\\scriptsize]{{${d['label']}$}}" if d.get("label") else ""
                L.append(f"\t\\draw ({b[0] + 0.4 * math.cos(math.radians(t1)):.3f},"
                         f"{b[1] + 0.4 * math.sin(math.radians(t1)):.3f}) arc ({t1:.2f}:{t2:.2f}:0.4){lab};")
            elif kind == "ticks":
                a, b = d["a"], d["b"]
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                ux, uy = _unit(a, b, 1)
                nx, ny = -uy * 0.1, ux * 0.1
                for k in range(d["n"]):
                    off = (k - (d["n"] - 1) / 2) * 0.07
                    px, py = mx + ux * off, my + uy * off
                    L.append(f"\t\\draw ({px - nx:.3f},{py - ny:.3f})--({px + nx:.3f},{py + ny:.3f});")
            elif kind == "text":
                L.append(f"\t\\node at {c(d['at'])}{{{d['text']}}};")
        if labels:
            cx = sum(p[0] for p in self.pts.values()) / max(1, len(self.pts))
            cy = sum(p[1] for p in self.pts.values()) / max(1, len(self.pts))
            for n, p in self.pts.items():
                ang = math.degrees(math.atan2(p[1] - cy, p[0] - cx)) if (p[0], p[1]) != (cx, cy) else 90
                L.append(f"\t\\fill {c(p)} circle (1pt) node[shift={{({ang:.0f}:7pt)}},font=\\small]{{${_tex_name(n)}$}};")
        L.append("\\end{tikzpicture}")
        return "\n".join(L)


def _tex_name(n: str) -> str:
    return n


def _unit(p, q, s=1.0):
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1
    return dx / n * s, dy / n * s


def _intersect(a, b, c, d):
    x1, y1 = a
    x2, y2 = b
    x3, y3 = c
    x4, y4 = d
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:
        raise FuncError("Hai đường thẳng song song – không có giao điểm")
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / den
    return x1 + t * (x2 - x1), y1 + t * (y2 - y1)


def _circum(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        raise FuncError("Ba điểm thẳng hàng")
    ux = ((ax ** 2 + ay ** 2) * (by - cy) + (bx ** 2 + by ** 2) * (cy - ay) + (cx ** 2 + cy ** 2) * (ay - by)) / d
    uy = ((ax ** 2 + ay ** 2) * (cx - bx) + (bx ** 2 + by ** 2) * (ax - cx) + (cx ** 2 + cy ** 2) * (bx - ax)) / d
    return ux, uy


def _incenter(a, b, c):
    la, lb, lc = math.dist(b, c), math.dist(a, c), math.dist(a, b)
    s = la + lb + lc
    if s < 1e-12:
        raise FuncError("Tam giác suy biến")
    I = ((la * a[0] + lb * b[0] + lc * c[0]) / s, (la * a[1] + lb * b[1] + lc * c[1]) / s)
    area = abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2
    return I, 2 * area / s


def _names(ds: str) -> list[str]:
    return [x.strip() for x in str(ds).replace(";", ",").replace(" ", ",").split(",") if x.strip()]


def build(steps: list[dict]) -> Scene:
    S = Scene()
    for i, st in enumerate(steps, 1):
        k = st.get("kind")
        g = (lambda key, default="": str(st.get(key, default)).strip())
        try:
            if k == "diem":
                S.pts[g("ten")] = (_f(g("x")), _f(g("y")))
            elif k == "trung_diem":
                a, b = S.P(g("A")), S.P(g("B"))
                S.pts[g("ten")] = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            elif k == "chia_doan":
                a, b, t = S.P(g("A")), S.P(g("B")), _f(g("k"))
                S.pts[g("ten")] = (a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1]))
            elif k == "giao":
                S.pts[g("ten")] = _intersect(S.P(g("A")), S.P(g("B")), S.P(g("C")), S.P(g("D")))
            elif k == "chan_dc":
                p, a, b = S.P(g("P")), S.P(g("A")), S.P(g("B"))
                dx, dy = b[0] - a[0], b[1] - a[1]
                t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy or 1)
                S.pts[g("ten")] = (a[0] + t * dx, a[1] + t * dy)
            elif k == "trong_tam":
                a, b, c = S.P(g("A")), S.P(g("B")), S.P(g("C"))
                S.pts[g("ten")] = ((a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3)
            elif k == "tam_ngoai":
                S.pts[g("ten")] = _circum(S.P(g("A")), S.P(g("B")), S.P(g("C")))
            elif k == "tam_noi":
                S.pts[g("ten")] = _incenter(S.P(g("A")), S.P(g("B")), S.P(g("C")))[0]
            elif k == "quay":
                p, o, t = S.P(g("P")), S.P(g("O")), math.radians(_f(g("goc")))
                dx, dy = p[0] - o[0], p[1] - o[1]
                S.pts[g("ten")] = (o[0] + dx * math.cos(t) - dy * math.sin(t), o[1] + dx * math.sin(t) + dy * math.cos(t))
            elif k == "doan":
                S.items.append(("seg", {"a": S.P(g("A")), "b": S.P(g("B")), "dash": g("net") == "dut",
                                        "label": g("nhan")}))
            elif k == "duong":
                S.items.append(("line", {"a": S.P(g("A")), "b": S.P(g("B"))}))
            elif k == "da_giac":
                pts = [S.P(n) for n in _names(g("ds"))]
                if len(pts) < 3:
                    raise FuncError("Đa giác cần ít nhất 3 đỉnh")
                S.items.append(("poly", {"pts": pts, "dash": g("net") == "dut"}))
            elif k == "tron":
                o = S.P(g("O"))
                r = math.dist(o, S.P(g("qua"))) if g("qua") else _f(g("r"), "bán kính")
                S.items.append(("circle", {"c": o, "rx": r, "ry": r}))
            elif k == "tron_ngoai":
                a, b, c = S.P(g("A")), S.P(g("B")), S.P(g("C"))
                o = _circum(a, b, c)
                S.items.append(("circle", {"c": o, "rx": math.dist(o, a), "ry": math.dist(o, a)}))
            elif k == "tron_noi":
                o, r = _incenter(S.P(g("A")), S.P(g("B")), S.P(g("C")))
                S.items.append(("circle", {"c": o, "rx": r, "ry": r}))
            elif k == "ellipse":
                S.items.append(("ellipse", {"c": S.P(g("O")), "rx": _f(g("a")), "ry": _f(g("b"))}))
            elif k == "cung":
                f = make_func(g("bieu_thuc"))
                a, b = _f(g("tu")), _f(g("den"))
                pts = [(a + (b - a) * j / 200, f(a + (b - a) * j / 200)) for j in range(201)]
                pts = [p for p in pts if not math.isnan(p[1]) and abs(p[1]) < 1e3]
                S.items.append(("curve", {"pts": pts}))
            elif k == "goc_vuong":
                S.items.append(("right", {"a": S.P(g("A")), "b": S.P(g("B")), "c": S.P(g("C"))}))
            elif k == "goc":
                S.items.append(("angle", {"a": S.P(g("A")), "b": S.P(g("B")), "c": S.P(g("C")), "label": g("nhan")}))
            elif k == "bang_nhau":
                S.items.append(("ticks", {"a": S.P(g("A")), "b": S.P(g("B")), "n": max(1, min(3, int(_f(g("so", "1")))))}))
            elif k == "to_mien":
                S.items.append(("fill", {"pts": [S.P(n) for n in _names(g("ds"))], "color": g("mau") or "gray!25"}))
            elif k == "chu":
                S.items.append(("text", {"at": (_f(g("x")), _f(g("y"))), "text": g("noi_dung")}))
            else:
                raise FuncError(f"Không biết loại bước «{k}»")
        except FuncError as e:
            raise FuncError(f"Bước {i}: {e}") from None
    return S


def describe(st: dict) -> str:
    name, fields = KINDS.get(st.get("kind"), (st.get("kind"), []))
    args = ", ".join(f"{f}={st[f]}" for f in fields if str(st.get(f, "")).strip())
    return f"{name}: {args}"


def S(kind, **kw):
    return {"kind": kind, **{k: str(v) for k, v in kw.items()}}


TEMPLATES = {
    "Tam giác ABC có đường cao AH": [
        S("diem", ten="A", x=1.2, y=3), S("diem", ten="B", x=0, y=0), S("diem", ten="C", x=4, y=0),
        S("chan_dc", ten="H", P="A", A="B", B="C"), S("da_giac", ds="A,B,C"), S("doan", A="A", B="H", net="dut"),
        S("goc_vuong", A="A", B="H", C="C")],
    "Tam giác vuông tại A": [
        S("diem", ten="A", x=0, y=0), S("diem", ten="B", x=0, y=3), S("diem", ten="C", x=4, y=0),
        S("da_giac", ds="A,B,C"), S("goc_vuong", A="B", B="A", C="C")],
    "Tam giác với đường tròn ngoại tiếp": [
        S("diem", ten="A", x=1, y=3), S("diem", ten="B", x=-1.5, y=0), S("diem", ten="C", x=3, y=0),
        S("tam_ngoai", ten="O", A="A", B="B", C="C"), S("da_giac", ds="A,B,C"), S("tron_ngoai", A="A", B="B", C="C")],
    "Tam giác với đường tròn nội tiếp": [
        S("diem", ten="A", x=1, y=3), S("diem", ten="B", x=-1, y=0), S("diem", ten="C", x=4, y=0),
        S("tam_noi", ten="I", A="A", B="B", C="C"), S("da_giac", ds="A,B,C"), S("tron_noi", A="A", B="B", C="C")],
    "Tam giác cân, trung tuyến AM": [
        S("diem", ten="A", x=2, y=3.2), S("diem", ten="B", x=0, y=0), S("diem", ten="C", x=4, y=0),
        S("trung_diem", ten="M", A="B", B="C"), S("da_giac", ds="A,B,C"), S("doan", A="A", B="M"),
        S("bang_nhau", A="A", B="B", so=1), S("bang_nhau", A="A", B="C", so=1), S("bang_nhau", A="B", B="M", so=2),
        S("bang_nhau", A="M", B="C", so=2)],
    "Hình bình hành ABCD": [
        S("diem", ten="A", x=0, y=0), S("diem", ten="B", x=4, y=0), S("diem", ten="D", x=1.2, y=2.2),
        S("diem", ten="C", x="4+1.2", y="2.2"), S("da_giac", ds="A,B,C,D"), S("giao", ten="O", A="A", B="C",
                                                                                  C="B", D="D")],
    "Hình vuông ABCD, tâm O": [
        S("diem", ten="A", x=0, y=0), S("diem", ten="B", x=3, y=0), S("quay", ten="C", P="A", O="B", goc=-90),
        S("quay", ten="D", P="B", O="A", goc=90), S("da_giac", ds="A,B,C,D"), S("doan", A="A", B="C", net="dut"),
        S("doan", A="B", B="D", net="dut"), S("giao", ten="O", A="A", B="C", C="B", D="D")],
    "Đường tròn tâm O, tiếp tuyến tại A": [
        S("diem", ten="O", x=0, y=0), S("diem", ten="A", x=1.5, y=1.5), S("tron", O="O", qua="A"),
        S("quay", ten="T", P="O", O="A", goc=90), S("quay", ten="T'", P="O", O="A", goc=-90),
        S("doan", A="O", B="A"), S("doan", A="T", B="T'"), S("goc_vuong", A="O", B="A", C="T")],
}


