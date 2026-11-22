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
        self._build_pager(gl)
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
        for text, fn in (("Điền", self.quick_fill), ("Xoá số đã nhập", self.clear_counts), ("🔄 Nạp lại (Map ID)", self.reload_map)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            q.addWidget(b)
        q.addStretch()
        lay.addLayout(q)
        row = QHBoxLayout()
        row.addStretch()
        for text, fn in (("Đưa vào ma trận (thay ma trận cũ)", lambda: self.to_matrix(True)),
                         ("Thêm vào ma trận", lambda: self.to_matrix(False))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self._init_static()

    # ---------------------------------------------------------------- dải nút và phân trang (như MyLT)
    PAGE_SIZE = 100

    def _build_pager(self, gl):
        bar = QHBoxLayout()
        tips = {"?": "Hướng dẫn", "H": "Chỉ hiện các dòng đã lấy / hiện lại tất cả", "A": "Chọn tất cả các dòng đang hiện",
                "C": "Xoá hết số câu đã nhập (Clear)", "E": "Xuất danh sách đã lấy ra Excel",
                "D": "Xoá số câu đã nhập ở các dòng đang chọn", "O": "Đưa vào ma trận rồi mở trang «Tuỳ chọn đề»",
                "U": "Hoàn tác thao tác gần nhất (Undo)"}
        fns = {"?": self.help, "H": self.toggle_taken, "A": lambda: self.t.selectAll(), "C": self.clear_counts,
               "E": self.export_xlsx, "D": self.clear_selected, "O": self.open_matrix, "U": self.undo}
        for k in "?HACEDOU":
            b = QPushButton(k)
            b.setFixedWidth(34)
            b.setToolTip(tips[k])
            b.clicked.connect(lambda _=False, f=fns[k]: f())
            bar.addWidget(b)
        bar.addStretch()
        self.l_sum = QLabel()
        bar.addWidget(self.l_sum)
        bar.addStretch()
        self.b_first, self.b_prev, self.b_next, self.b_last = (QPushButton(x) for x in ("Đầu", "Trước", "Sau", "Cuối"))
        self.cb_page = QComboBox()
        self.cb_page.setMinimumWidth(70)
        for w in (self.b_first, self.b_prev, self.cb_page, self.b_next, self.b_last):
            bar.addWidget(w)
        self.b_first.clicked.connect(lambda: self.go_page(0))
        self.b_prev.clicked.connect(lambda: self.go_page(self._page - 1))
        self.b_next.clicked.connect(lambda: self.go_page(self._page + 1))
        self.b_last.clicked.connect(lambda: self.go_page(10 ** 9))
        self.cb_page.activated.connect(lambda i: self.go_page(i))
        gl.addLayout(bar)
        self._page = 0
        self._undo: list[dict] = []
        self._page_rows = []

    def n_pages(self) -> int:
        return max(1, -(-len(self._shown) // self.PAGE_SIZE))

    def go_page(self, p: int):
        self._page = max(0, min(p, self.n_pages() - 1))
        self.apply_filter(keep_page=True)

    def push_undo(self):
        self._undo.append({k: dict(v) for k, v in self.counts.items()})
        del self._undo[:-30]

    def undo(self):
        if self._undo:
            self.counts = self._undo.pop()
            self.apply_filter(keep_page=True)

    def toggle_taken(self):
        cb = self.f["lay"]
        cb.setCurrentIndex(0 if cb.currentData() == "1" else cb.findData("1"))

    def clear_selected(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if not rows:
            return
        self.push_undo()
        for r in rows:
            if r < len(self._page_rows):
                self.counts.pop(self._page_rows[r][0], None)
        self.apply_filter(keep_page=True)

    def open_matrix(self):
        if self.to_matrix(True):
            self.win.show_panel(self.win.gen_panel)

    def export_xlsx(self):
        from PySide6.QtWidgets import QFileDialog
        rd = self.rules()
        if not rd:
            QMessageBox.information(self, "Chọn theo ID", "Chưa lấy dòng nào.")
            return
        from ...appdirs import path as app_path
        p, _ = QFileDialog.getSaveFileName(self, "Xuất danh sách đã lấy", app_path("ma_tran", "danh_sach_lay.xlsx"), "Excel (*.xlsx)")
        if not p:
            return
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.append(["Loại", "ID", "Mức độ", "Số câu"])
        for r in rd:
            ws.append([LOAI.get(r["qtype"], r["qtype"]), r["id"], r["muc_do"], r["count"]])
        wb.save(p)
        self.win.statusBar().showMessage(f"Đã xuất {len(rd)} dòng: {p}", 8000)

    def help(self):
        QMessageBox.information(self, "Tạo đề theo ID", (
            "• Gõ số câu vào các cột Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao của dòng cần lấy (không quá số câu «Đã có»).\n"
            "• «Chọn nhanh»: chọn Lớp… → Lọc; chọn Số câu và Mức độ → Lấy (đặt số câu cho mọi dòng đang hiện).\n"
            "• Nút ở dưới bảng: ? hướng dẫn · H chỉ hiện dòng đã lấy · A chọn tất cả dòng · C xoá hết số đã nhập · "
            "E xuất Excel · D xoá số ở dòng đang chọn · O đưa vào ma trận và mở «Tuỳ chọn đề» · U hoàn tác.\n"
            "• Đầu / Trước / Sau / Cuối: chuyển trang (mỗi trang %d dòng).\n• «Tạo đề» (góc dưới): tạo đề từ các dòng đã lấy." % self.PAGE_SIZE))

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
    def reload_map(self):
        """Đọc lại các file Map ID (thư mục «Map ID (DPS)», file mới đè file cũ) vào ngân hàng rồi dựng lại bảng ID."""
        from ...idmap import load_folder_maps
        m, used = load_folder_maps()
        if m and self.win.bank:
            self.win.bank.set_idmap(m)
        self.reload()
        self.win.statusBar().showMessage(
            (f"Đã nạp Map ID: {len(m)} mục từ {', '.join(used)}" if m else
             "Không thấy file Map ID trong thư mục «Map ID (DPS)» – dùng Map ID đi kèm phần mềm") +
            f" · bảng có {len(self.rows)} dòng ID", 9000)

    def reload(self):
        from ...idmap import bundled_map
        self._names = {**bundled_map(), **(self.win.bank.idmap() if self.win.bank else {})}
        pool = self.win.pool_bank()
        agg: dict[tuple, dict] = {}
        for r in (pool.id_level_stats() if pool else []):
            key = (r["lop"] or "", r["mon"] or "", r["chuong"] or "", r["bai"] or "", r["dang"] or "", r["qtype"])
            if not key[0]:                  # chưa có ID / ID không đọc được → dòng «?» (lấy ngẫu nhiên, ghi ở cột Nhận biết)
                key = ("", "", "", "", "", r["qtype"])
                agg.setdefault(key, {})["N"] = agg.get(key, {}).get("N", 0) + r["n"]
            else:
                agg.setdefault(key, {})[r["muc_do"] or "?"] = r["n"]
        self.rows = []
        names = self._names
        for (lop, mon, ch, bai, dang, qt), lv in sorted(agg.items()):
            kb = lop + mon + ch + bai
            if not lop:
                self.rows.append(((lop, mon, ch, bai, dang, qt), "Câu chưa có ID / ID không đọc được (lấy ngẫu nhiên)", lv))
                continue
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

    def apply_filter(self, _checked=False, keep_page=False):
        self._shown = self.visible_rows()
        if not keep_page:
            self._page = 0
        self._page = max(0, min(self._page, self.n_pages() - 1))
        start = self._page * self.PAGE_SIZE
        self._page_rows = self._shown[start:start + self.PAGE_SIZE]
        self.cb_page.blockSignals(True)
        self.cb_page.clear()
        for i in range(self.n_pages()):
            self.cb_page.addItem(str(i + 1))
        self.cb_page.setCurrentIndex(self._page)
        self.cb_page.blockSignals(False)
        self.b_first.setEnabled(self._page > 0)
        self.b_prev.setEnabled(self._page > 0)
        self.b_next.setEnabled(self._page < self.n_pages() - 1)
        self.b_last.setEnabled(self._page < self.n_pages() - 1)
        self.t.blockSignals(True)
        self.t.setRowCount(len(self._page_rows))
        for r, (key, idk, name, lv) in enumerate(self._page_rows):
            have = "/".join(str(lv.get(x, 0)) for x in LEVELS)
            cells = [str(start + r + 1), idk, lop_label(key[0]), key[1], key[2], name, LOAI.get(key[5], key[5]), have]
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
        if not C_LV0 <= c < C_LV0 + 4 or r >= len(self._page_rows):
            return
        key, _, _, lv = self._page_rows[r]
        self.push_undo()
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
        self.push_undo()
        """«Lấy»: với các dòng đang hiện, đặt số câu theo ô «Số câu» ở mức độ đã chọn (mọi mức nếu «Mọi mức độ»)."""
        n, muc = self.sp_n.currentData(), self.q["muc"].currentData()
        for key, _, _, lv in self._shown:
            for x in ([muc] if muc else LEVELS):
                if lv.get(x):
                    self.counts.setdefault(key, {})[x] = min(n, lv.get(x, 0))
        self.apply_filter(keep_page=True)

    def quick_fill(self):
        self.push_undo()
        x, n = self.cb_quick.currentData(), self.sp_quick.value()
        for key, _, _, lv in self._shown:
            self.counts.setdefault(key, {})[x] = min(n, lv.get(x, 0))
        self.apply_filter(keep_page=True)

    def clear_counts(self):
        self.push_undo()
        self.counts = {}
        self.apply_filter(keep_page=True)

    # ---------------------------------------------------------------- ma trận, tạo đề
    def rules(self) -> list[dict]:
        out = []
        for (lop, mon, ch, bai, dang, qt), d in sorted(self.counts.items()):
            for x in LEVELS:
                n = d.get(x, 0)
                if n and not lop:
                    out.append({"qtype": qt, "id": "?", "muc_do": "", "count": n})
                elif n:
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
