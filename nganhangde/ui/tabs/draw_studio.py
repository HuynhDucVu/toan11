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
    def preview_pdf(self):
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
                self._msg("Máy chưa cài MiKTeX/TeX Live – không xem trước được.", False)
                return
            r = compile_tex(p, eng, runs=1)
        finally:
            QApplication.restoreOverrideCursor()
        if r.ok and r.pdf:
            QDesktopServices.openUrl(QUrl.fromLocalFile(r.pdf))
            self._msg("Đã biên dịch hình.")
        else:
            self._msg(r.summary(), False)
