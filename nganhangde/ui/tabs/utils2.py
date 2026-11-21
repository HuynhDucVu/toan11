"""Tab «Tiện ích 2»: dọn mã, đáp án theo chuỗi, đưa đáp án về A, chuyển mức độ ID, tách/nối file, mã \\input,
xuất cả kho theo ID."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QComboBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QTextBrowser, QVBoxLayout, QWidget)

from ... import tools2

if TYPE_CHECKING:
    from ..main_window import MainWindow


class Utils2Panel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        g = QGroupBox("File .tex")
        h = QHBoxLayout(g)
        self.e_files = QLineEdit()
        self.e_files.setPlaceholderText("một hoặc nhiều file .tex (cách nhau dấu ;)")
        b = QPushButton("Chọn…")
        b.clicked.connect(self._pick)
        h.addWidget(self.e_files, 1)
        h.addWidget(b)
        lay.addWidget(g)
        row = QHBoxLayout()
        row.addWidget(QLabel("Chuỗi đáp án:"))
        self.e_key = QLineEdit()
        self.e_key.setPlaceholderText("vd ABCDABCD… (cho các câu trắc nghiệm theo thứ tự)")
        row.addWidget(self.e_key, 1)
        row.addWidget(QLabel("Tách / xuất theo"))
        self.cb_level = QComboBox()
        for t, d in (("Chương", "chuong"), ("Bài", "bai"), ("Dạng", "dang")):
            self.cb_level.addItem(t, d)
        self.cb_level.setCurrentIndex(1)
        row.addWidget(self.cb_level)
        lay.addLayout(row)
        grid = QGridLayout()
        items = [("Xoá dòng trống, căn mã", self.clean), ("Đặt đáp án theo chuỗi", self.set_key),
                 ("Đưa đáp án đúng về A", self.to_a), ("Chuyển mức độ ID (Y,B,K,G,T → N,H,V,C)", self.levels),
                 ("Tách file theo ID", self.split), ("Nối các file thành một", self.join),
                 ("Tạo mã \\input các file", self.inputs), ("Xuất cả kho ra các file theo ID", self.export_bank)]
        for k, (text, fn) in enumerate(items):
            bb = QPushButton(text)
            bb.clicked.connect(fn)
            grid.addWidget(bb, k // 4, k % 4)
        lay.addLayout(grid)
        self.out = QTextBrowser()
        lay.addWidget(self.out, 1)
        lay.addWidget(QLabel("<i>Các thao tác sửa file luôn ghi ra file mới (đuôi _moi.tex), file gốc giữ nguyên.</i>"))

    def _pick(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex", "", "LaTeX (*.tex)")
        if ps:
            self.e_files.setText("; ".join(ps))

    def paths(self):
        ps = [p.strip() for p in self.e_files.text().split(";") if p.strip()]
        if not ps:
            QMessageBox.information(self, "Tiện ích 2", "Chọn file .tex trước.")
        return ps

    def _each(self, fn, label):
        for p in self.paths():
            with open(p, encoding="utf-8", errors="replace") as f:
                text = f.read()
            res = fn(text)
            new, n = res[0], res[1]
            q = os.path.splitext(p)[0] + "_moi.tex"
            with open(q, "w", encoding="utf-8") as f:
                f.write(new)
            extra = ("; " + "; ".join(res[2])) if len(res) > 2 and res[2] else ""
            self.out.append(f"{os.path.basename(p)}: {label} {n} → {q}{extra}")

    def clean(self):
        self._each(tools2.clean_code, "bỏ dòng trống")

    def set_key(self):
        if not self.e_key.text().strip():
            QMessageBox.information(self, "Tiện ích 2", "Nhập chuỗi đáp án.")
            return
        self._each(lambda t: tools2.set_answers(t, self.e_key.text()), "đặt đáp án")

    def to_a(self):
        self._each(tools2.answers_to_A, "câu đưa đáp án về A")

    def levels(self):
        self._each(tools2.convert_levels, "ID đổi mức độ")

    def split(self):
        ps = self.paths()
        d = ps and QFileDialog.getExistingDirectory(self, "Thư mục lưu các file tách", os.path.dirname(ps[0]))
        if d:
            fs = tools2.split_by_id(ps, d, self.cb_level.currentData())
            self.out.append(f"Đã tách thành {len(fs)} file trong {d}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def join(self):
        ps = self.paths()
        p = ps and QFileDialog.getSaveFileName(self, "Lưu file nối", os.path.join(os.path.dirname(ps[0]), "noi.tex"),
                                               "LaTeX (*.tex)")[0]
        if p:
            self.out.append(f"Đã nối {tools2.join_files(ps, p)} câu → {p}")

    def inputs(self):
        ps = self.paths()
        if ps:
            code = tools2.input_code(ps, os.path.dirname(ps[0]))
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(code)
            self.out.append("Đã chép vào bộ nhớ tạm (dán vào file chính):<pre>" + code + "</pre>")

    def export_bank(self):
        from ...appdirs import path as app_path
        d = QFileDialog.getExistingDirectory(self, "Thư mục xuất kho", app_path("de_xuat"))
        if d:
            fs = tools2.export_bank_by_id(self.win.bank, d, self.cb_level.currentData())
            self.out.append(f"Đã xuất kho thành {len(fs)} file trong {d}")
            QDesktopServices.openUrl(QUrl.fromLocalFile(d))
