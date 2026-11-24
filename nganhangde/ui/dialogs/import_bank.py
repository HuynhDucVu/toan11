"""«Nhập câu hỏi vào ngân hàng» (như MyLT 2026): chọn file nguồn, tuỳ chọn nhập, và các thao tác kho
(Khởi tạo, Sao lưu, Kiểm tra, Ghép, Khôi phục, Xoá lỗi, Xuất, Chuyển sang macOS/Linux)."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QVBoxLayout)

from ...appdirs import folder


class ImportBankDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.st = win, win.settings
        self.setWindowTitle("Nhập câu hỏi vào ngân hàng")
        self.resize(680, 300)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chú ý: Người dùng không nên xoá file gốc sau khi nhập câu hỏi."))
        g = QGroupBox("Chọn một hoặc nhiều file nguồn chứa câu hỏi")
        row = QHBoxLayout(g)
        row.addWidget(QLabel("Files"))
        self.cb_files = QComboBox()
        self.cb_files.setEditable(False)
        row.addWidget(self.cb_files, 1)
        b = QPushButton("Chọn")
        b.clicked.connect(lambda: self.choose(False))
        row.addWidget(b)
        b = QPushButton("Thêm")
        b.clicked.connect(lambda: self.choose(True))
        row.addWidget(b)
        lay.addWidget(g)
        self.paths: list[str] = []
        g = QGroupBox("Tuỳ chọn")
        row = QHBoxLayout(g)
        self.ck = {}
        for key, text, default in (("no_id5", "Không nhập câu ID5", False), ("skip_dups", "Bỏ qua câu trùng", True),
                                   ("check_dups", "Kiểm tra câu trùng", False), ("deep_dups", "Kiểm tra câu trùng sâu", False)):
            c = QCheckBox(text)
            c.setChecked(str(self.st.value("iw/" + key, default)).lower() == "true")
            self.ck[key] = c
            row.addWidget(c)
        row.addWidget(QLabel("Tỉ lệ"))
        self.cb_ratio = QComboBox()
        for p in range(50, 100, 5):
            self.cb_ratio.addItem(f"{p}%", p / 100)
        self.cb_ratio.setCurrentIndex(max(0, self.cb_ratio.findData(float(self.st.value("iw/ratio", 0.85)))))
        row.addWidget(self.cb_ratio)
        lay.addWidget(g)
        grid = QGridLayout()
        funcs = {"Hướng dẫn": self.help, "Khởi tạo": self.init_bank, "Sao lưu": self.win.backup_bank,
                 "Kiểm tra": self.check, "Ghép": self.win.merge_bank, "Nhập": self.do_import,
                 "Chuyển sang macOS, linux": self.other_os, "Khôi phục": self.restore, "Xoá lỗi": self.clean,
                 "Xuất": self.export, "Đóng": self.close}
        layout = ((("Hướng dẫn", 0), ("Khởi tạo", 1), ("Sao lưu", 2), ("Kiểm tra", 3), ("Ghép", 4), ("Nhập", 6)),
                  (("Chuyển sang macOS, linux", 0), ("Khôi phục", 1), ("Xoá lỗi", 2), ("Xuất", 3), ("Đóng", 6)))
        self.btn = {}
        for r, items in enumerate(layout):
            for text, c in items:
                b = QPushButton(text)
                b.clicked.connect(funcs[text])
                self.btn[text] = b
                grid.addWidget(b, r, c)
        grid.setColumnStretch(5, 1)
        self.btn["Nhập"].setObjectName("primary")
        lay.addLayout(grid)

    # ---------------------------------------------------------------- file nguồn
    def choose(self, add: bool):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex", self.st.value("last_dir", ""),
                                             "LaTeX (*.tex);;Tất cả (*.*)")
        if not ps:
            return
        self.st.setValue("last_dir", os.path.dirname(ps[0]))
        self.paths = (self.paths if add else []) + [p for p in ps if p not in (self.paths if add else [])]
        self.cb_files.clear()
        self.cb_files.addItems([f"{os.path.basename(p)}   ({os.path.dirname(p)})" for p in self.paths])
        self.cb_files.setToolTip(f"{len(self.paths)} file")

    def _save_opts(self):
        for k, c in self.ck.items():
            self.st.setValue("iw/" + k, c.isChecked())
        self.st.setValue("iw/ratio", self.cb_ratio.currentData())

    def do_import(self):
        if not self.paths:
            QMessageBox.information(self, "Nhập câu hỏi", "Bấm «Chọn» để chọn file .tex nguồn.")
            return
        self._save_opts()
        from .import_wizard import ImportWizard
        if self.ck["check_dups"].isChecked():
            self.ck["skip_dups"].setChecked(True)
            self.st.setValue("iw/skip_dups", True)
        ImportWizard(self.win, self.paths).exec()

    # ---------------------------------------------------------------- thao tác kho
    def help(self):
        QMessageBox.information(
            self, "Hướng dẫn", "1. «Chọn»/«Thêm» file .tex nguồn.\n2. Đặt tuỳ chọn rồi «Nhập» (rà soát từng câu trước khi nhập).\n"
                               "• Khởi tạo: tạo kho trống mới.  • Sao lưu / Khôi phục: sao chép kho ra / mở lại bản sao lưu.\n"
                               "• Kiểm tra, Xoá lỗi: dọn câu trùng, câu sai.  • Ghép: gộp một kho khác vào kho này.\n"
                               "• Xuất: ghi mọi câu của kho ra file .tex.")

    def init_bank(self):
        self.win.new_bank()
        self.win.mix_source_bar.refresh()

    def _scan(self, title: str, **kw):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QProgressDialog
        from ... import cleanup
        from ..workers import TaskWorker
        bank = self.win.bank
        w = TaskWorker(lambda progress, should_stop: cleanup.scan(bank, progress=progress, should_stop=should_stop, **kw),
                       with_progress=True)
        dlg = QProgressDialog("Đang quét kho…", "Dừng", 0, 0, self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        w.progress.connect(lambda i, n: (dlg.setMaximum(n), dlg.setValue(i)))
        dlg.canceled.connect(w.requestInterruption)
        w.finished.connect(dlg.close)
        w.start()
        dlg.exec()
        w.wait()
        if w.error:
            QMessageBox.warning(self, title, w.error)
            return None
        return w.result

    def check(self):
        """Kiểm tra (chỉ xem, không xoá gì): đếm câu sai và câu trùng giống hệt, nêu các lỗi hay gặp."""
        res = self._scan("Kiểm tra kho", find_wrong=True, find_exact=True, find_near=False)
        if res is None:
            return
        from collections import Counter
        top = Counter(r for rs in res.wrong.values() for r in rs).most_common(5)
        msg = (f"Kho có {res.total:,} câu.\n• Câu sai (lỗi khi rà soát): {len(res.wrong):,}\n"
               f"• Câu trùng giống hệt (thừa): {len(res.dup_exact):,}\n")
        if top:
            msg += "\nLỗi hay gặp:\n" + "\n".join(f"  – {r} ({n:,})" for r, n in top)
        msg += "\n\nKhông có câu nào bị xoá. Mở công cụ dọn kho để xem danh sách và xoá?"
        if QMessageBox.question(self, "Kiểm tra kho", msg) == QMessageBox.StandardButton.Yes:
            self.win.cleanup_bank()

    def clean(self):
        """Xoá lỗi: xoá ngay các câu sai (có ghi lịch sử, khôi phục được); không đụng tới câu trùng."""
        res = self._scan("Xoá lỗi", find_wrong=True, find_exact=False, find_near=False)
        if res is None:
            return
        ids = res.delete_ids(wrong=True, exact=False, near=False)
        if not ids:
            QMessageBox.information(self, "Xoá lỗi", "Không có câu sai nào.")
            return
        if QMessageBox.question(self, "Xoá lỗi", f"Xoá {len(ids):,} câu sai khỏi kho?\n(Khôi phục được ở Câu hỏi → "
                                                  "Khôi phục câu đã xoá.)") != QMessageBox.StandardButton.Yes:
            return
        from ... import cleanup
        cleanup.apply(self.win.bank, ids)
        self.win.build_tree()
        self.win.refresh()
        QMessageBox.information(self, "Xoá lỗi", f"Đã xoá {len(ids):,} câu.")

    def restore(self):
        d = folder("sao_luu")
        p, _ = QFileDialog.getOpenFileName(self, "Chọn bản sao lưu để mở lại", d, "Kho câu hỏi (*.db)")
        if p:
            self.win.open_bank(p)
            self.win.mix_source_bar.refresh()

    def export(self):
        n = self.win.bank.count()
        p, _ = QFileDialog.getSaveFileName(self, f"Xuất {n:,} câu ra .tex", os.path.join(folder("loc_id"), "ngan_hang.tex"),
                                           "LaTeX (*.tex)")
        if p:
            from ...exporter import export_questions
            export_questions(self.win.bank.search(), p)
            QMessageBox.information(self, "Xuất", f"Đã xuất {n:,} câu ra\n{p}")

    def other_os(self):
        QMessageBox.information(
            self, "macOS, Linux", "Kho của phần mềm này là file SQLite (.db) – chép nguyên file sang macOS/Linux là dùng được, "
                                  "không cần chuyển đổi. Dùng «Sao lưu» rồi mở file sao lưu trên máy kia.")
