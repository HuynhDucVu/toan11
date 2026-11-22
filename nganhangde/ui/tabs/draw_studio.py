"""Draw Studio trong tab «Vẽ hình»: trục số, miền nghiệm, hình khối, xem trước PDF.

Tách thành mixin để draw.py gọn; DrawPanel kế thừa DrawStudioMixin.
"""
from __future__ import annotations

import os
import tempfile

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QFormLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QSpinBox, QTextBrowser, QWidget)

STANDALONE = ("\\documentclass[tikz,border=4pt]{standalone}\n\\usepackage{amsmath,amssymb,tkz-tab}\n"
              "\\begin{document}\n%s\n\\end{document}\n")


class DrawStudioMixin:
    # ---------------------------------------------------------------- trục số
    def _numline_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.e_set = QLineEdit("(-inf;-2] U (1;3) U {5}")
        self.c_hatch = QCheckBox("Gạch bỏ phần không thuộc tập nghiệm (kiểu SGK)")
        self.c_hatch.setChecked(True)
        f.addRow(QLabel("Nhập tập hợp: khoảng <code>(a;b)</code>, đoạn <code>[a;b]</code>, nửa khoảng, vô cực "
                        "<code>inf</code>, điểm <code>{5}</code>, hợp bằng <code>U</code>. Ví dụ "
                        "<code>(-inf;-2] U (1;3) U {5}</code>."))
        f.addRow("Tập hợp", self.e_set)
        f.addRow(self.c_hatch)
        b = QPushButton("Tạo mã")
        b.setObjectName("primary")
        b.clicked.connect(self.numline)
        f.addRow(b)
        return w

    def numline(self):
        from ... import drawstudio as ds
        try:
            self.code.setPlainText(ds.number_line_tikz(self.e_set.text(), self.c_hatch.isChecked()))
        except (ds.FuncError, ValueError) as e:
            self._msg(str(e), False)
            return
        self._msg("Đã tạo mã trục số – bấm «Xem trước PDF» để xem.")
        self.preview_pdf(auto=True)

    # ---------------------------------------------------------------- miền nghiệm
    def _region_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.e_ineqs = QPlainTextEdit("x >= 0\ny >= 0\nx + y <= 4\nx + 2y < 6")
        self.e_ineqs.setMaximumHeight(110)
        self.e_obj = QLineEdit("3x + 2y")
        self.sp_box = {}
        row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        for k, v in (("xmin", -1), ("xmax", 6), ("ymin", -1), ("ymax", 5)):
            sp = QSpinBox()
            sp.setRange(-50, 50)
            sp.setValue(v)
            sp.setPrefix(k[0] + (" từ " if "min" in k else " đến "))
            self.sp_box[k] = sp
            hl.addWidget(sp)
        f.addRow("Mỗi dòng một bất phương trình", self.e_ineqs)
        f.addRow("Khung vẽ", row)
        f.addRow("Biểu thức F (tìm GTLN, GTNN)", self.e_obj)
        b = QPushButton("Vẽ miền nghiệm và tính F tại các đỉnh")
        b.setObjectName("primary")
        b.clicked.connect(self.region)
        f.addRow(b)
        self.region_info = QTextBrowser()
        self.region_info.setMaximumHeight(110)
        f.addRow(self.region_info)
        return w

    def region(self):
        from ... import drawstudio as ds
        from ...drawgen import nice
        ineqs = [x for x in self.e_ineqs.toPlainText().splitlines() if x.strip()]
        v = {k: sp.value() for k, sp in self.sp_box.items()}
        try:
            code = ds.region_tikz(ineqs, v["xmin"], v["xmax"], v["ymin"], v["ymax"])
            rows, lo, hi = ds.optimize(ineqs, self.e_obj.text()) if self.e_obj.text().strip() else ([], None, None)
        except (ds.FuncError, ValueError, ZeroDivisionError) as e:
            self._msg(str(e), False)
            return
        self.code.setPlainText(code)
        if rows:
            t = "".join(f"<tr><td>({nice(x)}; {nice(y)})</td><td align=center>{nice(F)}</td></tr>" for x, y, F in rows)
            self.region_info.setHtml(f"<table border=1 cellspacing=0 cellpadding=3><tr><th>Đỉnh</th><th>F</th></tr>{t}"
                                     f"</table><p>GTNN của F = <b>{nice(lo)}</b>, GTLN = <b>{nice(hi)}</b> "
                                     "<i>(đúng khi miền nghiệm là đa giác – bị chặn)</i></p>")
        else:
            self.region_info.setHtml("<i>Miền nghiệm không có đỉnh nào (rỗng hoặc không bị chặn).</i>")
        self._msg("Đã tạo mã miền nghiệm (phần tô xám là phần bị gạch bỏ).")
        self.preview_pdf(auto=True)

    # ---------------------------------------------------------------- hình khối
    def _solid_tab(self):
        from ... import drawstudio as ds
        w = QWidget()
        f = QFormLayout(w)
        self.cb_solid = QComboBox()
        for k, name in ds.SOLIDS.items():
            self.cb_solid.addItem(name, k)
        self.sp_a = QDoubleSpinBox()
        self.sp_a.setRange(1, 8)
        self.sp_a.setValue(3)
        self.sp_h = QDoubleSpinBox()
        self.sp_h.setRange(1, 8)
        self.sp_h.setValue(3.5)
        f.addRow("Hình", self.cb_solid)
        f.addRow("Cạnh đáy / đường kính", self.sp_a)
        f.addRow("Chiều cao", self.sp_h)
        b = QPushButton("Tạo mã")
        b.setObjectName("primary")
        b.clicked.connect(self.solid)
        f.addRow(b)
        f.addRow(QLabel("<i>Hình chiếu song song theo SGK: cạnh khuất nét đứt. Toạ độ đặt tên (A), (B)… để vẽ "
                        "thêm đường (vd <code>\\draw (S)--(O);</code>).</i>"))
        return w

    def solid(self):
        from ... import drawstudio as ds
        self.code.setPlainText(ds.solid_tikz(self.cb_solid.currentData(), self.sp_a.value(), self.sp_h.value()))
        self._msg("Đã tạo mã hình khối.")

    # ---------------------------------------------------------------- xem trước
    def preview_pdf(self, _checked=False, auto=False):
        from ...pdfbuild import compile_tex, find_engine
        code = self.code.toPlainText().strip()
        if not code:
            return
        d = tempfile.mkdtemp(prefix="nhd_hinh_")
        p = os.path.join(d, "hinh.tex")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(STANDALONE % code)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            eng = find_engine(self.win.settings.value("pdf/engine", "auto"))
            if not eng:
                if auto:
                    return
                self._msg("Chưa tìm thấy LaTeX (TeX Live/MiKTeX) – chỉ đường dẫn trong Cài đặt biên dịch PDF.", False)
                return
            r = compile_tex(p, eng, runs=1)
        finally:
            QApplication.restoreOverrideCursor()
        if r.ok and r.pdf:
            if self.show_preview(r.pdf):
                self._msg("Đã biên dịch hình – xem ở khung bên phải.")
            elif not auto:
                QDesktopServices.openUrl(QUrl.fromLocalFile(r.pdf))
                self._msg("Đã biên dịch hình.")
        else:
            self._msg(r.summary(), False)


class DrawMoreMixin:
    """Bảng xét dấu, đường tròn lượng giác, mẫu hàm số, đồ thị theo cực trị, vạch chia và điểm gióng."""

    # ---------------------------------------------------------------- bảng xét dấu
    def _sign_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.e_sign = QLineEdit("(x - 1)(x + 2)/(x - 3)")
        self.e_sign_name = QLineEdit("f(x)")
        f.addRow(QLabel("Nhập biểu thức (tích, thương các nhân tử, đa thức…). Phần mềm tìm nghiệm, điểm không xác định "
                        "và xét dấu trên từng khoảng."))
        f.addRow("Biểu thức", self.e_sign)
        f.addRow("Tên dòng", self.e_sign_name)
        b = QPushButton("Lập bảng xét dấu")
        b.setObjectName("primary")
        b.clicked.connect(self.sign_auto)
        f.addRow(b)
        f.addRow(QLabel("<b>Nhập tay</b> (khi hàm phức tạp): mốc x cách nhau bằng dấu phẩy, dòng dấu theo tkz-tab "
                        "(vd <code>,+,0,-,d,+,</code>)."))
        self.e_sign_x = QLineEdit("-\\infty, -2, 1, +\\infty")
        self.e_sign_line = QLineEdit(",+,0,-,0,+,")
        f.addRow("Các mốc x", self.e_sign_x)
        f.addRow("Dòng dấu", self.e_sign_line)
        b2 = QPushButton("Tạo mã từ nhập tay")
        b2.clicked.connect(self.sign_manual)
        f.addRow(b2)
        return w

    def sign_auto(self):
        from ... import drawmore as dm
        try:
            self.code.setPlainText(dm.sign_table_tikz(self.e_sign.text(), self.e_sign_name.text() or "f(x)"))
        except (dm.FuncError, ValueError) as e:
            self._msg(str(e), False)
            return
        self._msg("Đã tạo bảng xét dấu (gói tkz-tab).")

    def sign_manual(self):
        from ... import drawmore as dm
        xs = [x.strip() for x in self.e_sign_x.text().split(",") if x.strip()]
        line = [x.strip() for x in self.e_sign_line.text().split(",")]
        self.code.setPlainText(dm.sign_table_manual(xs, line, self.e_sign_name.text() or "f(x)"))
        self._msg("Đã tạo bảng xét dấu nhập tay.")

    # ---------------------------------------------------------------- đường tròn lượng giác
    def _trig_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.e_trig = QPlainTextEdit("pi/6 + k2pi\n5pi/6 + k2pi")
        self.e_trig.setMaximumHeight(90)
        self.c_trig_poly = QCheckBox("Nối các điểm thành đa giác")
        self.c_trig_poly.setChecked(True)
        f.addRow(QLabel("Mỗi dòng một họ nghiệm dạng <code>a + k·b</code>, vd <code>pi/6 + k2pi</code>, "
                        "<code>-pi/4 + kpi/2</code>. Phần mềm biểu diễn các điểm ngọn cung trên đường tròn lượng giác."))
        f.addRow("Họ nghiệm", self.e_trig)
        f.addRow(self.c_trig_poly)
        b = QPushButton("Biểu diễn")
        b.setObjectName("primary")
        b.clicked.connect(self.trig)
        f.addRow(b)
        self.l_trig = QLabel()
        f.addRow(self.l_trig)
        return w

    def trig(self):
        from ... import drawmore as dm
        fams = [x for x in self.e_trig.toPlainText().splitlines() if x.strip()]
        try:
            pts = dm.trig_points(fams)
            self.code.setPlainText(dm.trig_circle_tikz(fams, self.c_trig_poly.isChecked()))
        except dm.FuncError as e:
            self._msg(str(e), False)
            return
        self.l_trig.setText(f"{len(pts)} điểm: " + ", ".join(f"${dm.angle_latex(t)}$" for t in pts))
        self._msg("Đã tạo mã đường tròn lượng giác.")
        self.preview_pdf(auto=True)

    # ---------------------------------------------------------------- đồ thị: phần bổ sung
    def _graph_extras(self, f):
        from ... import drawmore as dm
        self.cb_tpl = QComboBox()
        self.cb_tpl.addItem("— Mẫu hàm số thường gặp —", "")
        for name, expr in dm.TEMPLATES:
            self.cb_tpl.addItem(name, expr)
        self.cb_tpl.currentIndexChanged.connect(
            lambda: self.cb_tpl.currentData() and self.e_gx.setText(self.cb_tpl.currentData()))
        f.addRow("Mẫu", self.cb_tpl)
        self.e_ext = QLineEdit()
        self.e_ext.setPlaceholderText("bậc 3: x1;y1;x2;y2 – trùng phương: y0;x1;y1  (vd -1;3;1;-1)")
        b = QPushButton("Hàm theo cực trị")
        b.setToolTip("Tìm hàm bậc ba (4 số) hoặc trùng phương (3 số) có các điểm cực trị đã cho")
        b.clicked.connect(self.from_extrema)
        row = QWidget()
        from PySide6.QtWidgets import QHBoxLayout
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.e_ext)
        hl.addWidget(b)
        f.addRow("Đồ thị theo hình", row)
        self.e_xt = QLineEdit()
        self.e_xt.setPlaceholderText("vd -1, 1, 2  hoặc  pi/2, pi  (trống = vạch nguyên)")
        self.e_yt = QLineEdit()
        self.e_yt.setPlaceholderText("vd -1, 3")
        self.e_guides = QLineEdit()
        self.e_guides.setPlaceholderText("điểm gióng x;y, vd -1;3, 1;-1")
        f.addRow("Giá trị trên Ox", self.e_xt)
        f.addRow("Giá trị trên Oy", self.e_yt)
        f.addRow("Điểm gióng", self.e_guides)

    def from_extrema(self):
        from ... import drawmore as dm
        try:
            v = [float(x.replace(",", ".")) for x in self.e_ext.text().replace(" ", "").split(";") if x]
            if len(v) == 4:
                e = dm.cubic_from_extrema(*v)
                self.e_guides.setText(f"{v[0]:g};{v[1]:g}, {v[2]:g};{v[3]:g}")
            elif len(v) == 3:
                e = dm.quartic_from_extrema(*v)
                self.e_guides.setText(f"{-v[1]:g};{v[2]:g}, {v[1]:g};{v[2]:g}")
            else:
                raise dm.FuncError("Nhập 4 số (bậc ba) hoặc 3 số (trùng phương), cách nhau bằng dấu ;")
        except (dm.FuncError, ValueError) as ex:
            self._msg(str(ex), False)
            return
        self.e_gx.setText(e)
        self._msg(f"Hàm số: y = {e}")

    def _apply_graph_extras(self, code: str) -> str:
        from ... import drawmore as dm
        if not hasattr(self, "e_xt"):
            return code
        xt = dm.parse_ticks(self.e_xt.text()) if self.e_xt.text().strip() else None
        yt = dm.parse_ticks(self.e_yt.text()) if self.e_yt.text().strip() else None
        guides = []
        for part in self.e_guides.text().split(","):
            if ";" in part:
                a, b = part.split(";", 1)
                guides.append((float(a.strip().replace(" ", "")), float(b.strip())))
        return dm.customize_graph(code, xt, yt, guides) if (xt or yt or guides) else code
