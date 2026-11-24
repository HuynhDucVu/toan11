"""Tab «Vẽ hình»: dựng hình phẳng theo từng bước, xem trước ngay, sinh mã TikZ; kèm hình khối có sẵn."""
from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QWidget)

from ... import geom
from ..common import latex_editor

if TYPE_CHECKING:
    from ..main_window import MainWindow


class GeomView(QWidget):
    def __init__(self):
        super().__init__()
        self.scene = None
        self.setMinimumSize(320, 260)

    def show_scene(self, scene):
        self.scene = scene
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        S = self.scene
        if not S or not (S.pts or S.items):
            p.setPen(QColor("#888"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Thêm bước hoặc chọn hình mẫu")
            return
        x0, y0, x1, y1 = S.bbox()
        pad = 0.6
        sx = (self.width() - 30) / max(x1 - x0 + 2 * pad, 1e-6)
        sy = (self.height() - 30) / max(y1 - y0 + 2 * pad, 1e-6)
        k = min(sx, sy)

        def T(pt):
            return QPointF(15 + (pt[0] - x0 + pad) * k, self.height() - 15 - (pt[1] - y0 + pad) * k)
        solid, dash = QPen(QColor("black"), 1.6), QPen(QColor("black"), 1.4, Qt.PenStyle.DashLine)
        for kind, d in S.items:
            if kind == "fill":
                path = QPainterPath(T(d["pts"][0]))
                for q in d["pts"][1:]:
                    path.lineTo(T(q))
                path.closeSubpath()
                p.fillPath(path, QBrush(QColor(120, 160, 230, 70)))
        for kind, d in S.items:
            p.setPen(dash if d.get("dash") else solid)
            if kind == "seg":
                p.drawLine(T(d["a"]), T(d["b"]))
                if d.get("label"):
                    m = ((d["a"][0] + d["b"][0]) / 2, (d["a"][1] + d["b"][1]) / 2)
                    p.drawText(T(m) + QPointF(4, -4), d["label"])
            elif kind == "line":
                a, b = d["a"], d["b"]
                dx, dy = b[0] - a[0], b[1] - a[1]
                p.drawLine(T((a[0] - dx * 3, a[1] - dy * 3)), T((b[0] + dx * 3, b[1] + dy * 3)))
            elif kind == "poly":
                pts = [T(q) for q in d["pts"]]
                for i in range(len(pts)):
                    p.drawLine(pts[i], pts[(i + 1) % len(pts)])
            elif kind in ("circle", "ellipse"):
                c = T(d["c"])
                p.drawEllipse(c, d["rx"] * k, d["ry"] * k)
            elif kind == "curve":
                pts = [T(q) for q in d["pts"]]
                for i in range(len(pts) - 1):
                    p.drawLine(pts[i], pts[i + 1])
            elif kind == "right":
                b = d["b"]
                u, v = geom._unit(b, d["a"], 0.25), geom._unit(b, d["c"], 0.25)
                p.drawPolyline([T((b[0] + u[0], b[1] + u[1])), T((b[0] + u[0] + v[0], b[1] + u[1] + v[1])),
                                T((b[0] + v[0], b[1] + v[1]))])
            elif kind == "angle":
                b = T(d["b"])
                r = 0.4 * k
                t1 = math.degrees(math.atan2(d["a"][1] - d["b"][1], d["a"][0] - d["b"][0]))
                t2 = math.degrees(math.atan2(d["c"][1] - d["b"][1], d["c"][0] - d["b"][0]))
                span = (t2 - t1) % 360
                if span > 180:
                    t1, span = t2, 360 - span
                p.drawArc(QRectF(b.x() - r, b.y() - r, 2 * r, 2 * r), int(t1 * 16), int(span * 16))
            elif kind == "ticks":
                a, b = d["a"], d["b"]
                m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                ux, uy = geom._unit(a, b, 1)
                for j in range(d["n"]):
                    off = (j - (d["n"] - 1) / 2) * 0.07
                    c = (m[0] + ux * off, m[1] + uy * off)
                    p.drawLine(T((c[0] + uy * 0.1, c[1] - ux * 0.1)), T((c[0] - uy * 0.1, c[1] + ux * 0.1)))
            elif kind == "text":
                p.drawText(T(d["at"]), d["text"])
        p.setBrush(QColor("black"))
        cx = sum(q[0] for q in S.pts.values()) / max(1, len(S.pts))
        cy = sum(q[1] for q in S.pts.values()) / max(1, len(S.pts))
        for n, q in S.pts.items():
            pt = T(q)
            p.drawEllipse(pt, 2.5, 2.5)
            ang = math.atan2(q[1] - cy, q[0] - cx)
            p.drawText(pt + QPointF(12 * math.cos(ang) - 4, -12 * math.sin(ang) + 4), n)


class GeomPanel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        self.steps: list[dict] = []
        outer = QHBoxLayout(self)
        sp = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(sp)
        left = QWidget()
        lv = QVBoxLayout(left)
        g = QGroupBox("Thêm bước")
        gf = QVBoxLayout(g)
        row = QHBoxLayout()
        self.cb_kind = QComboBox()
        for k, (name, _) in geom.KINDS.items():
            self.cb_kind.addItem(name, k)
        self.cb_kind.currentIndexChanged.connect(self._fields)
        row.addWidget(self.cb_kind, 1)
        self.cb_tpl = QComboBox()
        self.cb_tpl.addItem("— Hình mẫu —", "")
        for name in geom.TEMPLATES:
            self.cb_tpl.addItem(name, name)
        self.cb_tpl.activated.connect(self.load_template)
        row.addWidget(self.cb_tpl, 1)
        gf.addLayout(row)
        self.form = QFormLayout()
        gf.addLayout(self.form)
        b = QPushButton("➕ Thêm bước")
        b.setObjectName("primary")
        b.clicked.connect(self.add_step)
        gf.addWidget(b)
        lv.addWidget(g)
        self.t = QTableWidget(0, 2)
        self.t.setHorizontalHeaderLabels(["#", "Bước đã vẽ"])
        self.t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.doubleClicked.connect(self.edit_step)
        self.t.verticalHeader().setVisible(False)
        lv.addWidget(self.t, 1)
        row = QHBoxLayout()
        for text, fn in (("▲", lambda: self.move(-1)), ("▼", lambda: self.move(1)), ("Sửa", self.edit_step),
                         ("Xoá", self.delete), ("Hình mới", self.new), ("Mở…", self.open), ("Lưu…", self.save_steps)):
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            row.addWidget(bb)
        lv.addLayout(row)
        sp.addWidget(left)
        right = QWidget()
        rv = QVBoxLayout(right)
        self.view = GeomView()
        rv.addWidget(self.view, 3)
        self.code = latex_editor()
        rv.addWidget(self.code, 2)
        row = QHBoxLayout()
        for text, fn in (("📋 Chép mã", self.copy), ("Xem trước PDF", self.preview)):
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            row.addWidget(bb)
        self.l_msg = QLabel()
        row.addWidget(self.l_msg, 1)
        rv.addLayout(row)
        sp.addWidget(right)
        sp.setSizes([480, 640])
        self.edits = {}
        self._editing = None
        self._fields()

    def _fields(self):
        while self.form.rowCount():
            self.form.removeRow(0)
        self.edits = {}
        for f in geom.KINDS[self.cb_kind.currentData()][1]:
            e = QLineEdit()
            if f == "net":
                e.setPlaceholderText("lien hoặc dut")
            self.edits[f] = e
            self.form.addRow(geom.FIELD_LABEL.get(f, f), e)

    def _msg(self, text, ok=True):
        self.l_msg.setText(f"<span style='color:{'#0b7a0b' if ok else '#c00000'}'>{text}</span>")

    def redraw(self):
        self.t.setRowCount(len(self.steps))
        for i, st in enumerate(self.steps):
            self.t.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.t.setItem(i, 1, QTableWidgetItem(geom.describe(st)))
        try:
            sc = geom.build(self.steps)
        except geom.FuncError as e:
            self._msg(str(e), False)
            return
        self.view.show_scene(sc)
        self.code.setPlainText(sc.tikz() if self.steps else "")
        self._msg(f"{len(sc.pts)} điểm, {len(sc.items)} nét." if self.steps else "")

    def add_step(self):
        st = {"kind": self.cb_kind.currentData(), **{k: e.text().strip() for k, e in self.edits.items()}}
        try:
            geom.build(self.steps + [st])
        except geom.FuncError as e:
            self._msg(str(e), False)
            return
        if self._editing is not None:
            self.steps[self._editing] = st
            self._editing = None
        else:
            self.steps.append(st)
        for e in self.edits.values():
            e.clear()
        self.redraw()

    def edit_step(self, *_):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if not rows:
            return
        st = self.steps[rows[0]]
        self.cb_kind.setCurrentIndex(self.cb_kind.findData(st["kind"]))
        for k, e in self.edits.items():
            e.setText(str(st.get(k, "")))
        self._editing = rows[0]
        self._msg(f"Đang sửa bước {rows[0] + 1} – chỉnh rồi bấm «Thêm bước» để lưu.")

    def move(self, d):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if len(rows) == 1 and 0 <= rows[0] + d < len(self.steps):
            r = rows[0]
            self.steps[r], self.steps[r + d] = self.steps[r + d], self.steps[r]
            self.redraw()
            self.t.selectRow(r + d)

    def delete(self):
        for r in sorted({i.row() for i in self.t.selectedIndexes()}, reverse=True):
            del self.steps[r]
        self.redraw()

    def new(self):
        self.steps = []
        self.redraw()

    def load_template(self):
        name = self.cb_tpl.currentData()
        if name:
            self.steps = [dict(s) for s in geom.TEMPLATES[name]]
            self.redraw()

    def save_steps(self):
        p, _ = QFileDialog.getSaveFileName(self, "Lưu các bước", "hinh.json", "Bước vẽ (*.json)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(self.steps, f, ensure_ascii=False, indent=1)

    def open(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở bước vẽ", "", "Bước vẽ (*.json)")
        if p:
            with open(p, encoding="utf-8") as f:
                self.steps = json.load(f)
            self.redraw()

    def copy(self):
        QApplication.clipboard().setText(self.code.toPlainText())
        self._msg("Đã chép mã TikZ.")

    def preview(self):
        from .draw_studio import DrawStudioMixin
        DrawStudioMixin.preview_pdf(self)
