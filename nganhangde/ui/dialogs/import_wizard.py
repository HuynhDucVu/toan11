"""Hộp thoại nhập .tex 3 bước: Rà soát – AI giải lại – Nhập (theo bản Gemini v4.6)."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)
from ... import importwiz as iw
from ..workers import TaskWorker
from PySide6.QtWidgets import QProgressDialog


class ImportWizard(QDialog):
    def __init__(self, win, paths):
        super().__init__(win)
        self.win, self.st = win, win.settings
        self.setWindowTitle("Nhập câu hỏi – 3 bước")
        self.resize(1000, 640)
        try:
            self.entries = iw.load(paths)
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(win, "Nhập", f"Không đọc được file: {e}")
            self.entries = []
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("<b>① Rà soát</b> → <b>② AI giải lại</b> (tuỳ chọn) → <b>③ Nhập vào kho</b>"))
        opts = QHBoxLayout()
        self.cks = {}
        for key, text in (("need_solution", "Bắt buộc có lời giải và đáp án"), ("skip_dups", "Bỏ qua câu trùng"),
                          ("deep_dups", "Kiểm tra trùng sâu"), ("no_id5", "Không nhập ID 5 ký tự"),
                          ("skip_errors", "Bỏ qua câu có lỗi")):
            c = QCheckBox(text)
            c.setChecked(bool(self.st.value("iw/" + key, key == "skip_dups", type=bool)))
            self.cks[key] = c
            opts.addWidget(c)
        lay.addLayout(opts)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["#", "Loại", "ID", "Rà soát", "Trạng thái"])
        self.t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.t)
        self.lb = QLabel("")
        lay.addWidget(self.lb)
        row = QHBoxLayout()
        self.b1 = QPushButton("① Rà soát")
        self.b2 = QPushButton("② AI giải lại câu có vấn đề")
        self.b3 = QPushButton("③ Nhập vào kho")
        self.b3.setObjectName("primary")
        self.b4 = QPushButton("Xuất .tex đã sửa…")
        for b in (self.b1, self.b2, self.b4, self.b3):
            row.addWidget(b)
        lay.addLayout(row)
        self.b1.clicked.connect(self.step1)
        self.b2.clicked.connect(self.step2)
        self.b3.clicked.connect(self.step3)
        self.b4.clicked.connect(self.export)
        self.step1()

    def options(self) -> iw.ImportOptions:
        for k, c in self.cks.items():
            self.st.setValue("iw/" + k, c.isChecked())
        return iw.ImportOptions(ratio=float(self.st.value("iw/ratio", 0.85)), **{k: c.isChecked() for k, c in self.cks.items()})

    def fill(self):
        self.t.setRowCount(len(self.entries))
        for r, e in enumerate(self.entries):
            msg = "; ".join(i.msg for i in e.issues)[:200]
            stt = ("Bỏ qua: " + e.skip) if e.skip else ("Nhập (AI đã sửa)" if e.ai_changed else "Sẽ nhập")
            for c, v in enumerate((str(r + 1), e.q.qtype, e.q.id_code, msg, stt)):
                it = QTableWidgetItem(v)
                if e.skip:
                    it.setForeground(Qt.GlobalColor.gray)
                elif any(i.level == "Lỗi" for i in e.issues):
                    it.setForeground(Qt.GlobalColor.red)
                self.t.setItem(r, c, it)
        n_ok = sum(1 for e in self.entries if not e.skip)
        n_bad = sum(1 for e in self.entries if e.issues)
        self.lb.setText(f"{len(self.entries)} câu · sẽ nhập {n_ok} · bỏ qua {len(self.entries) - n_ok} · có vấn đề {n_bad}")

    def step1(self):
        iw.review(self.entries, self.win.bank, self.options())
        self.fill()

    def step2(self):
        from .ai_settings import ensure_client
        client = ensure_client(self.win)
        if client is None:
            return
        ents = self.entries

        def job(progress, should_stop):
            return iw.ai_resolve(client, ents, True, progress=progress, should_stop=should_stop)
        w = TaskWorker(job, with_progress=True)
        dlg = QProgressDialog("AI đang giải lại…", "Dừng", 0, 0, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        w.progress.connect(lambda i, n: (dlg.setMaximum(n), dlg.setValue(i)))
        dlg.canceled.connect(w.requestInterruption)
        w.finished.connect(dlg.close)
        w.start()
        dlg.exec()
        w.wait()
        if w.error:
            QMessageBox.warning(self, "AI", w.error)
        self.fill()

    def step3(self):
        r = iw.commit(self.entries, self.win.bank)
        self.win.build_tree()
        self.win.refresh()
        from ...typecount import bank_counts, fmt
        QMessageBox.information(self, "Nhập", f"Đã thêm {r['added']} câu, bỏ qua {r['skipped']}, trùng {r['dup']}.\n\n"
                                f"ĐÃ NHẬP VÀO KHO: {fmt(r['by_type'])}\nKho hiện có: {fmt(bank_counts(self.win.bank))}")
        self.accept()

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Xuất .tex", os.path.join(self.st.value("last_dir", ""), "da_sua.tex"),
                                           "LaTeX (*.tex)")
        if p:
            n = iw.export_fixed(self.entries, p)
            QMessageBox.information(self, "Xuất", f"Đã ghi {n} câu vào {p}")
