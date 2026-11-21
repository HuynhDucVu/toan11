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
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QTextBrowser,
    QVBoxLayout, QWidget)

from ...generator import MixOptions, mix_versions, sections_from_questions, similar_exam
from ...parser import parse_file

if TYPE_CHECKING:
    from ..main_window import MainWindow


def export_with_gen_options(win, versions, title="Kết quả trộn đề", log_rules=None):
    """Xuất các mã đề bằng thông tin đầu đề, thư mục, mẫu và tuỳ chọn của tab Tạo đề; mở hộp kết quả."""
    from ...exporter import export_versions
    from ..dialogs.result import ResultDialog
    gp = win.gen_panel
    out = gp.e_out[0].text()
    try:
        export_versions(versions, out, template_path=gp.e_tpl[0].text() or None, ten_de=gp.e_ten.text(),
                        truong=gp.e_truong.text(), thoi_gian=gp.e_tg.value(), options=gp.export_options())
    except (OSError, ValueError) as e:
        QMessageBox.critical(win, title, str(e))
        return False
    ids = {q.db_id for v in versions for q in v.all_questions() if q.db_id is not None}
    if ids:
        win.bank.mark_used(ids)
        win.bank.log_batch(versions, ten_de=gp.e_ten.text(), matrix=log_rules or [], out_dir=out)
    gp.opts.save()
    ResultDialog(win, versions, out, '', gp.export_options().omr_capacity).exec()
    return True


def _codes_row(parent):
    sp = QSpinBox()
    sp.setRange(1, 99)
    sp.setValue(4)
    return sp


class _Base(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win

    def codes(self, n):
        return self.win.gen_panel.opts.codes(n)

    def mix_opt(self) -> MixOptions:
        return self.win.gen_panel.opts.mix_options()

    def note(self, lay):
        lb = QLabel("<i>Thông tin đầu đề, thư mục xuất, file mẫu và «Tuỳ chọn trộn đề» lấy theo tab "
                    "<b>Theo ma trận</b>.</i>")
        lb.setWordWrap(True)
        lay.addWidget(lb)


class PickPanel(_Base):
    """Tự chọn câu: lấy câu đang chọn ở tab Câu hỏi đưa vào giỏ, sắp xếp, rồi trộn."""

    def __init__(self, win):
        super().__init__(win)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chọn câu ở tab <b>Câu hỏi</b> (giữ Ctrl/Shift để chọn nhiều) rồi bấm "
                             "<b>Thêm câu đang chọn</b>. Thứ tự trong giỏ là thứ tự của đề gốc."))
        self.t = QTableWidget(0, 4)
        self.t.setHorizontalHeaderLabels(["#", "Loại", "ID", "Nội dung"])
        self.t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.t, 1)
        row = QHBoxLayout()
        for text, fn in (("➕ Thêm câu đang chọn", self.add_selected), ("Bỏ câu", self.remove),
                         ("▲", lambda: self.move(-1)), ("▼", lambda: self.move(1)), ("Xoá giỏ", self.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        self.l_count = QLabel()
        row.addWidget(self.l_count)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số mã đề"))
        self.sp_n = _codes_row(self)
        row.addWidget(self.sp_n)
        row.addStretch()
        b = QPushButton("TẠO ĐỀ TỪ GIỎ")
        b.setObjectName("primary")
        b.clicked.connect(self.generate)
        row.addWidget(b)
        lay.addLayout(row)
        self.note(lay)
        self.basket = []

    def _refresh(self):
        self.t.setRowCount(len(self.basket))
        for r, q in enumerate(self.basket):
            for c, v in enumerate((str(q.db_id), q.qtype, q.id_code, " ".join(q.stem.split())[:150])):
                self.t.setItem(r, c, QTableWidgetItem(v))
        n = {s: sum(q.qtype == s for q in self.basket) for s in ("TN", "DS", "KQ", "TL")}
        self.l_count.setText(" · ".join(f"{k}: {v}" for k, v in n.items() if v) or "Giỏ trống")

    def add_selected(self):
        have = {q.db_id for q in self.basket}
        for i in self.win.selected_ids():
            q = self.win.bank.get(i)
            if q is not None and q.db_id not in have:
                self.basket.append(q)
                have.add(q.db_id)
        self._refresh()

    def remove(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()}, reverse=True)
        for r in rows:
            del self.basket[r]
        self._refresh()

    def move(self, d):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if len(rows) != 1:
            return
        r = rows[0]
        if 0 <= r + d < len(self.basket):
            self.basket[r], self.basket[r + d] = self.basket[r + d], self.basket[r]
            self._refresh()
            self.t.selectRow(r + d)

    def clear(self):
        self.basket = []
        self._refresh()

    def generate(self):
        if not self.basket:
            QMessageBox.information(self, "Tự chọn câu", "Giỏ đề đang trống.")
            return
        vs = mix_versions(sections_from_questions(self.basket), self.codes(self.sp_n.value()), random.Random(),
                          self.mix_opt())
        export_with_gen_options(self.win, vs, "Tự chọn câu")


class FileMixPanel(_Base):
    def __init__(self, win):
        super().__init__(win)
        lay = QVBoxLayout(self)
        f = QFormLayout()
        self.e_file = QLineEdit()
        self.e_file.setPlaceholderText("một file, hoặc nhiều file cách nhau dấu ; – thêm :số câu để chọn ngẫu nhiên từng file, "
                                       "vd  a.tex:10 ; b.tex:5 ; c.tex")
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(self._pick)
        r = QHBoxLayout()
        r.addWidget(self.e_file)
        r.addWidget(b)
        self.sp_n = _codes_row(self)
        f.addRow("File đề .tex", r)
        f.addRow("Số mã đề", self.sp_n)
        lay.addLayout(f)
        lay.addWidget(QLabel("Trộn theo vùng: thêm dòng chú thích <code>%VUNG</code> vào file để chia đề thành các vùng – "
                             "câu chỉ đổi chỗ trong vùng của nó (vd giữ câu dễ ở đầu, câu khó ở cuối)."))
        self.info = QTextBrowser()
        lay.addWidget(self.info, 1)
        b = QPushButton("TRỘN FILE")
        b.setObjectName("primary")
        b.clicked.connect(self.generate)
        lay.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)
        self.note(lay)

    def _pick(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "File đề (chọn được nhiều file)", "", "LaTeX (*.tex)")
        if ps:
            self.e_file.setText(" ; ".join(ps))
            try:
                qs = self.load_questions()
            except ValueError as e:
                QMessageBox.warning(self, "Trộn theo file", str(e))
                return
            n = {s: sum(q.qtype == s for q in qs) for s in ("TN", "DS", "KQ", "TL")}
            regions = len({getattr(q, "region", 0) for q in qs})
            self.info.setHtml(f"<p>{len(qs)} câu: " + ", ".join(f"{k} {v}" for k, v in n.items() if v) +
                              (f" · {regions} vùng" if regions > 1 else "") + "</p>")

    def load_questions(self) -> list:
        """Đọc các file (cách nhau ;). «đường_dẫn:N» = lấy ngẫu nhiên N câu của file đó (cùng loại phân đều theo thứ tự)."""
        import re
        qs = []
        for part in [x.strip() for x in self.e_file.text().split(";") if x.strip()]:
            m = re.match(r"^(.*?)(?::(\d+))?$", part)
            path, n = m.group(1).strip().strip('"'), (int(m.group(2)) if m.group(2) else 0)
            if not os.path.isfile(path):
                raise ValueError(f"Không thấy file: {path}")
            got = parse_file(path)
            if n and n < len(got):
                keep = sorted(random.sample(range(len(got)), n))
                got = [got[i] for i in keep]
            qs += got
        return qs

    def generate(self):
        if not self.e_file.text().strip():
            QMessageBox.information(self, "Trộn theo file", "Chọn file đề .tex.")
            return
        try:
            qs = self.load_questions()
        except ValueError as e:
            QMessageBox.warning(self, "Trộn theo file", str(e))
            return
        if not qs:
            QMessageBox.warning(self, "Trộn theo file", "File không có câu hỏi nào.")
            return
        vs = mix_versions(sections_from_questions(qs), self.codes(self.sp_n.value()), random.Random(), self.mix_opt())
        export_with_gen_options(self.win, vs, "Trộn theo file")


class SimilarExamPanel(_Base):
    def __init__(self, win):
        super().__init__(win)
        lay = QVBoxLayout(self)
        g = QGroupBox("Đề mẫu")
        f = QFormLayout(g)
        self.e_file = QLineEdit()
        self.e_file.setPlaceholderText("file đề .tex (để trống = dùng các câu đang chọn ở tab Câu hỏi)")
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(lambda: self.e_file.setText(QFileDialog.getOpenFileName(self, "Đề mẫu", "", "LaTeX (*.tex)")[0]
                                                      or self.e_file.text()))
        r = QHBoxLayout()
        r.addWidget(self.e_file)
        r.addWidget(b)
        self.c_level = QCheckBox("Giữ đúng mức độ (thiếu thì lấy câu cùng dạng khác mức độ)")
        self.c_level.setChecked(True)
        self.c_keep = QCheckBox("Câu không có câu thay: giữ câu của đề mẫu")
        self.c_keep.setChecked(True)
        self.sp_n = _codes_row(self)
        self.c_each = QCheckBox("Mỗi mã đề một bộ câu tương tự khác nhau")
        self.cb_widen = QComboBox()
        for t, d in (("Chỉ cùng ID (đủ dạng)", 0), ("Nếu thiếu: mở rộng theo ID5 (bỏ dạng)", 1),
                     ("Nếu thiếu: mở rộng tới ID4 (bỏ cả bài)", 2), ("Nếu thiếu: mở rộng tới ID3 (bỏ cả mức độ)", 3)):
            self.cb_widen.addItem(t, d)
        self.c_content = QCheckBox("Chọn câu giống NỘI DUNG nhất (thay vì ngẫu nhiên) trong các câu ứng viên")
        f.addRow("Đề mẫu", r)
        f.addRow("Phạm vi tìm câu", self.cb_widen)
        f.addRow(self.c_content)
        f.addRow(self.c_level)
        f.addRow(self.c_keep)
        f.addRow("Số mã đề", self.sp_n)
        f.addRow(self.c_each)
        lay.addWidget(g)
        lay.addWidget(QLabel("Mỗi câu của đề mẫu được thay bằng một câu <b>cùng ID</b> (cùng chương – bài – dạng) trong "
                             "kho, không trùng câu mẫu. Hợp để ra đề kiểm tra lại, đề ôn tập «giống đề cũ»."))
        self.info = QTextBrowser()
        lay.addWidget(self.info, 1)
        b = QPushButton("TẠO ĐỀ TƯƠNG TỰ")
        b.setObjectName("primary")
        b.clicked.connect(self.generate)
        lay.addWidget(b, alignment=Qt.AlignmentFlag.AlignRight)
        self.note(lay)

    def sample(self):
        p = self.e_file.text().strip()
        if p:
            return parse_file(p)
        return [q for q in (self.win.bank.get(i) for i in self.win.selected_ids()) if q is not None]

    def generate(self):
        sample = self.sample()
        if not sample:
            QMessageBox.information(self, "Đề tương tự", "Chọn file đề mẫu, hoặc chọn câu ở tab Câu hỏi.")
            return
        rng = random.Random()
        codes = self.codes(self.sp_n.value())
        notes = []
        if self.c_each.isChecked():
            vs, used = [], set()
            for c in codes:
                qs, nt = similar_exam(self.win.bank, sample, rng, same_level=self.c_level.isChecked(),
                                      keep_missing=self.c_keep.isChecked(), exclude_ids=used,
                                      widen=self.cb_widen.currentData(), by_content=self.c_content.isChecked())
                used |= {q.db_id for q in qs if q.db_id is not None}
                notes += [f"Mã {c}: {x}" for x in nt]
                vs += mix_versions(sections_from_questions(qs), [c], rng, self.mix_opt())
        else:
            qs, notes = similar_exam(self.win.bank, sample, rng, same_level=self.c_level.isChecked(),
                                     keep_missing=self.c_keep.isChecked(), widen=self.cb_widen.currentData(),
                                     by_content=self.c_content.isChecked())
            vs = mix_versions(sections_from_questions(qs), codes, rng, self.mix_opt())
        self.info.setHtml("<p><b>Ghi chú:</b></p>" + "<br>".join(notes) if notes else
                          "<p>Mọi câu đều có câu tương tự trong kho.</p>")
        if not any(list(v.all_questions()) for v in vs):
            return
        export_with_gen_options(self.win, vs, "Đề tương tự")
