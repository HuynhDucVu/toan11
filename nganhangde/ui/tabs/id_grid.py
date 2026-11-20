"""Trộn đề → «Chọn theo ID»: bảng mọi dạng (lớp – môn – chương – bài – dạng) có trong kho, số câu có sẵn từng mức độ
N/H/V/C; gõ số câu muốn lấy ở từng mức độ → thành ma trận (mỗi ô ≠ 0 là một dòng ma trận) rồi tạo đề."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ..common import TEN_LOAI

if TYPE_CHECKING:
    from ..main_window import MainWindow

LEVELS = ["N", "H", "V", "C"]
COLS = ["ID", "Bài › dạng", "Loại", "Có N/H/V/C", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao", "Tổng có",
        "Tổng lấy"]


class IdGridPanel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        self.rows = []                      # [(khoá ID không mức độ, lop, mon, chuong, bai, dang, qtype, {mức: n})]
        lay = QVBoxLayout(self)
        f = QHBoxLayout()
        self.cb_lop = QComboBox()
        self.cb_type = QComboBox()
        self.cb_type.addItem("Mọi loại", "")
        for k, v in TEN_LOAI.items():
            self.cb_type.addItem(v, k)
        self.e_find = QLineEdit()
        self.e_find.setPlaceholderText("lọc theo ID hoặc tên bài/dạng (không dấu cũng được)")
        self.cb_taken = QComboBox()
        for t, d in (("Tất cả dạng", ""), ("Dạng đã lấy", "1"), ("Dạng chưa lấy", "0")):
            self.cb_taken.addItem(t, d)
        for w_, lab in ((self.cb_lop, "Lớp"), (self.cb_type, "Loại"), (self.e_find, "Tìm"), (self.cb_taken, "")):
            if lab:
                f.addWidget(QLabel(lab))
            f.addWidget(w_, 2 if w_ is self.e_find else 0)
        b = QPushButton("Lọc")
        b.clicked.connect(self.apply_filter)
        f.addWidget(b)
        b = QPushButton("🔄 Nạp lại từ kho")
        b.clicked.connect(self.reload)
        f.addWidget(b)
        lay.addLayout(f)
        q = QHBoxLayout()
        q.addWidget(QLabel("Lấy nhanh: mỗi dạng đang hiện lấy"))
        self.sp_quick = QSpinBox()
        self.sp_quick.setRange(0, 20)
        self.sp_quick.setValue(1)
        q.addWidget(self.sp_quick)
        q.addWidget(QLabel("câu mức"))
        self.cb_quick = QComboBox()
        for lv, name in zip(LEVELS, ("Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao")):
            self.cb_quick.addItem(name, lv)
        q.addWidget(self.cb_quick)
        b = QPushButton("Điền")
        b.clicked.connect(self.quick_fill)
        q.addWidget(b)
        b = QPushButton("Xoá số đã nhập")
        b.clicked.connect(self.clear_counts)
        q.addWidget(b)
        q.addStretch()
        lay.addLayout(q)
        self.t = QTableWidget(0, len(COLS))
        self.t.setHorizontalHeaderLabels(COLS)
        self.t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.itemChanged.connect(self._changed)
        lay.addWidget(self.t, 1)
        row = QHBoxLayout()
        self.l_sum = QLabel()
        row.addWidget(self.l_sum)
        row.addStretch()
        for text, fn, prim in (("Đưa vào ma trận (thay ma trận cũ)", lambda: self.to_matrix(True), False),
                               ("Thêm vào ma trận", lambda: self.to_matrix(False), False),
                               ("TẠO ĐỀ NGAY", self.generate, True)):
            b = QPushButton(text)
            if prim:
                b.setObjectName("primary")
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self.counts: dict[tuple, dict] = {}

    # ---------------------------------------------------------------- dữ liệu
    def reload(self):
        names = self.win.bank.idmap()
        agg: dict[tuple, dict] = {}
        for r in self.win.bank.id_level_stats():
            key = (r["lop"] or "", r["mon"] or "", r["chuong"] or "", r["bai"] or "", r["dang"] or "", r["qtype"])
            agg.setdefault(key, {})[r["muc_do"] or "?"] = r["n"]
        self.rows = []
        for (lop, mon, ch, bai, dang, qt), lv in sorted(agg.items()):
            kb = lop + mon + ch + bai
            name = " › ".join(x for x in (names.get(kb, f"Bài {bai}"), names.get(f"{kb}-{dang}", f"Dạng {dang}" if dang
                                                                                  else "")) if x)
            self.rows.append(((lop, mon, ch, bai, dang, qt), name, lv))
        lops = sorted({k[0] for k, _, _ in self.rows})
        cur = self.cb_lop.currentData()
        self.cb_lop.blockSignals(True)
        self.cb_lop.clear()
        self.cb_lop.addItem("Mọi lớp", "")
        for x in lops:
            self.cb_lop.addItem(names.get(x) or f"Lớp {x}", x)
        self.cb_lop.setCurrentIndex(max(0, self.cb_lop.findData(cur)))
        self.cb_lop.blockSignals(False)
        self.apply_filter()

    def visible_rows(self):
        from ...textnorm import unaccent
        lop, qt, taken = self.cb_lop.currentData(), self.cb_type.currentData(), self.cb_taken.currentData()
        find = unaccent(self.e_find.text().strip().lower())
        out = []
        for key, name, lv in self.rows:
            idk = key[0] + key[1] + key[2] + key[3] + (f"-{key[4]}" if key[4] else "")
            if lop and key[0] != lop or qt and key[5] != qt:
                continue
            if find and find not in unaccent(f"{idk} {name}".lower()):
                continue
            got = sum(self.counts.get(key, {}).values())
            if taken == "1" and not got or taken == "0" and got:
                continue
            out.append((key, idk, name, lv))
        return out

    def apply_filter(self):
        self._shown = self.visible_rows()
        self.t.blockSignals(True)
        self.t.setRowCount(len(self._shown))
        for r, (key, idk, name, lv) in enumerate(self._shown):
            have = "/".join(str(lv.get(x, 0)) for x in LEVELS)
            cells = [idk, name, TEN_LOAI.get(key[5], key[5]), have]
            for c, v in enumerate(cells):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.t.setItem(r, c, it)
            for j, x in enumerate(LEVELS):
                n = self.counts.get(key, {}).get(x, 0)
                it = QTableWidgetItem(str(n) if n else "")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not lv.get(x):
                    it.setFlags(Qt.ItemFlag.ItemIsSelectable)
                    it.setBackground(QColor("#eeeeee"))
                self.t.setItem(r, 4 + j, it)
            for c, v in ((8, sum(v for k, v in lv.items() if k in LEVELS)), (9, sum(self.counts.get(key, {}).values()))):
                it = QTableWidgetItem(str(v))
                it.setFlags(Qt.ItemFlag.ItemIsEnabled)
                self.t.setItem(r, c, it)
        self.t.blockSignals(False)
        self._summary()

    def _changed(self, it):
        c, r = it.column(), it.row()
        if not 4 <= c <= 7 or r >= len(self._shown):
            return
        key, _, _, lv = self._shown[r]
        x = LEVELS[c - 4]
        try:
            n = max(0, int(it.text().strip() or 0))
        except ValueError:
            n = 0
        n = min(n, lv.get(x, 0))
        self.counts.setdefault(key, {})[x] = n
        self.t.blockSignals(True)
        it.setText(str(n) if n else "")
        it.setForeground(QColor("#c00000") if n and n == lv.get(x, 0) else QColor("black"))
        self.t.item(r, 9).setText(str(sum(self.counts[key].values())))
        self.t.blockSignals(False)
        self._summary()

    def _summary(self):
        tot = {}
        for key, d in self.counts.items():
            tot[key[5]] = tot.get(key[5], 0) + sum(d.values())
        self.l_sum.setText("Đã chọn: " + (" · ".join(f"{TEN_LOAI[k]} {v}" for k, v in tot.items() if v) or "chưa có") +
                           f" · tổng <b>{sum(tot.values())}</b> câu")

    def quick_fill(self):
        x, n = self.cb_quick.currentData(), self.sp_quick.value()
        for key, _, _, lv in self._shown:
            self.counts.setdefault(key, {})[x] = min(n, lv.get(x, 0))
        self.apply_filter()

    def clear_counts(self):
        self.counts = {}
        self.apply_filter()

    # ---------------------------------------------------------------- ma trận, tạo đề
    def rules(self) -> list[dict]:
        out = []
        for (lop, mon, ch, bai, dang, qt), d in sorted(self.counts.items()):
            for x in LEVELS:
                n = d.get(x, 0)
                if n:
                    out.append({"qtype": qt, "id": f"{lop}{mon}{ch}{x}{bai}" + (f"-{dang}" if dang else ""),
                                "muc_do": x, "count": n})
        order = {"TN": 0, "DS": 1, "KQ": 2, "TL": 3}
        return sorted(out, key=lambda r: order.get(r["qtype"], 9))

    def to_matrix(self, replace: bool) -> bool:
        rd = self.rules()
        if not rd:
            QMessageBox.information(self, "Chọn theo ID", "Chưa nhập số câu cần lấy ở dạng nào.")
            return False
        gp = self.win.gen_panel
        if replace:
            gp.t.setRowCount(0)
        for r in rd:
            gp.add_row(r)
        gp.update_avail()
        self.win.statusBar().showMessage(f"Đã đưa {len(rd)} dòng vào ma trận (tab Theo ma trận ID).", 8000)
        return True

    def generate(self):
        if self.to_matrix(True):
            self.win.show_panel(self.win.gen_panel)
            self.win.gen_panel.generate()

    def showEvent(self, e):
        super().showEvent(e)
        if not self.rows:
            self.reload()
