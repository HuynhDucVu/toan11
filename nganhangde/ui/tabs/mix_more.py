"""Các cách trộn đề khác (dùng chung thông tin đề, thư mục xuất và tuỳ chọn trộn của tab «Theo ma trận»):

* Tự chọn câu – nhặt từng câu trong kho vào «giỏ đề» rồi trộn;
* Theo file    – trộn trực tiếp file đề .tex (hỗ trợ %VUNG để trộn trong từng vùng);
* Đề tương tự  – từ một đề mẫu, mỗi câu được thay bằng câu cùng ID trong kho.
"""
from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

from ...generator import MixOptions, mix_versions, sections_from_questions, similar_exam
from ...parser import parse_file

if TYPE_CHECKING:
    from ..main_window import MainWindow


def export_with_gen_options(win, versions, title="Kết quả trộn đề", log_rules=None, files_pdf=None):
    """Xuất các mã đề bằng thông tin đầu đề, thư mục, mẫu và tuỳ chọn của tab Tạo đề; mở hộp kết quả."""
    from ...exporter import export_versions
    from ..dialogs.result import ResultDialog
    gp = win.gen_panel
    out = gp.e_out[0].text()
    try:
        files = export_versions(versions, out, template_path=gp.e_tpl[0].text() or None, ten_de=gp.e_ten.text(),
                        truong=gp.e_truong.text(), thoi_gian=gp.e_tg.value(), options=gp.export_options())
    except (OSError, ValueError) as e:
        QMessageBox.critical(win, title, str(e))
        return False
    if files_pdf is None:
        files_pdf = gp.c_pdf.isChecked()
    ids = {q.db_id for v in versions for q in v.all_questions() if q.db_id is not None}
    if ids:
        win.pool_bank().mark_used(ids)
        win.pool_bank().log_batch(versions, ten_de=gp.e_ten.text(), matrix=log_rules or [], out_dir=out)
    gp.opts.save()
    extra = ""
    if files_pdf and win.engine(quiet=True):
        res = win.build_pdfs([f for f in files if f.endswith(".tex")], "Biên dịch đề ra PDF", open_single=False)
        extra = f"<p><b>Biên dịch PDF:</b> {sum(r.ok for r in res)}/{len(res)} file thành công.</p>"
    ResultDialog(win, versions, out, extra, gp.export_options().omr_capacity).exec()
    return True


def _codes_row(parent):
    sp = QSpinBox()
    sp.setRange(1, 99)
    sp.setValue(4)
    return sp


LEVEL_NAMES = {"N": "[N] Nhận biết", "H": "[H] Thông hiểu", "V": "[V] Vận dụng", "C": "[C] Vận dụng cao"}
LOAI_ITEMS = (("TN", "TN"), ("TL", "TL"), ("ĐS", "DS"), ("SA", "KQ"))
LOAI_SHOW = {"TN": "TN", "TL": "TL", "DS": "ĐS", "KQ": "SA"}


def one_line(text: str, n: int = 260) -> str:
    return " ".join((text or "").split())[:n]


class _Base(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win

    def codes(self, n=None):
        """Danh sách mã đề: «Mã đề tự nhập» nếu có, không thì sinh theo «Số đề tạo ra» và cách đánh mã ở tab Tuỳ chọn đề."""
        gp = self.win.gen_panel
        manual = gp.codes()
        if manual:
            return manual
        op = getattr(self.win, "opt_panel", None)
        return gp.opts.codes(n or (op.n_codes() if op is not None else gp.e_n.value()))

    def mix_opt(self) -> MixOptions:
        return self.win.gen_panel.opts.mix_options()

    def sync_options(self):
        op = getattr(self.win, "opt_panel", None)
        if op is not None:
            op.apply()


class PickPanel(_Base):
    """Tạo đề tự chọn (như MyLT 2026): lọc câu → bảng «STT | Nội dung câu hỏi | Loại | ID | Chọn» có phân trang → Tạo đề."""

    PAGE = 50

    def __init__(self, win):
        super().__init__(win)
        self.chosen: dict = {}            # db_id -> Question, giữ thứ tự chọn (qua các trang)
        self.page = 0
        self.total = 0
        self._rows: list = []
        self._busy = False
        lay = QVBoxLayout(self)
        fr = QHBoxLayout()
        self.e_text = QLineEdit()
        self.e_text.setPlaceholderText("tìm trong đề bài")
        fr.addWidget(QLabel("Lọc"))
        fr.addWidget(self.e_text, 2)
        self.f: dict[str, QComboBox] = {}
        for key, lab in (("lop", "Lớp"), ("mon", "Môn"), ("chuong", "Chương"), ("bai", "Bài"), ("dang", "Dạng"),
                         ("muc_do", "Mức độ"), ("qtype", "Loại"), ("kieu", "Kiểu ID"), ("used", "Đã lấy")):
            cb = QComboBox()
            cb.setMinimumWidth(62)
            self.f[key] = cb
            fr.addWidget(QLabel(lab))
            fr.addWidget(cb, 1)
        lay.addLayout(fr)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["STT", "Nội dung câu hỏi", "Loại", "ID", "Chọn"])
        h = self.t.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c, w in ((0, 50), (2, 50), (3, 90), (4, 50)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.t.setColumnWidth(c, w)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.t, 1)
        bot = QHBoxLayout()
        self.btn = {}
        for key, text, fn in (("hdsd", "HDSD", self.help), ("edit", "Sửa câu hỏi", self.edit_row),
                              ("del", "Xoá", self.delete_rows)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            self.btn[key] = b
            bot.addWidget(b)
        bot.addWidget(QLabel("Chọn"))
        self.cb_n = QComboBox()
        self.cb_n.addItem("", 0)
        for n in (5, 10, 15, 20, 25, 30, 40, 50, 100):
            self.cb_n.addItem(str(n), n)
        self.cb_n.setToolTip("Chọn ngẫu nhiên N câu trong số câu đang lọc")
        self.cb_n.activated.connect(self.pick_random)
        bot.addWidget(self.cb_n)
        for key, text, fn in (("all", "Chọn hết", self.select_all), ("none", "Xoá chọn", self.clear_chosen)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            self.btn[key] = b
            bot.addWidget(b)
        self.c_pdf = QCheckBox("PDF")
        self.c_pdf.setToolTip("Biên dịch luôn ra PDF sau khi tạo đề")
        bot.addWidget(self.c_pdf)
        self.l_count = QLabel("Đã chọn: 0 câu")
        bot.addWidget(self.l_count)
        bot.addStretch()
        self.pager = QHBoxLayout()
        bot.addLayout(self.pager)
        lay.addLayout(bot)
        self.t.itemChanged.connect(self._item_changed)
        for cb in self.f.values():
            cb.activated.connect(self._filter_changed)
        self.e_text.returnPressed.connect(self.reload)
        self._fill_combos()

    # ---------------------------------------------------------------- bộ lọc
    @property
    def basket(self) -> list:
        return list(self.chosen.values())

    def _fill_combos(self, changed: str | None = None):
        pool = self.win.pool_bank()
        order = ("lop", "mon", "chuong", "bai", "dang")
        cur = {k: self.f[k].currentData() or "" for k in self.f}
        start = order.index(changed) + 1 if changed in order else 0
        for k, cb in self.f.items():
            if k in order and order.index(k) < start and cb.count():
                continue
            if k == "kieu":
                items = [("", ""), ("ID6", "6"), ("ID5", "5")]
            elif k == "used":
                items = [("", ""), ("Đã lấy", "1"), ("Chưa lấy", "0")]
            elif k == "qtype":
                items = [("", "")] + list(LOAI_ITEMS)
            elif k == "muc_do":
                items = [("", "")] + [(LEVEL_NAMES.get(x, x), x) for x in (pool.distinct("muc_do") if pool else [])]
            else:
                parents = {p: cur[p] for p in order[:order.index(k)]}
                items = [("", "")] + [(x, x) for x in (pool.distinct(k, **parents) if pool else [])]
            keep = cb.currentData() if k not in order[start:] else ""
            cb.blockSignals(True)
            cb.clear()
            for text, data in items:
                cb.addItem(text, data)
            cb.setCurrentIndex(max(0, cb.findData(keep)))
            cb.blockSignals(False)

    def _filter_changed(self, *_):
        sender = self.sender()
        key = next((k for k, c in self.f.items() if c is sender), None)
        self._fill_combos(key)
        self.reload()

    def filters(self) -> dict:
        kw = {k: (cb.currentData() or None) for k, cb in self.f.items()}
        t = self.e_text.text().strip()
        if t:
            kw["text"] = t
        return kw

    # ---------------------------------------------------------------- bảng
    def reload(self, keep_page=False):
        pool = self.win.pool_bank()
        if not keep_page:
            self.page = 0
        self._rows, self.total = [], 0
        if pool is not None:
            kw = self.filters()
            self.total = pool.search_count(**kw)
            self.page = min(self.page, max(0, (self.total - 1) // self.PAGE))
            self._rows = pool.search(limit=self.PAGE, offset=self.page * self.PAGE, **kw)
        self._busy = True
        self.t.setRowCount(len(self._rows))
        for r, q in enumerate(self._rows):
            for c, v in enumerate((str(self.page * self.PAGE + r + 1), one_line(q.raw or q.stem),
                                   LOAI_SHOW.get(q.qtype, q.qtype), q.id_code)):
                self.t.setItem(r, c, QTableWidgetItem(v))
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked if q.db_id in self.chosen else Qt.CheckState.Unchecked)
            self.t.setItem(r, 4, it)
        self._busy = False
        self._rebuild_pager()
        self._update_count()

    def showEvent(self, e):
        super().showEvent(e)
        if not self._rows and self.total == 0:
            self._fill_combos()
            self.reload()

    def _item_changed(self, it):
        if self._busy or it.column() != 4 or it.row() >= len(self._rows):
            return
        q = self._rows[it.row()]
        if it.checkState() == Qt.CheckState.Checked:
            self.chosen.setdefault(q.db_id, q)
        else:
            self.chosen.pop(q.db_id, None)
        self._update_count()

    def _update_count(self):
        self.l_count.setText(f"Đã chọn: {len(self.chosen)} câu")

    # ---------------------------------------------------------------- phân trang
    def pages(self) -> int:
        return max(1, -(-self.total // self.PAGE))

    def go_page(self, p: int):
        self.page = max(0, min(p, self.pages() - 1))
        self.reload(keep_page=True)

    def _rebuild_pager(self):
        while self.pager.count():
            w = self.pager.takeAt(0).widget()
            if w is not None:
                w.deleteLater()
        n, cur = self.pages(), self.page
        items = [("Đầu", 0), ("Trước", cur - 1)]
        lo = max(0, min(cur - 2, n - 5))
        items += [(f"[{i + 1}]" if i == cur else str(i + 1), i) for i in range(lo, min(n, lo + 5))]
        items += [("Sau", cur + 1), ("Cuối", n - 1)]
        for text, p in items:
            b = QPushButton(text)
            b.setFixedWidth(46 if len(text) <= 3 else 56)
            b.setEnabled(0 <= p < n and p != cur)
            b.clicked.connect(lambda _c=False, p=p: self.go_page(p))
            self.pager.addWidget(b)

    # ---------------------------------------------------------------- nút dưới bảng
    def help(self):
        QMessageBox.information(self, "Tạo đề tự chọn",
                                "1. Lọc câu hỏi bằng các ô phía trên (Lớp → Môn → Chương → Bài → Dạng, Mức độ, Loại…).\n"
                                "2. Tick cột «Chọn» ở các câu muốn lấy (giữ nguyên khi sang trang khác), hoặc dùng "
                                "«Chọn [số]» để lấy ngẫu nhiên, «Chọn hết».\n"
                                "3. Đặt thông tin đề, số mã đề ở tab «Tuỳ chọn đề» rồi bấm «Tạo đề».\n\n"
                                "«Sửa câu hỏi»/«Xoá» tác động lên dòng đang chọn trong kho.")

    def _current_ids(self) -> list[int]:
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        return [self._rows[r].db_id for r in rows if r < len(self._rows)]

    def edit_row(self):
        ids = self._current_ids()
        if not ids:
            QMessageBox.information(self, "Sửa câu hỏi", "Bấm vào một dòng để chọn câu cần sửa.")
            return
        if self.win.pool_bank() is not self.win.bank:
            QMessageBox.information(self, "Sửa câu hỏi", "Chỉ sửa được câu trong ngân hàng (không sửa câu nạp từ file).")
            return
        from ..dialogs.edit import EditDialog
        if EditDialog(self.win, ids[0]).exec():
            self.chosen.pop(ids[0], None)
            self.win.build_tree()
            self.win.refresh()
            self.reload(keep_page=True)

    def delete_rows(self):
        ids = self._current_ids()
        if not ids or self.win.pool_bank() is not self.win.bank:
            return
        if QMessageBox.question(self, "Xoá", f"Xoá {len(ids)} câu khỏi ngân hàng?") != QMessageBox.StandardButton.Yes:
            return
        self.win.bank.delete(ids)
        for i in ids:
            self.chosen.pop(i, None)
        self.win.build_tree()
        self.win.refresh()
        self.reload(keep_page=True)

    def pick_random(self, *_):
        n = self.cb_n.currentData() or 0
        pool = self.win.pool_bank()
        if not n or pool is None:
            return
        ids = pool.search_ids(**self.filters())
        for i in random.sample(ids, min(n, len(ids))):
            if i not in self.chosen:
                q = pool.get(i)
                if q is not None:
                    self.chosen[i] = q
        self.reload(keep_page=True)

    def select_all(self):
        pool = self.win.pool_bank()
        if pool is None:
            return
        ids = pool.search_ids(limit=2000, **self.filters())
        if self.total > 2000:
            QMessageBox.information(self, "Chọn hết", "Chỉ chọn 2000 câu đầu – hãy lọc thêm để thu hẹp.")
        for i in ids:
            if i not in self.chosen:
                q = pool.get(i)
                if q is not None:
                    self.chosen[i] = q
        self.reload(keep_page=True)

    def clear_chosen(self):
        self.chosen.clear()
        self.reload(keep_page=True)

    # --- tương thích: thêm câu đang chọn ở tab Câu hỏi
    def add_selected(self):
        for i in self.win.selected_ids():
            q = self.win.bank.get(i)
            if q is not None:
                self.chosen.setdefault(q.db_id, q)
        self.reload(keep_page=True)

    def generate(self):
        if not self.chosen:
            QMessageBox.information(self, "Tạo đề tự chọn", "Chưa chọn câu nào (tick cột «Chọn»).")
            return
        self.sync_options()
        vs = mix_versions(sections_from_questions(self.basket), self.codes(), random.Random(), self.mix_opt())
        export_with_gen_options(self.win, vs, "Tạo đề tự chọn", files_pdf=self.c_pdf.isChecked() or None)


class FileMixPanel(_Base):
    """Tạo đề theo file (như MyLT): bảng «STT | Tập tin | Đã có | Lấy» – mỗi file lấy N câu (trống = lấy hết)."""

    def __init__(self, win):
        super().__init__(win)
        self.paths: list[str] = []
        self.qs: dict[str, list] = {}
        self._busy = False
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        for text, fn in (("Chọn files…", self.pick), ("Bỏ file chọn", self.remove), ("Nạp vào nguồn", self.load_source)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.t = QTableWidget(0, 4)
        self.t.setHorizontalHeaderLabels(["STT", "Tập tin", "Đã có", "Lấy"])
        h = self.t.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for c, w in ((0, 50), (2, 70), (3, 70)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.t.setColumnWidth(c, w)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.itemChanged.connect(lambda _i: not self._busy and self._count())
        lay.addWidget(self.t, 1)
        bot = QHBoxLayout()
        self.l_count = QLabel("Đã chọn: 0 câu")
        bot.addWidget(self.l_count)
        b = QPushButton("Xoá chọn")
        b.clicked.connect(self.clear_take)
        bot.addWidget(b)
        bot.addStretch()
        lay.addLayout(bot)
        lay.addWidget(QLabel("<i>«Lấy» = số câu lấy ngẫu nhiên từ file đó; để trống = lấy hết. Dòng <code>%VUNG</code> trong "
                             "file chia đề thành các vùng trộn riêng.</i>"))

    def pick(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "File đề (chọn được nhiều file)", self.win.settings.value("last_dir", ""),
                                             "LaTeX (*.tex)")
        if ps:
            self.set_files(self.paths + [p for p in ps if p not in self.paths])

    def load_source(self):
        """Nạp các file này làm nguồn câu hỏi của cả tab Trộn đề (chế độ «Từ Files»): bảng ID, tự chọn… dùng luôn."""
        if not self.paths:
            self.pick()
        if not self.paths:
            return
        bar = self.win.mix_source_bar
        bar.load_files(self.paths)
        if not bar.r_files.isChecked():
            bar.r_files.blockSignals(True)
            bar.r_files.setChecked(True)
            bar.r_files.blockSignals(False)
            self.win.mix_source = "files"
            bar.b_files.setEnabled(True)
            bar.b_open.setEnabled(False)
            bar.b_import.setEnabled(False)
        bar.refresh()
        self.win.statusBar().showMessage(f"Đã nạp {self.win.file_pool.count():,} câu từ {len(self.paths)} file làm nguồn trộn đề.", 8000)

    def remove(self):
        rows = {i.row() for i in self.t.selectedIndexes()}
        self.set_files([p for r, p in enumerate(self.paths) if r not in rows])

    def set_files(self, paths: list[str]):
        takes = {p: self._take(r) for r, p in enumerate(self.paths)}
        self.paths = list(paths)
        for p in self.paths:
            if p not in self.qs:
                try:
                    self.qs[p] = parse_file(p)
                except Exception:  # noqa: BLE001
                    self.qs[p] = []
        self._busy = True
        self.t.setRowCount(len(self.paths))
        for r, p in enumerate(self.paths):
            for c, v in enumerate((str(r + 1), p, str(len(self.qs[p])))):
                it = QTableWidgetItem(v)
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.t.setItem(r, c, it)
            self.t.setItem(r, 3, QTableWidgetItem(str(takes.get(p) or "")))
        self._busy = False
        self._count()

    def _take(self, r: int) -> int:
        it = self.t.item(r, 3)
        txt = it.text().strip() if it else ""
        return int(txt) if txt.isdigit() else 0

    def _count(self):
        n = 0
        for r, p in enumerate(self.paths):
            have = len(self.qs.get(p, []))
            t = self._take(r)
            n += min(t, have) if t else have
        self.l_count.setText(f"Đã chọn: {n} câu")

    def clear_take(self):
        self._busy = True
        for r in range(self.t.rowCount()):
            self.t.setItem(r, 3, QTableWidgetItem(""))
        self._busy = False
        self._count()

    def load_questions(self) -> list:
        out = []
        for r, p in enumerate(self.paths):
            if not os.path.isfile(p):
                raise ValueError(f"Không thấy file: {p}")
            got = parse_file(p)
            t = self._take(r)
            if t and t < len(got):
                got = [got[i] for i in sorted(random.sample(range(len(got)), t))]
            out += got
        return out

    def generate(self):
        if not self.paths:
            QMessageBox.information(self, "Tạo đề theo file", "Chọn file đề .tex (nút «Chọn files…»).")
            return
        try:
            qs = self.load_questions()
        except ValueError as e:
            QMessageBox.warning(self, "Tạo đề theo file", str(e))
            return
        if not qs:
            QMessageBox.warning(self, "Tạo đề theo file", "File không có câu hỏi nào.")
            return
        self.sync_options()
        vs = mix_versions(sections_from_questions(qs), self.codes(), random.Random(), self.mix_opt())
        export_with_gen_options(self.win, vs, "Tạo đề theo file")


class SimilarExamPanel(_Base):
    """Tạo đề tương tự (như MyLT): đề gốc → tìm tối đa K đề tương tự (theo ID hoặc nội dung, ngưỡng tỉ lệ) → xem/đổi/sửa → Tạo đề."""

    def __init__(self, win):
        super().__init__(win)
        self.sample: list = []
        self.exams: list[list[dict]] = []       # mỗi đề: [{"orig": Question, "new": Question|None, "on": bool}]
        self._busy = False
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("File đề gốc"))
        self.e_file = QLineEdit()
        self.e_file.setReadOnly(True)
        row.addWidget(self.e_file, 1)
        for text, fn in (("Chọn", self.pick), ("Xoá", self.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Đề tương tự thứ"))
        self.cb_exam = QComboBox()
        self.cb_exam.setMinimumWidth(60)
        self.cb_exam.activated.connect(lambda _i: self.show_exam())
        row.addWidget(self.cb_exam)
        for text, fn in (("Lưu", self.save), ("Đổi", self.swap), ("Sửa", self.edit)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        self.c_pdf = QCheckBox("Xem PDF")
        row.addWidget(self.c_pdf)
        row.addStretch()
        row.addWidget(QLabel("Tìm theo"))
        self.cb_by = QComboBox()
        for t, d in (("ID (cùng dạng)", "id"), ("ID mở rộng (bỏ dạng)", "id5"), ("Nội dung", "content")):
            self.cb_by.addItem(t, d)
        row.addWidget(self.cb_by)
        row.addWidget(QLabel("Tỉ lệ tương tự"))
        self.cb_ratio = QComboBox()
        for p in range(30, 100, 5):
            self.cb_ratio.addItem(f"{p}%", p / 100)
        self.cb_ratio.setCurrentIndex(self.cb_ratio.findData(0.65))
        row.addWidget(self.cb_ratio)
        row.addWidget(QLabel("Số đề tối đa"))
        self.e_max = QLineEdit("3")
        self.e_max.setFixedWidth(50)
        row.addWidget(self.e_max)
        b = QPushButton("Tìm")
        b.clicked.connect(self.search)
        row.addWidget(b)
        b = QPushButton("HDSD")
        b.clicked.connect(self.help)
        row.addWidget(b)
        lay.addLayout(row)
        self.t = QTableWidget(0, 4)
        self.t.setHorizontalHeaderLabels(["STT", "Câu hỏi đề gốc", "Câu hỏi đề tương tự", "Chọn"])
        h = self.t.horizontalHeader()
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        for c, w in ((0, 50), (3, 50)):
            h.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.t.setColumnWidth(c, w)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.itemChanged.connect(self._item_changed)
        lay.addWidget(self.t, 1)
        self.l_note = QLabel("")
        self.l_note.setWordWrap(True)
        lay.addWidget(self.l_note)

    # ---------------------------------------------------------------- đề gốc
    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "File đề gốc", self.win.settings.value("last_dir", ""), "LaTeX (*.tex)")
        if p:
            self.e_file.setText(p)
            self.sample = parse_file(p)
            self.exams = []
            self.cb_exam.clear()
            self.show_sample()

    def clear(self):
        self.e_file.clear()
        self.sample, self.exams = [], []
        self.cb_exam.clear()
        self.t.setRowCount(0)
        self.l_note.clear()

    def get_sample(self) -> list:
        if self.sample:
            return self.sample
        return [q for q in (self.win.bank.get(i) for i in self.win.selected_ids()) if q is not None]

    def show_sample(self):
        self._busy = True
        self.t.setRowCount(len(self.sample))
        for r, q in enumerate(self.sample):
            self.t.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self.t.setItem(r, 1, QTableWidgetItem(one_line(q.stem)))
        self._busy = False

    # ---------------------------------------------------------------- tìm
    @staticmethod
    def _sim(a, b) -> float:
        from ...idsuggest import question_text, tokens
        ta, tb = tokens(question_text(a)), tokens(question_text(b))
        num = sum(min(v, ta.get(k, 0)) for k, v in tb.items())
        return num / ((sum(ta.values()) * sum(tb.values())) ** 0.5 or 1)

    def search(self):
        sample = self.get_sample()
        if not sample:
            QMessageBox.information(self, "Đề tương tự", "Chọn file đề gốc (hoặc chọn câu ở tab Câu hỏi).")
            return
        pool = self.win.pool_bank()
        k = int(self.e_max.text()) if self.e_max.text().strip().isdigit() else 3
        by, ratio = self.cb_by.currentData(), self.cb_ratio.currentData()
        rng = random.Random()
        self.sample = sample
        self.exams, notes, used = [], [], set()
        for n in range(max(1, k)):
            qs, nt = similar_exam(pool, sample, rng, same_level=True, keep_missing=False, exclude_ids=used,
                                  widen=1 if by == "id5" else 0, by_content=(by == "content"))
            # similar_exam bỏ câu không thay được (keep_missing=False) → ghép lại theo thứ tự câu gốc
            rows, j = [], 0
            for q in sample:
                new = None
                if j < len(qs) and qs[j].qtype == q.qtype and qs[j].db_id != q.db_id and (qs[j].id_code[:5] == q.id_code[:5]
                                                                                           or by == "content"):
                    new = qs[j]
                    j += 1
                if new is not None and by == "content" and self._sim(q, new) < ratio:
                    new = None
                rows.append({"orig": q, "new": new, "on": new is not None})
            if not any(r["new"] for r in rows):
                break
            used |= {r["new"].db_id for r in rows if r["new"] is not None and r["new"].db_id is not None}
            self.exams.append(rows)
            notes += nt
        self.cb_exam.clear()
        if not self.exams:
            self.show_sample()
            self.l_note.setText("Không tìm được câu tương tự trong nguồn (cùng ID/loại, khác câu gốc). Thử «ID mở rộng» "
                                "hoặc «Nội dung», hạ tỉ lệ, hoặc kiểm tra câu gốc đã có ID.")
            return
        for i in range(len(self.exams)):
            self.cb_exam.addItem(str(i + 1), i)
        self.l_note.setText(f"Tìm được {len(self.exams)} đề tương tự." + (("  " + " · ".join(notes[:4])) if notes else ""))
        self.show_exam()

    def _cur(self) -> list[dict]:
        i = self.cb_exam.currentData()
        return self.exams[i] if i is not None and 0 <= i < len(self.exams) else []

    def show_exam(self):
        rows = self._cur()
        if not rows:
            return
        self._busy = True
        self.t.setRowCount(len(rows))
        for r, d in enumerate(rows):
            self.t.setItem(r, 0, QTableWidgetItem(str(r + 1)))
            self.t.setItem(r, 1, QTableWidgetItem(one_line(d["orig"].stem)))
            self.t.setItem(r, 2, QTableWidgetItem(one_line(d["new"].stem) if d["new"] else "(không có câu tương tự)"))
            it = QTableWidgetItem()
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Checked if d["on"] and d["new"] else Qt.CheckState.Unchecked)
            self.t.setItem(r, 3, it)
        self._busy = False

    def _item_changed(self, it):
        rows = self._cur()
        if self._busy or it.column() != 3 or it.row() >= len(rows):
            return
        rows[it.row()]["on"] = it.checkState() == Qt.CheckState.Checked and rows[it.row()]["new"] is not None

    def _sel_row(self) -> int:
        rs = sorted({i.row() for i in self.t.selectedIndexes()})
        return rs[0] if rs else -1

    def swap(self):
        """Đổi câu tương tự ở dòng đang chọn sang một câu ứng viên khác."""
        rows, r = self._cur(), self._sel_row()
        if not rows or r < 0:
            QMessageBox.information(self, "Đổi", "Bấm vào một dòng trong bảng để đổi câu tương tự.")
            return
        d, pool = rows[r], self.win.pool_bank()
        taken = {x["new"].db_id for ex in self.exams for x in ex if x["new"]} | {d["orig"].db_id}
        cands = [c for c in pool.similar(d["orig"], True) if c.qtype == d["orig"].qtype and c.db_id not in taken]
        if not cands:
            QMessageBox.information(self, "Đổi", "Không còn câu tương tự nào khác trong kho.")
            return
        d["new"], d["on"] = random.choice(cands), True
        self.show_exam()

    def edit(self):
        rows, r = self._cur(), self._sel_row()
        if not rows or r < 0 or rows[r]["new"] is None or self.win.pool_bank() is not self.win.bank:
            QMessageBox.information(self, "Sửa", "Bấm vào dòng có câu tương tự (trong ngân hàng) để sửa.")
            return
        from ..dialogs.edit import EditDialog
        if EditDialog(self.win, rows[r]["new"].db_id).exec():
            rows[r]["new"] = self.win.bank.get(rows[r]["new"].db_id)
            self.show_exam()

    def _chosen_questions(self) -> list:
        return [d["new"] if d["on"] and d["new"] else d["orig"] for d in self._cur()]

    def save(self):
        qs = self._chosen_questions()
        if not qs:
            return
        from ...appdirs import folder
        from ...exporter import export_questions
        d = folder("tuong_tu")
        os.makedirs(d, exist_ok=True)
        p, _ = QFileDialog.getSaveFileName(self, "Lưu đề tương tự", os.path.join(d, "de_tuong_tu.tex"), "LaTeX (*.tex)")
        if p:
            export_questions(qs, p)

    def help(self):
        QMessageBox.information(self, "Tạo đề tương tự",
                                "1. «Chọn» file đề gốc (.tex).\n2. Đặt «Tìm theo» (ID / Nội dung), «Tỉ lệ tương tự» (chỉ dùng "
                                "khi tìm theo nội dung) và «Số đề tối đa» rồi bấm «Tìm».\n3. Chọn «Đề tương tự thứ» N để xem; "
                                "bỏ tick «Chọn» ở câu nào thì giữ câu gốc; «Đổi» đổi câu tương tự khác; «Sửa» sửa câu.\n"
                                "4. «Lưu» lưu đề đang xem ra .tex, hoặc «Tạo đề» để trộn thành các mã đề.")

    def generate(self):
        if not self._cur():
            self.search()
            if not self._cur():
                return
        self.sync_options()
        qs = self._chosen_questions()
        vs = mix_versions(sections_from_questions(qs), self.codes(), random.Random(), self.mix_opt())
        export_with_gen_options(self.win, vs, "Đề tương tự", files_pdf=self.c_pdf.isChecked() or None)
