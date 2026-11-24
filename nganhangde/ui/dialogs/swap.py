"""Hộp thoại xem trước bộ câu và đổi câu trước khi trộn."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QInputDialog, QLabel,
    QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem, QVBoxLayout)
from ..common import latex_editor


class SwapDialog(QDialog):
    """Xem bộ câu đã chọn theo ma trận; «đổi câu» = thay bằng câu khác cùng dòng ma trận."""

    def __init__(self, panel, sections, rules):
        super().__init__(panel)
        self.panel, self.rules = panel, rules
        self.bank = panel.win.bank
        self.sections = {k: list(v) for k, v in sections.items()}
        self.setWindowTitle("Xem trước bộ câu – đổi câu trước khi trộn")
        self.resize(1150, 680)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chọn câu muốn thay rồi bấm <b>Đổi ngẫu nhiên</b> hoặc <b>Chọn câu thay…</b>. "
                             "Câu thay luôn cùng dòng ma trận (cùng loại, cùng mẫu ID, cùng mức độ)."))
        split = QSplitter(Qt.Orientation.Vertical)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["Phần", "Câu", "ID", "Đáp án", "Nội dung"])
        self.t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.itemSelectionChanged.connect(self.show_code)
        split.addWidget(self.t)
        self.code = latex_editor(read_only=True)
        split.addWidget(self.code)
        split.setSizes([420, 200])
        lay.addWidget(split, 1)
        row = QHBoxLayout()
        for text, fn in (("🎲 Đổi ngẫu nhiên", self.swap_random), ("Chọn câu thay…", self.swap_pick)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        ok = QPushButton("Dùng bộ câu này để trộn")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Huỷ")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.fill()

    def rows(self):
        return [(s, i, q) for s in ("TN", "DS", "KQ", "TL") for i, q in enumerate(self.sections.get(s, []))]

    def fill(self):
        rows = self.rows()
        self.t.setRowCount(len(rows))
        part = {"TN": "I", "DS": "II", "KQ": "III", "TL": "IV"}
        for r, (s, i, q) in enumerate(rows):
            for c, v in enumerate((part[s], str(i + 1), q.id_code, q.answer_text, " ".join(q.stem.split())[:200])):
                self.t.setItem(r, c, QTableWidgetItem(v))

    def current(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        return (self.rows()[rows[0]], rows[0]) if rows else (None, None)

    def show_code(self):
        (item, _r) = self.current()
        if item:
            self.code.setPlainText(item[2].to_latex())

    def used(self):
        return {q.db_id for qs in self.sections.values() for q in qs}

    def _replace(self, new):
        (s, i, old), r = self.current()
        new.rule_index = getattr(old, "rule_index", 0)
        self.sections[s][i] = new
        self.fill()
        self.t.selectRow(r)
        self.show_code()

    def swap_random(self):
        from ...generator import replacement_pool
        import random as _r
        (item, _row) = self.current()
        if not item:
            return
        pool = replacement_pool(self.bank, self.rules, item[2], self.used())
        if not pool:
            QMessageBox.information(self, "Đổi câu", "Kho không còn câu nào khác cùng dòng ma trận.")
            return
        self._replace(_r.choice(pool))

    def swap_pick(self):
        from ...generator import replacement_pool
        (item, _row) = self.current()
        if not item:
            return
        pool = replacement_pool(self.bank, self.rules, item[2], self.used())
        if not pool:
            QMessageBox.information(self, "Đổi câu", "Kho không còn câu nào khác cùng dòng ma trận.")
            return
        labels = [f"#{q.db_id} [{q.id_code}] " + " ".join(q.stem.split())[:110] for q in pool]
        choice, ok = QInputDialog.getItem(self, "Chọn câu thay", f"{len(pool)} câu cùng dòng ma trận:", labels, 0, False)
        if ok:
            self._replace(pool[labels.index(choice)])
