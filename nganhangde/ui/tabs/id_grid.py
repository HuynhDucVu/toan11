"""Trộn đề → «Tạo đề theo ID» (như MyLT 2026): khung «Chọn nhanh» (Lớp, Môn, Chương, Bài, Dạng, Mức độ, Loại, Số câu → Lọc /
Lấy) và bảng «Chọn theo ID» liệt kê mọi dạng (lớp – môn – chương – bài – dạng) có trong nguồn câu hỏi (ngân hàng hoặc các file),
số câu có sẵn từng mức độ N/H/V/C; nhập số câu muốn lấy ở từng mức độ → ma trận (mỗi ô ≠ 0 là một dòng) rồi tạo đề."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QWidget)

if TYPE_CHECKING:
    from ..main_window import MainWindow

LEVELS = ["N", "H", "V", "C"]
LEVEL_NAMES = ("Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao")
LOAI = {"TN": "TN", "DS": "ĐS", "KQ": "SA", "TL": "TL"}           # tên loại như MyLT: SA = trả lời ngắn
COLS = ["STT", "ID", "Lớp", "Môn", "Chương", "Bài, dạng", "Loại", "Đã có (N/H/V/C)", "Nhận biết", "Thông hiểu", "Vận dụng",
        "Vận dụng cao", "Tổng lấy"]
C_LV0 = 8            # cột đầu của 4 cột mức độ
C_TOTAL = 12


def lop_label(code: str) -> str:
    return str(10 + int(code)) if code.isdigit() and int(code) <= 2 else code


class IdGridPanel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        self.rows = []                      # [((lop, mon, chuong, bai, dang, qtype), tên bài/dạng, {mức: n})]
        self._shown = []
        self.counts: dict[tuple, dict] = {}
        self._names: dict[str, str] = {}
        lay = QVBoxLayout(self)

        # ---------------- Chọn nhanh
        g = QGroupBox("Chọn nhanh")
        gl = QGridLayout(g)
        self.q = {}
        spec = (("lop", "Lớp", 0, 0), ("mon", "Môn", 1, 0), ("chuong", "Chương", 2, 0),
                ("bai", "Bài", 0, 2), ("dang", "Dạng", 1, 2), ("muc", "Mức độ", 2, 2))
        for key, text, r, c in spec:
            cb = QComboBox()
            cb.setMinimumWidth(150)
            self.q[key] = cb
            gl.addWidget(QLabel(text), r, c)
            gl.addWidget(cb, r, c + 1)
        self.q["loai"] = QComboBox()
        self.sp_n = QComboBox()
        for n in (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20):
            self.sp_n.addItem(str(n), n)
        gl.addWidget(QLabel("Loại"), 0, 4)
        gl.addWidget(self.q["loai"], 0, 5)
        gl.addWidget(QLabel("Số câu"), 1, 4)
        gl.addWidget(self.sp_n, 1, 5)
        b_loc, b_lay = QPushButton("Lọc"), QPushButton("Lấy")
        gl.addWidget(b_loc, 2, 4)
        gl.addWidget(b_lay, 2, 5)
        gl.setColumnStretch(1, 1)
        gl.setColumnStretch(3, 1)
        b_loc.clicked.connect(self.apply_filter)
        b_lay.clicked.connect(self.take_quick)
        for key in ("lop", "mon", "chuong", "bai"):
            self.q[key].currentIndexChanged.connect(lambda _=0, k=key: self._cascade(k))
        lay.addWidget(g)

        # ---------------- Chọn theo ID
        g = QGroupBox("Chọn theo ID")
        gl = QVBoxLayout(g)
        f = QHBoxLayout()
        self.cb_conv = QComboBox()
        self.cb_conv.addItem("ID hiện có")
        self.cb_conv.setToolTip("Chuyển ID sang chương trình khác (KNTT/CTST/CD) cần bảng ConvID của MyLT – chưa có")
        self.cb_conv.setEnabled(False)
        f.addWidget(QLabel("Chuyển ID"))
        f.addWidget(self.cb_conv)
        b = QPushButton("Lọc")
        b.clicked.connect(self.apply_filter)
        f.addWidget(b)
        self.f = {}
        for key, text in (("lop", "Lớp"), ("mon", "Môn"), ("chuong", "Chương"), ("bai", "Bài"), ("loai", "Loại"),
                          ("kieu", "Kiểu ID"), ("lay", "Đã lấy")):
            cb = QComboBox()
            self.f[key] = cb
            f.addWidget(QLabel(text))
            f.addWidget(cb, 3 if key in ("chuong", "bai") else 0)
            cb.currentIndexChanged.connect(lambda _=0: self.apply_filter())
        self.e_find = QLineEdit()
        self.e_find.setPlaceholderText("tìm ID/tên (không dấu cũng được)")
        self.e_find.returnPressed.connect(self.apply_filter)
        f.addWidget(self.e_find, 2)
        gl.addLayout(f)
        self.t = QTableWidget(0, len(COLS))
        self.t.setHorizontalHeaderLabels(COLS)
        self.t.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.itemChanged.connect(self._changed)
        for c, w in ((0, 40), (1, 90), (2, 40), (3, 40), (4, 60), (6, 50), (7, 110), (8, 78), (9, 78), (10, 78), (11, 90), (12, 70)):
            self.t.setColumnWidth(c, w)
        gl.addWidget(self.t, 1)
        lay.addWidget(g, 1)

        # ---------------- dưới
        q = QHBoxLayout()
        q.addWidget(QLabel("Điền nhanh: mỗi dòng đang hiện lấy"))
        self.sp_quick = QSpinBox()
        self.sp_quick.setRange(0, 20)
        self.sp_quick.setValue(1)
        q.addWidget(self.sp_quick)
        q.addWidget(QLabel("câu mức"))
        self.cb_quick = QComboBox()
        for lv, name in zip(LEVELS, LEVEL_NAMES):
            self.cb_quick.addItem(name, lv)
        q.addWidget(self.cb_quick)
        for text, fn in (("Điền", self.quick_fill), ("Xoá số đã nhập", self.clear_counts), ("🔄 Nạp lại", self.reload)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            q.addWidget(b)
        q.addStretch()
        lay.addLayout(q)
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
        self._init_static()

    # ---------------------------------------------------------------- bộ lọc
    def _init_static(self):
        for cb in (self.q["loai"], self.f["loai"]):
            cb.addItem("Mọi loại", "")
            for k, v in LOAI.items():
                cb.addItem(v, k)
        self.q["muc"].addItem("Mọi mức độ", "")
        for lv, name in zip(LEVELS, LEVEL_NAMES):
            self.q["muc"].addItem(name, lv)
        for t, d in (("Tất cả", ""), ("ID6 (có dạng)", "6"), ("ID5 (không dạng)", "5")):
            self.f["kieu"].addItem(t, d)
        for t, d in (("Tất cả", ""), ("Đã lấy", "1"), ("Chưa lấy", "0")):
            self.f["lay"].addItem(t, d)

    def _fill(self, cb: QComboBox, items, all_text: str):
        cur = cb.currentData()
        cb.blockSignals(True)
        cb.clear()
        cb.addItem(all_text, "")
        for data, text in items:
            cb.addItem(text, data)
        cb.setCurrentIndex(max(0, cb.findData(cur)))
        cb.blockSignals(False)

    def _cascade(self, changed: str):
        """Chọn Lớp → chỉ còn Môn thuộc lớp đó… (các ô phía dưới trong khung «Chọn nhanh»); rồi lọc bảng."""
        order = ["lop", "mon", "chuong", "bai", "dang"]
        all_text = {"lop": "Mọi lớp", "mon": "Mọi môn", "chuong": "Mọi chương", "bai": "Mọi bài", "dang": "Mọi dạng"}
        keys = [k for k, _, _ in self.rows]
        for k in order[order.index(changed) + 1:]:
            def ok(key):
                for up in order[:order.index(k)]:
                    cb = self.q.get(up)
                    v = (cb.currentData() if cb is not None else "") or ""
                    if v and self._value(key, up) != v:
                        return False
                return True
            vals = sorted({self._value(key, k) for key in keys if ok(key)} - {""})
            self._fill(self.q[k], [(v, self._label(k, v)) for v in vals], all_text[k])
        self.apply_filter()

    @staticmethod
    def _value(key, k):
        lop, mon, ch, bai, dang = key[:5]
        if k == "lop":
            return lop
        if k == "mon":
            return lop + mon
        if k == "chuong":
            return lop + mon + ch
        if k == "bai":
            return lop + mon + ch + bai
        return lop + mon + ch + bai + "-" + dang if dang else ""

    def _label(self, k, v):
        n = self._names
        if k == "lop":
            return f"Lớp {lop_label(v)}"
        if k == "mon":
            return n.get(v) or f"Môn {v[1:]}"
        if k == "chuong":
            return f"{v[2:]}. {n.get(v, 'Chương ' + v[2:])}"
        if k == "bai":
            return f"Bài {v[3:]}: {n.get(v, '')}".strip().rstrip(":")
        return f"Dạng {v.split('-')[-1]}: {n.get(v, '')}".strip().rstrip(":")

    # ---------------------------------------------------------------- dữ liệu
    def reload(self):
        self._names = self.win.bank.idmap() if self.win.bank else {}
        pool = self.win.pool_bank()
        agg: dict[tuple, dict] = {}
        for r in (pool.id_level_stats() if pool else []):
            key = (r["lop"] or "", r["mon"] or "", r["chuong"] or "", r["bai"] or "", r["dang"] or "", r["qtype"])
            agg.setdefault(key, {})[r["muc_do"] or "?"] = r["n"]
        self.rows = []
        names = self._names
        for (lop, mon, ch, bai, dang, qt), lv in sorted(agg.items()):
            kb = lop + mon + ch + bai
            name = " › ".join(x for x in (names.get(kb, f"Bài {bai}"), names.get(f"{kb}-{dang}", f"Dạng {dang}" if dang
                                                                                  else "")) if x)
            self.rows.append(((lop, mon, ch, bai, dang, qt), name, lv))
        keys = [k for k, _, _ in self.rows]
        for k, all_text in (("lop", "Mọi lớp"), ("mon", "Mọi môn"), ("chuong", "Mọi chương"), ("bai", "Mọi bài"),
                            ("dang", "Mọi dạng")):
            vals = sorted({self._value(key, k) for key in keys} - {""})
            items = [(v, self._label(k, v)) for v in vals]
            if k in self.q:
                self._fill(self.q[k], items, all_text)
            if k in self.f:
                self._fill(self.f[k], items, all_text)
        self.apply_filter()

    def _passes(self, key, name, lv, idk, find):
        from ...textnorm import unaccent
        lop, mon, ch, bai, dang, qt = key
        for src in (self.q, self.f):
            for k, part in (("lop", lop), ("mon", lop + mon), ("chuong", lop + mon + ch), ("bai", lop + mon + ch + bai),
                            ("dang", lop + mon + ch + bai + "-" + dang)):
                cb = src.get(k)
                v = cb.currentData() if cb is not None else ""
                if v and part != v:
                    return False
            lo = src["loai"].currentData()
            if lo and qt != lo:
                return False
        ki = self.f["kieu"].currentData()
        if ki == "6" and not dang or ki == "5" and dang:
            return False
        got = sum(self.counts.get(key, {}).values())
        la = self.f["lay"].currentData()
        if la == "1" and not got or la == "0" and got:
            return False
        if find and find not in unaccent(f"{idk} {name}".lower()):
            return False
        return True

    def visible_rows(self):
        from ...textnorm import unaccent
        find = unaccent(self.e_find.text().strip().lower())
        out = []
        for key, name, lv in self.rows:
            idk = key[0] + key[1] + key[2] + "?" + key[3] + (f"-{key[4]}" if key[4] else "")
            if self._passes(key, name, lv, idk, find):
                out.append((key, idk, name, lv))
        return out

    def apply_filter(self):
        self._shown = self.visible_rows()
        self.t.blockSignals(True)
        self.t.setRowCount(len(self._shown))
        for r, (key, idk, name, lv) in enumerate(self._shown):
            have = "/".join(str(lv.get(x, 0)) for x in LEVELS)
            cells = [str(r + 1), idk, lop_label(key[0]), key[1], key[2], name, LOAI.get(key[5], key[5]), have]
            for c, v in enumerate(cells):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if c in (0, 2, 3, 4, 6, 7):
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.t.setItem(r, c, it)
            for j, x in enumerate(LEVELS):
                n = self.counts.get(key, {}).get(x, 0)
                it = QTableWidgetItem(str(n) if n else "")
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if not lv.get(x):
                    it.setFlags(Qt.ItemFlag.ItemIsSelectable)
                    it.setBackground(QColor("#eeeeee"))
                self.t.setItem(r, C_LV0 + j, it)
            it = QTableWidgetItem(str(sum(self.counts.get(key, {}).values())))
            it.setFlags(Qt.ItemFlag.ItemIsEnabled)
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.t.setItem(r, C_TOTAL, it)
        self.t.blockSignals(False)
        self._summary()

    def _changed(self, it):
        c, r = it.column(), it.row()
        if not C_LV0 <= c < C_LV0 + 4 or r >= len(self._shown):
            return
        key, _, _, lv = self._shown[r]
        x = LEVELS[c - C_LV0]
        try:
            n = max(0, int(it.text().strip() or 0))
        except ValueError:
            n = 0
        n = min(n, lv.get(x, 0))
        self.counts.setdefault(key, {})[x] = n
        self.t.blockSignals(True)
        it.setText(str(n) if n else "")
        it.setForeground(QColor("#c00000") if n and n == lv.get(x, 0) else QColor("black"))
        self.t.item(r, C_TOTAL).setText(str(sum(self.counts[key].values())))
        self.t.blockSignals(False)
        self._summary()

    def _summary(self):
        tot = {}
        for key, d in self.counts.items():
            tot[key[5]] = tot.get(key[5], 0) + sum(d.values())
        self.l_sum.setText("Đã chọn: " + (" · ".join(f"{LOAI.get(k, k)} {v}" for k, v in tot.items() if v) or "chưa có") +
                           f" · tổng <b>{sum(tot.values())}</b> câu · đang hiện {len(self._shown)} dòng")

    def take_quick(self):
        """«Lấy»: với các dòng đang hiện, đặt số câu theo ô «Số câu» ở mức độ đã chọn (mọi mức nếu «Mọi mức độ»)."""
        n, muc = self.sp_n.currentData(), self.q["muc"].currentData()
        for key, _, _, lv in self._shown:
            for x in ([muc] if muc else LEVELS):
                if lv.get(x):
                    self.counts.setdefault(key, {})[x] = min(n, lv.get(x, 0))
        self.apply_filter()

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
