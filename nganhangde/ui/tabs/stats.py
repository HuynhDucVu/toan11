"""Tab «Thống kê»."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget)
from ...idcode import LOP, MON
from ..common import TEN_LOAI

if TYPE_CHECKING:
    from ..main_window import MainWindow


class StatsPanel(QWidget):
    """Tab «Thống kê»: tổng quan kho theo lớp/chương/loại/mức độ."""

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        self.cards = QHBoxLayout()
        lay.addLayout(self.cards)
        self.card_labels = {}
        for key, title in (("all", "Tổng số câu"), ("TN", "Trắc nghiệm"), ("DS", "Đúng/Sai"),
                           ("KQ", "Trả lời ngắn"), ("TL", "Tự luận")):
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            lb = QLabel("0")
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setStyleSheet("font-size: 26px; font-weight: 700; color: #1f4e79;")
            bl.addWidget(lb)
            self.card_labels[key] = lb
            self.cards.addWidget(box)
        self.t = QTableWidget(0, 7)
        self.t.setHorizontalHeaderLabels(["Lớp", "Môn", "Chương", "Nhận biết", "Thông hiểu", "Vận dụng",
                                          "Vận dụng cao"])
        self.t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setAlternatingRowColors(True)
        lay.addWidget(QLabel("<b>Số câu theo chương và mức độ</b>"))
        lay.addWidget(self.t, 1)

    def reload(self):
        bank = self.win.bank
        if not bank:
            return
        self.card_labels["all"].setText(str(bank.count()))
        for k in TEN_LOAI:
            n = bank.con.execute("SELECT COUNT(*) FROM questions WHERE qtype=?", (k,)).fetchone()[0]
            self.card_labels[k].setText(str(n))
        grid = {}
        for r in bank.stats():
            key = (r["lop"], r["mon"], r["chuong"])
            grid.setdefault(key, {})
            grid[key][r["muc_do"]] = grid[key].get(r["muc_do"], 0) + r["n"]
        self.t.setRowCount(len(grid))
        for i, ((lop, mon, ch), d) in enumerate(sorted(grid.items())):
            vals = [LOP.get(lop, lop or "?"), MON.get(mon, mon or "?"), ch or "?"] + \
                   [d.get(m, 0) for m in "NHVC"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.t.setItem(i, c, it)
