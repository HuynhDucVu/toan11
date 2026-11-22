"""Tab «Vẽ hình»: bảng biến thiên, đồ thị, biểu đồ → TikZ; xem trước bằng QPainter."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTabWidget, QTextBrowser, QVBoxLayout,
    QWidget)
from ..common import latex_editor
from .draw_studio import DrawMoreMixin, DrawStudioMixin

if TYPE_CHECKING:
    from ..main_window import MainWindow


class PlotView(QWidget):
    """Xem trước đồ thị / biểu đồ bằng QPainter (không cần LaTeX)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(360, 300)
        self.mode, self.data = None, None

    def show_graph(self, f, xmin, xmax, ymin, ymax, points=()):
        self.mode, self.data = "graph", (f, xmin, xmax, ymin, ymax, points)
        self.update()

    def show_chart(self, kind, labels, values):
        self.mode, self.data = kind, (labels, values)
        self.update()

    def paintEvent(self, _e):
        from ... import drawgen as dg
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        W, H, m = self.width(), self.height(), 24
        if self.mode == "graph":
            f, x0, x1, y0, y1, pts = self.data

            def X(x):
                return m + (x - x0) / (x1 - x0) * (W - 2 * m)

            def Y(y):
                return H - m - (y - y0) / (y1 - y0) * (H - 2 * m)
            p.setPen(QPen(QColor("#e3e8ef"), 1))
            for i in range(int(x0), int(x1) + 1):
                p.drawLine(int(X(i)), int(Y(y0)), int(X(i)), int(Y(y1)))
            for j in range(int(y0), int(y1) + 1):
                p.drawLine(int(X(x0)), int(Y(j)), int(X(x1)), int(Y(j)))
            p.setPen(QPen(QColor("black"), 1.4))
            p.drawLine(int(X(x0)), int(Y(0)), int(X(x1)), int(Y(0)))
            p.drawLine(int(X(0)), int(Y(y0)), int(X(0)), int(Y(y1)))
            p.setFont(QFont("Segoe UI", 8))
            for i in range(int(x0), int(x1) + 1):
                if i:
                    p.drawText(int(X(i)) - 4, int(Y(0)) + 13, str(i))
            for j in range(int(y0), int(y1) + 1):
                if j:
                    p.drawText(int(X(0)) - 16, int(Y(j)) + 4, str(j))
            p.setPen(QPen(QColor("#1f5fbf"), 2.2))
            for seg in dg.sample(f, x0, x1, 600, y0 - 0.5, y1 + 0.5):
                path = QPainterPath()
                path.moveTo(X(seg[0][0]), Y(seg[0][1]))
                for x, y in seg[1:]:
                    path.lineTo(X(x), Y(y))
                p.drawPath(path)
            p.setBrush(QBrush(QColor("#c00000")))
            for x in pts:
                y = f(x)
                if y == y:
                    p.drawEllipse(int(X(x)) - 3, int(Y(y)) - 3, 6, 6)
        elif self.mode in ("bar", "pie") and self.data[1]:
            labels, values = self.data
            colors = ["#f4a6a6", "#a6c4f4", "#a6e3a6", "#f9cc8a", "#d1a6f4", "#a6e8f0", "#f7f08a", "#cfcfcf"]
            p.setFont(QFont("Segoe UI", 9))
            if self.mode == "bar":
                vmax = max(values) or 1
                n = len(values)
                bw = (W - 2 * m) / max(n, 1)
                for i, (lb, v) in enumerate(zip(labels, values)):
                    h = (H - 3 * m) * v / vmax
                    x = m + i * bw + bw * 0.2
                    p.setBrush(QBrush(QColor("#8fb3e8")))
                    p.setPen(QPen(QColor("black"), 1))
                    p.drawRect(int(x), int(H - 2 * m - h), int(bw * 0.6), int(h))
                    p.drawText(int(x), int(H - 2 * m - h) - 4, dg.nice(v).replace("{,}", ","))
                    p.drawText(int(x), H - m, lb[:12])
                p.drawLine(m, H - 2 * m, W - m, H - 2 * m)
            else:
                tot = sum(values) or 1
                r = min(W, H) / 2 - m
                cx, cy = W / 2, H / 2
                a = 90 * 16
                for i, (lb, v) in enumerate(zip(labels, values)):
                    span = -int(360 * 16 * v / tot)
                    p.setBrush(QBrush(QColor(colors[i % len(colors)])))
                    p.setPen(QPen(QColor("black"), 1))
                    p.drawPie(int(cx - r), int(cy - r), int(2 * r), int(2 * r), a, span)
                    import math as _m
                    mid = _m.radians((a + span / 2) / 16)
                    p.drawText(int(cx + 0.6 * r * _m.cos(mid)) - 20, int(cy - 0.6 * r * _m.sin(mid)),
                               f"{lb[:10]} {100 * v / tot:.1f}%".replace(".", ","))
                    a += span
        p.end()


class DrawPanel(DrawMoreMixin, DrawStudioMixin, QWidget):
    """Tab «Vẽ hình»: bảng biến thiên, đồ thị (tiệm cận, tô miền), biểu đồ, trục số, miền nghiệm, hình khối."""

    ALL = ("bbt", "sign", "graph", "chart", "numline", "trig", "region", "solid")
    NAMES = {"bbt": "Bảng biến thiên", "sign": "Bảng xét dấu", "graph": "Đồ thị hàm số", "chart": "Biểu đồ cột / quạt",
             "numline": "Trục số", "trig": "Đường tròn lượng giác", "region": "Miền nghiệm", "solid": "Hình khối"}

    def __init__(self, win: MainWindow, kinds=ALL):
        super().__init__()
        self.win = win
        self.kinds = tuple(kinds)
        lay = QVBoxLayout(self)
        self.sub = QTabWidget()
        lay.addWidget(self.sub, 1)
        build = {"bbt": self._bbt_tab, "sign": self._sign_tab, "graph": self._graph_tab, "chart": self._chart_tab,
                 "numline": self._numline_tab, "trig": self._trig_tab, "region": self._region_tab,
                 "solid": self._solid_tab}
        for k in self.kinds:
            self.sub.addTab(self._with_preview(build[k]()), self.NAMES[k])
        g = QGroupBox("Mã TikZ (dán vào đề bài hoặc lời giải)")
        gl = QVBoxLayout(g)
        self.code = latex_editor()
        self.code.setMaximumHeight(230)
        gl.addWidget(self.code)
        row = QHBoxLayout()
        for text, fn in (("📋 Chép mã", self.copy), ("Lưu thành file .tex…", self.save),
                         ("Xem trước PDF", self.preview_pdf)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        self.l_pkg = QLabel()
        row.addWidget(self.l_pkg)
        row.addStretch()
        gl.addLayout(row)
        lay.addWidget(g)

    def _with_preview(self, page):
        """Trang nhập liệu + khung xem trước ngay bên phải (như bảng biến thiên): xem hình mà không rời trang tạo mã."""
        if hasattr(self, "bbt_view") and page.findChild(QTextBrowser) is self.bbt_view:
            page.preview = self.bbt_view                       # trang đã có khung xem trước riêng
            return page
        from PySide6.QtWidgets import QScrollArea
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(page, 3)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        lab = QLabel("<i>Xem trước hình sẽ hiện ở đây sau khi tạo mã (cần LaTeX trên máy).</i>")
        lab.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        lab.setWordWrap(True)
        sc.setWidget(lab)
        h.addWidget(sc, 3)
        w.preview = lab
        return w

    def show_preview(self, pdf_path: str) -> bool:
        """Vẽ trang 1 của PDF vào khung xem trước của trang đang mở. False nếu không vẽ được (thiếu pypdfium2…)."""
        from PySide6.QtGui import QPixmap
        pv = getattr(self.sub.currentWidget(), "preview", None)
        if pv is None:
            return False
        try:
            from ...pdfrender import render_file
            img = render_file(pdf_path, 0, 1.8)
        except Exception:  # noqa: BLE001
            return False
        if img is None:
            return False
        if isinstance(pv, QTextBrowser):
            pv.document().addResource(2, QUrl("preview.png"), img)      # 2 = QTextDocument.ImageResource
            pv.setHtml('<p><b>Xem trước</b></p><img src="preview.png">')
        else:
            pv.setPixmap(QPixmap.fromImage(img))
        return True

    def _msg(self, text, ok=True):
        self.l_pkg.setText(f"<span style='color:{'#0b7a0b' if ok else '#c00000'}'>{text}</span>")

    # --- bảng biến thiên
    def _bbt_tab(self):
        w = QWidget()
        h = QHBoxLayout(w)
        f = QFormLayout()
        h.addLayout(f, 2)
        self.e_fx = QLineEdit("x^3 - 3x + 1")
        self.e_fname = QLineEdit("y")
        b = QPushButton("Tự lập bảng từ hàm số")
        b.setObjectName("primary")
        b.clicked.connect(self.bbt_auto)
        f.addRow("Hàm số y =", self.e_fx)
        f.addRow("Tên hàm", self.e_fname)
        f.addRow(b)
        f.addRow(QLabel("<b>Hoặc sửa tay</b> (cách nhau dấu phẩy, theo cú pháp tkz-tab):"))
        self.e_xs = QLineEdit()
        self.e_sign = QLineEdit()
        self.e_var = QLineEdit()
        self.e_xs.setPlaceholderText(r"-\infty, -1, 1, +\infty")
        self.e_sign.setPlaceholderText(",+,0,-,0,+,")
        self.e_var.setPlaceholderText(r"-/$-\infty$, +/$3$, -/$-1$, +/$+\infty$")
        f.addRow("Hàng x", self.e_xs)
        f.addRow("Hàng y'", self.e_sign)
        f.addRow("Hàng y", self.e_var)
        b2 = QPushButton("Tạo mã từ 3 hàng trên")
        b2.clicked.connect(self.bbt_manual)
        f.addRow(b2)
        f.addRow(QLabel("<i>Cần gói <code>\\usepackage{tkz-tab}</code>. Hàm hỗ trợ: đa thức, phân thức, sqrt, sin, cos, exp, ln.</i>"))
        self.bbt_view = QTextBrowser()
        h.addWidget(self.bbt_view, 3)
        return w

    def bbt_auto(self):
        from ... import drawgen as dg
        try:
            t = dg.variation_table(self.e_fx.text(), self.e_fname.text() or "y")
        except dg.FuncError as e:
            self._msg(str(e), False)
            return
        self.e_xs.setText(", ".join(t["xs"]))
        self.e_sign.setText(",".join(t["sign"]))
        self.e_var.setText(", ".join(t["var"]))
        self.bbt_manual()
        self._msg("Đã lập bảng – kiểm tra lại giá trị trước khi dùng (tính bằng số, có thể làm tròn).")

    def bbt_manual(self):
        from ... import drawgen as dg
        xs = [x.strip().strip("$") for x in self.e_xs.text().split(",") if x.strip()]
        sign = [x.strip() for x in self.e_sign.text().split(",")]
        var = [x.strip() for x in re.split(r",\s*(?=[+\-][D/])", self.e_var.text()) if x.strip()]
        name = self.e_fname.text() or "y"
        self.code.setPlainText(dg.variation_tikz(xs, sign[:-1] if sign and sign[-1] == "" else sign, var, name))
        # xem trước dạng bảng HTML
        def cell(v):
            return v.replace("\\infty", "∞").replace("\\dfrac", "").replace("$", "")
        def at(v, pos):
            parts = v.split("/")
            if "D" in parts[0]:                     # tiệm cận đứng: «-D+/trái/phải»
                l_, r_ = parts[0].split("D")
                txt = [cell(parts[1]) if l_ == pos else "", cell(parts[2]) if r_ == pos else ""]
                return " ‖ ".join(t or "&nbsp;" for t in txt)
            return cell(parts[1]) if parts[0] == pos else ""
        top = "".join(f"<td align=center>{at(v, '+')}</td><td></td>" for v in var)
        bot = "".join(f"<td align=center>{at(v, '-')}</td><td></td>" for v in var)
        xrow = "".join(f"<td align=center><b>{cell(x)}</b></td><td></td>" for x in xs)
        srow = "".join(f"<td align=center>{s_}</td>" for s_ in sign[1:])
        self.bbt_view.setHtml("<p><b>Xem trước (đơn giản)</b></p><table border=1 cellspacing=0 cellpadding=6>"
                              f"<tr><td>x</td>{xrow}</tr><tr><td>{name}'</td><td></td>{srow}</tr>"
                              f"<tr><td rowspan=2>{name}</td>{top}</tr><tr>{bot}</tr></table>")

    # --- đồ thị
    def _graph_tab(self):
        w = QWidget()
        h = QHBoxLayout(w)
        f = QFormLayout()
        h.addLayout(f, 2)
        self.e_gx = QLineEdit("x^3 - 3x + 1")
        self.sp = {}
        for k, v in (("xmin", -3), ("xmax", 3), ("ymin", -3), ("ymax", 4)):
            sp = QSpinBox()
            sp.setRange(-50, 50)
            sp.setValue(v)
            self.sp[k] = sp
        self.e_pts = QLineEdit("-1, 1")
        self.c_grid = QCheckBox("Vẽ lưới")
        self.c_grid.setChecked(True)
        self.e_glabel = QLineEdit("(C)")
        f.addRow("Hàm số y =", self.e_gx)
        rowx, rowy = QHBoxLayout(), QHBoxLayout()
        for k in ("xmin", "xmax"):
            rowx.addWidget(self.sp[k])
        for k in ("ymin", "ymax"):
            rowy.addWidget(self.sp[k])
        f.addRow("x từ … đến", rowx)
        f.addRow("y từ … đến", rowy)
        f.addRow("Đánh dấu điểm có x =", self.e_pts)
        f.addRow("Nhãn đồ thị", self.e_glabel)
        f.addRow("", self.c_grid)
        self.c_asym = QCheckBox("Vẽ tiệm cận (đứng, ngang, xiên)")
        self.c_asym.setChecked(True)
        self.e_shade = QLineEdit()
        self.e_shade.setPlaceholderText("vd 0; 2 – tô miền tích phân trên [0; 2]")
        self.e_g2 = QLineEdit()
        self.e_g2.setPlaceholderText("hàm thứ hai g(x) (tuỳ chọn), vd 2x")
        f.addRow("", self.c_asym)
        f.addRow("Tô miền trên đoạn", self.e_shade)
        f.addRow("Hàm thứ hai", self.e_g2)
        self._graph_extras(f)
        b = QPushButton("Vẽ và tạo mã")
        b.setObjectName("primary")
        b.clicked.connect(self.graph)
        f.addRow(b)
        f.addRow(QLabel("<i>Mã dùng TikZ thuần (toạ độ điểm tính sẵn) – biên dịch được ở mọi máy.</i>"))
        self.gview = PlotView()
        h.addWidget(self.gview, 3)
        return w

    def graph(self):
        from ... import drawgen as dg
        try:
            f = dg.make_func(self.e_gx.text())
            pts = [float(x) for x in self.e_pts.text().replace(";", ",").split(",") if x.strip()]
        except (dg.FuncError, ValueError) as e:
            self._msg(str(e), False)
            return
        v = {k: sp.value() for k, sp in self.sp.items()}
        if v["xmin"] >= v["xmax"] or v["ymin"] >= v["ymax"]:
            self._msg("Khoảng x hoặc y không hợp lệ", False)
            return
        self.gview.show_graph(f, v["xmin"], v["xmax"], v["ymin"], v["ymax"], pts)
        from ... import drawstudio as ds
        shade = None
        if self.e_shade.text().strip():
            try:
                a, b = [float(x.replace(",", ".")) for x in self.e_shade.text().replace(";", " ").split()][:2]
                shade = (min(a, b), max(a, b))
            except ValueError:
                self._msg("Đoạn tô miền: nhập 2 số, vd 0; 2", False)
                return
        try:
            code = ds.graph_plus_tikz(
                self.e_gx.text(), v["xmin"], v["xmax"], v["ymin"], v["ymax"], grid=self.c_grid.isChecked(),
                label=self.e_glabel.text(), points=pts, show_asymptotes=self.c_asym.isChecked(), shade=shade,
                expr2=self.e_g2.text())
            self.code.setPlainText(self._apply_graph_extras(code))
        except (dg.FuncError, ValueError) as e:
            self._msg(str(e), False)
            return
        self._msg("Đã tạo mã đồ thị.")

    # --- biểu đồ
    def _chart_tab(self):
        w = QWidget()
        h = QHBoxLayout(w)
        f = QFormLayout()
        h.addLayout(f, 2)
        self.e_data = QPlainTextEdit("Giỏi: 12\nKhá: 20\nTrung bình: 6\nYếu: 2")
        self.cb_kind = QComboBox()
        self.cb_kind.addItem("Biểu đồ cột", "bar")
        self.cb_kind.addItem("Biểu đồ quạt (tròn)", "pie")
        self.e_xl, self.e_yl = QLineEdit("Xếp loại"), QLineEdit("Số học sinh")
        f.addRow("Số liệu (mỗi dòng «nhãn: số»)", self.e_data)
        f.addRow("Loại", self.cb_kind)
        f.addRow("Nhãn trục ngang", self.e_xl)
        f.addRow("Nhãn trục đứng", self.e_yl)
        b = QPushButton("Vẽ và tạo mã")
        b.setObjectName("primary")
        b.clicked.connect(self.chart)
        f.addRow(b)
        self.cview = PlotView()
        h.addWidget(self.cview, 3)
        return w

    def chart(self):
        from ... import drawgen as dg
        try:
            labels, values = dg.parse_data(self.e_data.toPlainText())
        except dg.FuncError as e:
            self._msg(str(e), False)
            return
        kind = self.cb_kind.currentData()
        self.cview.show_chart(kind, labels, values)
        code = dg.bar_tikz(labels, values, self.e_xl.text(), self.e_yl.text()) if kind == "bar" \
            else dg.pie_tikz(labels, values)
        self.code.setPlainText(code)
        self._msg("Đã tạo mã biểu đồ.")

    # --- chung
    def copy(self):
        QApplication.clipboard().setText(self.code.toPlainText())
        self._msg("Đã chép mã – dán (Ctrl+V) vào câu hỏi.")

    def save(self):
        p, _ = QFileDialog.getSaveFileName(self, "Lưu hình", "hinh.tex", "LaTeX (*.tex)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write("\\documentclass[tikz,border=2pt]{standalone}\n\\usepackage{amsmath,tkz-tab}\n"
                        "\\begin{document}\n" + self.code.toPlainText() + "\n\\end{document}\n")
