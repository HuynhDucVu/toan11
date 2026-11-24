"""Dọn kho: ① lọc câu trùng (chỉ giữ 1 câu) – ② lọc câu sai. Xoá có ghi lịch sử, khôi phục được."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDoubleSpinBox, QHBoxLayout, QHeaderView, QLabel,
                               QMessageBox, QProgressDialog, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout)
from ... import cleanup
from ..workers import TaskWorker


class CleanupDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.res = win, None
        self.setWindowTitle("Dọn kho – lọc câu trùng và câu sai")
        self.resize(1050, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel(
            f"Kho có <b>{win.bank.count():,}</b> câu. <b>① Câu trùng</b>: nhóm các câu giống nhau, <b>chỉ giữ lại 1 câu</b> "
            "(ưu tiên câu có lời giải và ID đầy đủ). <b>② Câu sai</b>: câu lỗi LaTeX/đáp án khi rà soát. "
            "Xem danh sách rồi mới xoá; câu xoá <b>khôi phục được</b> (Câu hỏi → Khôi phục câu đã xoá)."))
        row = QHBoxLayout()
        self.c_exact = QCheckBox("Trùng giống hệt (sau chuẩn hoá)")
        self.c_exact.setChecked(True)
        self.c_near = QCheckBox("Trùng gần giống ≥")
        self.sp = QDoubleSpinBox()
        self.sp.setRange(60, 100)
        self.sp.setValue(95)
        self.sp.setSuffix(" %")
        self.c_wrong = QCheckBox("Tìm câu sai")
        self.c_wrong.setChecked(True)
        for w in (self.c_exact, self.c_near, self.sp, self.c_wrong):
            row.addWidget(w)
        row.addStretch()
        b = QPushButton("🔍 Quét kho")
        b.setObjectName("primary")
        b.clicked.connect(self.scan)
        row.addWidget(b)
        lay.addLayout(row)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["Loại", "Câu", "Giữ câu", "ID", "Nội dung / lí do"])
        self.t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        lay.addWidget(self.t)
        self.lb = QLabel("")
        lay.addWidget(self.lb)
        row = QHBoxLayout()
        self.b1 = QPushButton("① Xoá câu trùng (giữ 1 câu mỗi nhóm)")
        self.b1.setObjectName("primary")
        self.b2 = QPushButton("② Xoá câu sai")
        self.b3 = QPushButton("Xoá các dòng đã chọn")
        for x in (self.b1, self.b2, self.b3):
            row.addWidget(x)
            x.setEnabled(False)
        lay.addLayout(row)
        self.b1.clicked.connect(lambda: self.delete(cleanup.ScanResult.delete_ids, "trùng", wrong=False, exact=True, near=True))
        self.b2.clicked.connect(lambda: self.delete(cleanup.ScanResult.delete_ids, "sai", wrong=True, exact=False, near=False))
        self.b3.clicked.connect(self.delete_selected)

    def scan(self):
        bank = self.win.bank
        ex, nr, wr, th = self.c_exact.isChecked(), self.c_near.isChecked(), self.c_wrong.isChecked(), self.sp.value() / 100

        def job(progress, should_stop):
            return cleanup.scan(bank, find_wrong=wr, find_exact=ex, find_near=nr, threshold=th,
                                progress=progress, should_stop=should_stop)
        w = TaskWorker(job, with_progress=True)
        dlg = QProgressDialog("Đang quét kho…", "Dừng", 0, 0, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        w.progress.connect(lambda i, n: (dlg.setMaximum(n), dlg.setValue(i)))
        dlg.canceled.connect(w.requestInterruption)
        w.finished.connect(dlg.close)
        w.start()
        dlg.exec()
        w.wait()
        if w.error:
            QMessageBox.warning(self, "Dọn kho", w.error)
            return
        self.res = w.result
        self.fill()

    def fill(self):
        r, bank = self.res, self.win.bank
        rows = [("Sai", i, "", "; ".join(why)) for i, why in r.wrong.items()]
        rows += [("Trùng", i, k, "giống hệt") for i, k in r.dup_exact.items()]
        rows += [("Gần giống", i, k, f"{sc:.0%}") for i, (k, sc) in r.dup_near.items()]
        self.t.setRowCount(min(len(rows), 5000))
        for n, (kind, i, keep, note) in enumerate(rows[:5000]):
            q = bank.get(i)
            vals = (kind, f"#{i}", f"#{keep}" if keep != "" else "", q.id_code if q else "",
                    note if kind == "Sai" else (note + " – " + " ".join((q.stem if q else "").split())[:140]))
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, i)
                self.t.setItem(n, c, it)
        self.lb.setText(f"Quét {r.total:,} câu: <b>{len(r.dup_exact):,}</b> trùng giống hệt, <b>{len(r.dup_near):,}</b> "
                        f"gần giống, <b>{len(r.wrong):,}</b> câu sai."
                        + (" (Bảng chỉ hiện 5.000 dòng đầu; nút xoá áp dụng cho toàn bộ.)" if len(rows) > 5000 else ""))
        self.b1.setEnabled(bool(r.dup_exact or r.dup_near))
        self.b2.setEnabled(bool(r.wrong))
        self.b3.setEnabled(bool(rows))

    def _do(self, ids, what):
        if not ids:
            return
        if QMessageBox.question(self, "Xoá", f"Xoá {len(ids):,} câu {what}? Có thể khôi phục ở Câu hỏi → Khôi phục câu "
                                "đã xoá.") != QMessageBox.StandardButton.Yes:
            return
        cleanup.apply(self.win.bank, ids)
        self.win.build_tree()
        self.win.refresh()
        QMessageBox.information(self, "Dọn kho", f"Đã xoá {len(ids):,} câu. Quét lại để cập nhật danh sách.")
        self.res = None
        self.t.setRowCount(0)
        for x in (self.b1, self.b2, self.b3):
            x.setEnabled(False)

    def delete(self, fn, what, **kw):
        self._do(fn(self.res, **kw), what)

    def delete_selected(self):
        ids = sorted({self.t.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in {i.row() for i in self.t.selectedIndexes()}})
        self._do(ids, "đã chọn")
