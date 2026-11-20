"""Hộp thoại «Phòng thi LAN»: phát đề qua Wi-Fi, xem bảng điểm trực tiếp."""
from __future__ import annotations

import os
import random
from typing import TYPE_CHECKING

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout)

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ArenaDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win, self.arena = win, None
        self.setWindowTitle("Phòng thi LAN")
        self.resize(820, 600)
        lay = QVBoxLayout(self)
        f = QFormLayout()
        self.cb_src = QComboBox()
        self.cb_src.addItem("Theo ma trận ở tab Tạo đề", "matrix")
        self.cb_src.addItem("Từ một file đề .tex", "file")
        self.e_file = QLineEdit()
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(self._pick)
        r = QHBoxLayout()
        r.addWidget(self.e_file)
        r.addWidget(b)
        self.sp_n = QSpinBox()
        self.sp_n.setRange(1, 24)
        self.sp_n.setValue(4)
        self.sp_tg = QSpinBox()
        self.sp_tg.setRange(1, 180)
        self.sp_tg.setValue(15)
        self.sp_tg.setSuffix(" phút")
        self.sp_port = QSpinBox()
        self.sp_port.setRange(1024, 65535)
        self.sp_port.setValue(8765)
        f.addRow("Nguồn đề", self.cb_src)
        f.addRow("File đề", r)
        f.addRow("Số mã đề", self.sp_n)
        f.addRow("Thời gian", self.sp_tg)
        f.addRow("Cổng", self.sp_port)
        lay.addLayout(f)
        row = QHBoxLayout()
        self.b_start = QPushButton("▶ Mở phòng thi")
        self.b_start.setObjectName("primary")
        self.b_start.clicked.connect(self.toggle)
        row.addWidget(self.b_start)
        for text, fn in (("Mở bảng điểm (máy chiếu)", self.open_board), ("Xuất CSV…", self.export)):
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            row.addWidget(bb)
        row.addStretch()
        lay.addLayout(row)
        self.l_url = QLabel("Chưa mở phòng thi.")
        fnt = QFont()
        fnt.setPointSize(16)
        fnt.setBold(True)
        self.l_url.setFont(fnt)
        self.l_url.setTextInteractionFlags(self.l_url.textInteractionFlags())
        lay.addWidget(self.l_url)
        lay.addWidget(QLabel("<i>Học sinh nối cùng Wi-Fi với máy này, mở trình duyệt, gõ địa chỉ trên, nhập họ tên → "
                             "làm bài → nộp. Đề trên máy học sinh không chứa đáp án; máy giáo viên chấm. Nếu học sinh "
                             "không vào được: cho phép phần mềm qua Tường lửa Windows (Private network).</i>"))
        self.t = QTableWidget(0, 4)
        self.t.setHorizontalHeaderLabels(["Họ tên", "Mã đề", "Điểm", "Nộp lúc"])
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.t, 1)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)

    def _pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "File đề", "", "LaTeX (*.tex)")
        if p:
            self.e_file.setText(p)
            self.cb_src.setCurrentIndex(1)

    def versions(self):
        from ...generator import make_codes, make_versions, mix_versions, Rule, sections_from_questions
        n = self.sp_n.value()
        codes = make_codes(n, 101, 3)
        opt = self.win.gen_panel.opts.mix_options()
        if self.cb_src.currentData() == "file":
            from ...parser import parse_file
            qs = parse_file(self.e_file.text())
            if not qs:
                raise ValueError("File không có câu hỏi nào")
            return mix_versions(sections_from_questions(qs), codes, random.Random(), opt)
        rules = [Rule.from_dict(r) for r in self.win.gen_panel.rules_dicts()]
        return make_versions(self.win.bank, rules, n, codes=codes, options=opt)

    def toggle(self):
        from ...arena import Arena
        if self.arena:
            self.arena.stop()
            self.arena = None
            self.timer.stop()
            self.b_start.setText("▶ Mở phòng thi")
            self.l_url.setText("Đã đóng phòng thi.")
            return
        try:
            vs = self.versions()
            self.arena = Arena(vs, ten_de=self.win.gen_panel.e_ten.text() or "BÀI KIỂM TRA",
                               thoi_gian=self.sp_tg.value(), port=self.sp_port.value(),
                               scoring=self.win.gen_panel.export_options().scoring_obj())
            url = self.arena.start()
        except Exception as e:  # noqa: BLE001 – không đủ câu, cổng bận…
            self.arena = None
            QMessageBox.warning(self, "Phòng thi LAN", str(e))
            return
        self.b_start.setText("■ Đóng phòng thi")
        self.l_url.setText(f"Địa chỉ cho học sinh: {url}")
        self.timer.start(2000)

    def refresh(self):
        if not self.arena:
            return
        with self.arena.lock:
            rows = list(self.arena.results)
        self.t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, v in enumerate((r["ten"], r["ma"], f"{r['diem']:g} / {r['toi_da']:g}".replace(".", ","), r["luc"])):
                self.t.setItem(i, c, QTableWidgetItem(v))

    def open_board(self):
        if self.arena:
            QDesktopServices.openUrl(QUrl(self.arena.url() + "bang"))

    def export(self):
        if not self.arena or not self.arena.results:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Xuất bảng điểm", "bang_diem.csv", "CSV (*.csv)")
        if p:
            self.arena.export_csv(p)
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(p)))

    def done(self, r):
        if self.arena:
            self.arena.stop()
            self.arena = None
        super().done(r)
