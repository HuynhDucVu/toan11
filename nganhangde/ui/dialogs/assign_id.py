"""Bộ chọn ID theo Map ID và hộp thoại gán ID (gợi ý, Gemini)."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QProgressDialog, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from ... import review as rv
from ...idcode import parse_id
from ...idmap import IdTree
from ...idsuggest import MapSuggester, Suggester, combine
from ..common import TEN_MUC
from ..dialogs.ai_settings import GeminiSettingsDialog
from ..workers import AiWorker

if TYPE_CHECKING:
    from ..main_window import MainWindow


class IdPicker(QWidget):
    """Bộ chọn ID theo Map ID: Lớp → Môn → Chương → Bài → Dạng + Mức độ. Mỗi ô có lựa chọn «giữ nguyên»."""
    KEEP = None
    LABELS = ("Lớp", "Môn", "Chương", "Bài", "Dạng")

    def __init__(self, mapping: dict[str, str]):
        super().__init__()
        self.tree = IdTree(mapping)
        lay = QFormLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.cbs = []
        for i, lb in enumerate(self.LABELS):
            cb = QComboBox()
            cb.setMinimumWidth(320)
            cb.currentIndexChanged.connect(lambda _=0, i=i: self._changed(i))
            lay.addRow(lb, cb)
            self.cbs.append(cb)
        self.cb_md = QComboBox()
        self.cb_md.addItem("(giữ nguyên)", self.KEEP)
        for k, v in TEN_MUC.items():
            self.cb_md.addItem(f"[{k}] {v}", k)
        lay.addRow("Mức độ", self.cb_md)
        self.preview = QLabel()
        lay.addRow("ID", self.preview)
        self.cb_md.currentIndexChanged.connect(self._show)
        self._fill(0)

    def _fill(self, i):
        for j in range(i, 5):
            cb = self.cbs[j]
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("(giữ nguyên)", self.KEEP)
            parts = self.parts()[:j]
            if len(parts) == j and all(p is not self.KEEP for p in parts):
                for code, name in self.tree.children(parts):
                    cb.addItem(f"[{code}] {name}", code)
            cb.blockSignals(False)
        self._show()

    def _changed(self, i):
        if i < 4:
            self._fill(i + 1)
        self._show()

    def parts(self):
        return [cb.currentData() for cb in self.cbs]

    def level(self):
        return self.cb_md.currentData()

    def _show(self):
        p = ["?" if x is self.KEEP else x for x in self.parts()]
        md = self.level() or "?"
        self.preview.setText(f"<b>{p[0]}{p[1]}{p[2]}{md}{p[3]}-{p[4]}</b> &nbsp; (? = giữ nguyên theo ID cũ)")

    def apply_to(self, old_id: str) -> str | None:
        """Ghép phần đã chọn với ID cũ; trả về None nếu còn phần chưa xác định."""
        idc = parse_id(old_id) if old_id else None
        old = [idc.lop, idc.mon, idc.chuong, idc.bai, idc.dang] if idc else [None] * 5
        p = [o if x is self.KEEP else x for x, o in zip(self.parts(), old)]
        md = self.level() or (idc.muc_do if idc else None)
        if any(x is None for x in p[:4]) or md is None:
            return None
        return f"{p[0]}{p[1]}{p[2]}{md}{p[3]}" + (f"-{p[4]}" if p[4] else "")


class AssignIdDialog(QDialog):
    """Gán ID cho nhiều câu: gợi ý tự động (kho + Map ID), chọn theo Map ID, chỉ đổi mức độ; lưu vào kho hoặc file mới."""
    COLS = ["", "Câu", "ID hiện tại", "ID mới", "Độ giống", "Nội dung"]

    def __init__(self, win: MainWindow, questions, labels, source_file: str | None = None):
        super().__init__(win)
        self.win, self.qs, self.labels, self.src = win, questions, labels, source_file
        self.setWindowTitle("Gán ID" + (f" – {os.path.basename(source_file)}" if source_file else " – kho câu hỏi"))
        self.resize(1250, 760)
        self.mapping = win.bank.idmap()
        self.sugs = [[] for _ in questions]
        lay = QVBoxLayout(self)
        if not [k for k in self.mapping if not k.startswith("#")]:
            lay.addWidget(QLabel("<span style='color:#c00000'>Kho chưa có Map ID – vào <b>Công cụ → Giải nghĩa ID</b> "
                                 "để nạp file Map_ID.tex thì mới chọn ID theo tên chương/bài/dạng và gợi ý theo tên được.</span>"))
        top = QHBoxLayout()
        lay.addLayout(top, 1)

        left = QVBoxLayout()
        top.addLayout(left, 3)
        self.t = QTableWidget(len(questions), len(self.COLS))
        self.t.setHorizontalHeaderLabels(self.COLS)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for c, w_ in enumerate((30, 110, 90, 100, 70)):
            self.t.setColumnWidth(c, w_)
        self.t.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        for r, (q, lb) in enumerate(zip(questions, labels)):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.t.setItem(r, 0, chk)
            for c, v in ((1, lb), (2, q.id_code or "—"), (3, ""), (4, ""), (5, " ".join(q.stem.split())[:200])):
                it = QTableWidgetItem(v)
                if c != 3:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.t.setItem(r, c, it)
        self.t.itemSelectionChanged.connect(self.on_select)
        left.addWidget(self.t)
        row = QHBoxLayout()
        for text, fn in (("Chọn hết", lambda: self.set_all(True)), ("Bỏ chọn", lambda: self.set_all(False)),
                         ("Chọn câu thiếu ID", self.check_missing)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        left.addLayout(row)

        right = QVBoxLayout()
        top.addLayout(right, 2)
        g = QGroupBox("1. Gợi ý tự động")
        gl = QFormLayout(g)
        self.cb_scope = QComboBox()
        self.cb_scope.addItem("Mọi lớp", "")
        tree = IdTree(self.mapping)
        for code, name in tree.children([]):
            self.cb_scope.addItem(name, code)
        self.cb_def_md = QComboBox()
        for k, v in TEN_MUC.items():
            self.cb_def_md.addItem(f"{v} (nếu câu chưa có mức độ)", k)
        b = QPushButton("Tìm gợi ý cho các câu")
        b.clicked.connect(self.compute)
        gl.addRow("Phạm vi", self.cb_scope)
        gl.addRow("Mức độ", self.cb_def_md)
        gl.addRow("", b)
        self.sp_thr = QSpinBox()
        self.sp_thr.setRange(5, 100)
        self.sp_thr.setValue(35)
        self.sp_thr.setSuffix(" %")
        b2 = QPushButton("Nhận gợi ý tốt nhất cho câu đã chọn có độ giống ≥")
        b2.clicked.connect(self.accept_best)
        h = QHBoxLayout()
        h.addWidget(b2)
        h.addWidget(self.sp_thr)
        gl.addRow(h)
        self.sug_list = QTableWidget(0, 3)
        self.sug_list.setHorizontalHeaderLabels(["ID gợi ý", "Giống", "Theo"])
        self.sug_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.sug_list.verticalHeader().setVisible(False)
        self.sug_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sug_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sug_list.setMaximumHeight(130)
        self.sug_list.doubleClicked.connect(self.use_suggestion)
        gl.addRow(QLabel("Gợi ý cho câu đang chọn (nhấp đúp để dùng):"))
        gl.addRow(self.sug_list)
        right.addWidget(g)

        g = QGroupBox("🤖 Gán ID bằng AI (Gemini, Claude, OpenAI…)")
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        b = QPushButton("🤖 Gợi ý bằng AI cho các câu đã chọn")
        b.setObjectName("primary")
        b.clicked.connect(self.run_gemini)
        bs = QPushButton("Cài đặt…")
        bs.clicked.connect(lambda: GeminiSettingsDialog(self.win).exec())
        row.addWidget(b, 1)
        row.addWidget(bs)
        gl.addLayout(row)
        self.c_ai_level = QCheckBox("AI đánh giá luôn mức độ (N/H/V/C)")
        self.c_ai_level.setChecked(True)
        self.c_ai_fill = QCheckBox("Điền luôn kết quả vào cột «ID mới»")
        self.c_ai_fill.setChecked(True)
        gl.addWidget(self.c_ai_level)
        gl.addWidget(self.c_ai_fill)
        note = QLabel("<i>Dùng phạm vi ở mục 1 để giới hạn Map ID gửi đi (nhanh, đỡ tốn hạn mức). Nội dung câu hỏi "
                      "được gửi tới nhà cung cấp AI đã chọn. ID AI trả về luôn được đối chiếu với Map ID; mã không có thật bị loại. "
                      "Vẫn cần giáo viên duyệt lại trước khi lưu.</i>")
        note.setWordWrap(True)
        gl.addWidget(note)
        right.addWidget(g)

        g = QGroupBox("2. Chọn ID theo Map ID rồi áp cho câu đã chọn")
        gl = QVBoxLayout(g)
        self.picker = IdPicker(self.mapping)
        gl.addWidget(self.picker)
        b = QPushButton("Áp ID cho các câu đã chọn")
        b.clicked.connect(self.apply_picker)
        gl.addWidget(b)
        gl.addWidget(QLabel("<i>Để «giữ nguyên» ở mọi ô và chỉ chọn Mức độ ⇒ chỉ đổi mức độ.</i>"))
        right.addWidget(g)

        self.detail = QLabel()
        self.detail.setWordWrap(True)
        right.addWidget(self.detail)
        right.addStretch()

        row = QHBoxLayout()
        self.l_count = QLabel()
        row.addWidget(self.l_count)
        row.addStretch()
        ok = QPushButton("Lưu vào kho" if not source_file else "Lưu thành file mới…")
        ok.setObjectName("primary")
        ok.clicked.connect(self.save)
        cancel = QPushButton("Đóng")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.t.itemChanged.connect(self.update_count)
        self.check_missing()
        self.update_count()

    # --- tiện ích
    def set_all(self, v):
        for r in range(self.t.rowCount()):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)

    def check_missing(self):
        for r, q in enumerate(self.qs):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Unchecked if q.id_code else Qt.CheckState.Checked)

    def checked_rows(self):
        return [r for r in range(self.t.rowCount()) if self.t.item(r, 0).checkState() == Qt.CheckState.Checked]

    def set_new(self, r, code, score=None):
        self.t.item(r, 3).setText(code)
        self.t.item(r, 3).setForeground(QColor("#0b7a0b") if parse_id(code) else QColor("#c00000"))
        if score is not None:
            self.t.item(r, 4).setText(f"{score:.0%}")

    def update_count(self, *_):
        n = sum(1 for r in range(self.t.rowCount()) if self.t.item(r, 3) and self.t.item(r, 3).text().strip())
        self.l_count.setText(f"{n} câu có ID mới · {len(self.checked_rows())} câu đang chọn")

    # --- gợi ý
    def compute(self):
        prefix = self.cb_scope.currentData() or ""
        bank_items = [q for q in self.win.bank.search() if q.id_code.startswith(prefix)]
        bs = Suggester(bank_items) if bank_items else None
        ms = MapSuggester(self.mapping, prefix)
        rows = self.checked_rows() or list(range(len(self.qs)))
        for r in rows:
            q = self.qs[r]
            idc = parse_id(q.id_code) if q.id_code else None
            md = idc.muc_do if idc else self.cb_def_md.currentData()
            b = bs.suggest(q, 3, exclude_db_id=q.db_id) if bs and len(bs) else []
            m = ms.suggest(q, md, 3) if len(ms) else []
            self.sugs[r] = combine(b, m, 4)
            if self.sugs[r]:
                self.t.item(r, 4).setText(f"{self.sugs[r][0].score:.0%}")
                self.t.item(r, 4).setToolTip(self.sugs[r][0].id_code)
        self.on_select()

    def on_select(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        self.sug_list.setRowCount(0)
        if not rows:
            return
        r = rows[0]
        q = self.qs[r]
        names = self.win.bank.id_names(q.id_code) if q.id_code else []
        self.detail.setText("<b>Câu đang chọn:</b> " + " ".join(q.stem.split())[:300]
                            + ("<br><b>ID hiện tại:</b> " + " › ".join(names) if names else ""))
        sg = self.sugs[r]
        self.sug_list.setRowCount(len(sg))
        for i, x in enumerate(sg):
            src = (f"câu #{x.db_id} trong kho: {x.sample}" if x.db_id is not None else
                   x.sample if x.sample.startswith("AI:") else f"Map ID: {x.sample}")
            for c, v in enumerate((x.id_code, f"{x.score:.0%}", src)):
                it = QTableWidgetItem(v)
                it.setToolTip(src)
                self.sug_list.setItem(i, c, it)

    def use_suggestion(self, idx):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if rows:
            x = self.sugs[rows[0]][idx.row()]
            self.set_new(rows[0], x.id_code, x.score)
            self.update_count()

    def run_gemini(self):
        from ... import ai
        from ...idsuggest import Suggestion
        from .ai_settings import ensure_client
        st = self.win.settings
        client = ensure_client(self.win)
        if client is None:
            return
        model = f"{ai.provider_name(client.provider)} – {client.model}"
        rows = self.checked_rows() or list(range(len(self.qs)))
        qs = [self.qs[r] for r in rows]
        dlg = QProgressDialog("Đang hỏi AI…", "Dừng", 0, len(qs), self)
        dlg.setWindowTitle("Gán ID bằng AI")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        worker = AiWorker(client, qs, self.mapping, self.cb_scope.currentData() or "",
                          self.cb_def_md.currentData(), self.c_ai_level.isChecked(),
                          int(st.value("ai/batch", 10)))
        worker.progress.connect(lambda i, n: (dlg.setValue(i), dlg.setLabelText(f"Đã phân loại {i}/{n} câu…")))
        dlg.canceled.connect(worker.requestInterruption)
        worker.start()
        while worker.isRunning():
            QApplication.processEvents()
            worker.wait(50)
        dlg.close()
        if worker.error:
            QMessageBox.warning(self, "AI", worker.error)
            if not worker.results:
                return
        ok = 0
        for res in worker.results:
            r = rows[res.index]
            sug = Suggestion(res.id_code or (res.raw_code or "—"), res.score, None, f"AI: {res.reason}")
            self.sugs[r] = [sug] + [x for x in self.sugs[r] if not x.sample.startswith("AI:")]
            if res.id_code:
                ok += 1
                if self.c_ai_fill.isChecked():
                    self.set_new(r, res.id_code, res.score)
                    self.t.item(r, 4).setToolTip("AI: " + res.reason)
        self.update_count()
        self.on_select()
        QMessageBox.information(self, "AI", f"AI đã phân loại {ok}/{len(worker.results)} câu hợp lệ "
                                f"(mô hình {model}).\nCột «Độ giống» là độ tin cậy AI tự đánh giá – "
                                "xem lại các câu có độ tin cậy thấp trước khi lưu.")

    def accept_best(self):
        thr = self.sp_thr.value() / 100
        n = 0
        for r in self.checked_rows():
            if self.sugs[r] and self.sugs[r][0].score >= thr:
                self.set_new(r, self.sugs[r][0].id_code, self.sugs[r][0].score)
                n += 1
        self.update_count()
        QMessageBox.information(self, "Gợi ý", f"Đã điền ID gợi ý cho {n} câu (độ giống ≥ {thr:.0%}). "
                                "Kiểm tra lại cột «ID mới» trước khi lưu – có thể sửa trực tiếp trong ô.")

    def apply_picker(self):
        rows = self.checked_rows()
        bad = 0
        for r in rows:
            cur = self.t.item(r, 3).text().strip() or self.qs[r].id_code
            new = self.picker.apply_to(cur)
            if new:
                self.set_new(r, new)
            else:
                bad += 1
        self.update_count()
        if bad:
            QMessageBox.warning(self, "Gán ID", f"{bad} câu chưa có ID cũ nên phải chọn đủ Lớp, Môn, Chương, Bài "
                                "và Mức độ (không để «giữ nguyên»).")

    # --- lưu
    def save(self):
        changes, invalid = [], []
        for r, q in enumerate(self.qs):
            new = self.t.item(r, 3).text().strip().upper()
            if not new or new == q.id_code:
                continue
            if not parse_id(new):
                invalid.append(f"{self.labels[r]}: «{new}»")
                continue
            changes.append((q, new))
        if invalid:
            QMessageBox.warning(self, "ID sai dạng", "Các ID sau không đúng dạng 0D2N1-2:\n" + "\n".join(invalid[:15]))
            return
        if not changes:
            QMessageBox.information(self, "Gán ID", "Chưa có câu nào được đặt ID mới (cột «ID mới»).")
            return
        if self.src is None:
            for q, new in changes:
                q.set_id(new)
                self.win.bank.update(q.db_id, q)
            self.win.build_tree()
            self.win.refresh()
            QMessageBox.information(self, "Gán ID", f"Đã gán ID cho {len(changes)} câu trong kho.")
        else:
            base, ext = os.path.splitext(self.src)
            out, _ = QFileDialog.getSaveFileName(self, "Lưu file đã gán ID", base + "_ganID" + ext, "LaTeX (*.tex)")
            if not out:
                return
            with open(self.src, encoding="utf-8") as f:
                text = f.read()
            pairs = []
            for q, new in changes:
                old_raw = q.raw
                q.set_id(new)
                pairs.append((old_raw, q.raw))
            text, n = rv.replace_questions_text(text, pairs)
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Gán ID", f"Đã gán ID cho {n} câu, lưu thành\n{out}\n(file gốc giữ nguyên)")
        self.accept()
