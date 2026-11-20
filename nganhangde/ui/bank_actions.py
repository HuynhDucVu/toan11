"""Các thao tác trên kho câu hỏi tách khỏi cửa sổ chính: tìm/thay thế, câu gần trùng, khôi phục câu đã xoá,
nhập Word, xuất câu ra Word/Moodle/online. Dùng như lớp trộn (mixin) của MainWindow."""
from __future__ import annotations

import os
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QInputDialog, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout)
from .. import review as rv, tools
from ..parser import parse_tex


class BankActionsMixin:
    """Phương thức dùng chung self.bank, self.settings, self.refresh()… của MainWindow."""

    def restore_deleted(self):
        rows = self.bank.con.execute(
            "SELECT h.hid, h.at, h.question_id, h.old_raw FROM history h WHERE h.action='xoá' AND "
            "NOT EXISTS (SELECT 1 FROM questions q WHERE q.id=h.question_id) ORDER BY h.hid DESC LIMIT 500").fetchall()
        if not rows:
            QMessageBox.information(self, "Khôi phục", "Không có câu nào đã xoá cần khôi phục.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Khôi phục câu đã xoá")
        dlg.resize(900, 500)
        lay = QVBoxLayout(dlg)
        t = QTableWidget(len(rows), 3)
        t.setHorizontalHeaderLabels(["Xoá lúc", "Câu", "Nội dung"])
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, h in enumerate(rows):
            for c, v in enumerate((h["at"].replace("T", " "), f"#{h['question_id']}", " ".join(h["old_raw"].split())[:200])):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, h["hid"])
                t.setItem(r, c, it)
        lay.addWidget(t)
        b = QPushButton("Khôi phục các câu đã chọn")
        b.setObjectName("primary")
        lay.addWidget(b)

        def go():
            sel = sorted({i.row() for i in t.selectedIndexes()})
            for r in sel:
                self.bank.restore(t.item(r, 0).data(Qt.ItemDataRole.UserRole))
            self.build_tree()
            self.refresh()
            QMessageBox.information(dlg, "Khôi phục", f"Đã khôi phục {len(sel)} câu.")
            dlg.accept()
        b.clicked.connect(go)
        dlg.exec()

    def find_replace(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Tìm và thay thế trong kho")
        f = QFormLayout(dlg)
        e_find, e_rep = QLineEdit(), QLineEdit()
        c_re = QCheckBox("Dùng biểu thức chính quy (regex)")
        scope = QComboBox()
        scope.addItem("Câu đang chọn", "sel")
        scope.addItem("Câu đang hiển thị (theo bộ lọc)", "vis")
        scope.addItem("Toàn bộ kho", "all")
        if not self.selected_ids():
            scope.setCurrentIndex(1)
        cs = {k: QCheckBox(v) for k, v in (("stem", "Đề bài"), ("choices", "Phương án / đáp án"),
                                           ("solution", "Lời giải"))}
        for c in cs.values():
            c.setChecked(True)
        f.addRow("Tìm", e_find)
        f.addRow("Thay bằng", e_rep)
        f.addRow("", c_re)
        f.addRow("Phạm vi", scope)
        row = QHBoxLayout()
        for c in cs.values():
            row.addWidget(c)
        f.addRow("Trong", row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Thay tất cả")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec() or not e_find.text():
            return
        ids = {"sel": self.selected_ids(), "vis": self.visible_ids(), "all": None}[scope.currentData()]
        try:
            n = self.bank.replace_text(e_find.text(), e_rep.text(), ids, c_re.isChecked(),
                                       tuple(k for k, c in cs.items() if c.isChecked()))
        except re.error as e:
            QMessageBox.warning(self, "Regex sai", str(e))
            return
        self.refresh()
        QMessageBox.information(self, "Thay thế", f"Đã sửa {n} câu. Có thể hoàn tác từng câu ở tab «Lịch sử sửa».")

    def near_dups(self):
        thr, ok = QInputDialog.getInt(self, "Câu gần trùng", "Độ giống tối thiểu (%)", 80, 30, 100)
        if not ok:
            return
        qs = self.bank.search()
        pairs = tools.near_duplicates(qs, thr / 100)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Câu gần trùng (≥ {thr}%) – {len(pairs)} cặp")
        dlg.resize(1100, 600)
        lay = QVBoxLayout(dlg)
        t = QTableWidget(len(pairs), 5)
        t.setHorizontalHeaderLabels(["Giống", "Câu 1", "Câu 2", "Nội dung câu 1", "Nội dung câu 2"])
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (i, j, sc) in enumerate(pairs):
            a, b_ = qs[i], qs[j]
            for c, v in enumerate((f"{sc:.0%}", f"#{a.db_id} [{a.id_code}]", f"#{b_.db_id} [{b_.id_code}]",
                                   " ".join(a.stem.split())[:150], " ".join(b_.stem.split())[:150])):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, b_.db_id)
                t.setItem(r, c, it)
        lay.addWidget(t)
        b = QPushButton("Xoá «Câu 2» của các cặp đã chọn")
        lay.addWidget(b)

        def go():
            ids = sorted({t.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in {i.row() for i in t.selectedIndexes()}})
            if ids and QMessageBox.question(dlg, "Xoá", f"Xoá {len(ids)} câu? (khôi phục được ở "
                                            "Câu hỏi → Khôi phục câu đã xoá)") == QMessageBox.StandardButton.Yes:
                self.bank.delete(ids)
                self.build_tree()
                self.refresh()
                dlg.accept()
        b.clicked.connect(go)
        dlg.exec()

    def import_word(self):
        from ..wordconv import PandocMissing, import_docx
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn file Word", self.settings.value("last_dir", ""),
                                                "Word (*.docx)")
        if not paths:
            return
        tag, ok = QInputDialog.getText(self, "Nhập từ Word", "Nhãn nguồn gắn cho các câu (có thể để trống):")
        if not ok:
            return
        lines = []
        for p in paths:
            try:
                tex = import_docx(p, tag.strip())
            except PandocMissing as e:
                QMessageBox.warning(self, "Thiếu pandoc", str(e))
                return
            except Exception as e:  # noqa: BLE001
                lines.append(f"✘ {os.path.basename(p)}: {e}")
                continue
            out = os.path.splitext(p)[0] + "_tuWord.tex"
            with open(out, "w", encoding="utf-8") as f:
                f.write(tex)
            qs = parse_tex(tex)
            added = sum(1 for q in qs if self.bank.add(q, p))
            bad = sum(1 for q in qs if rv.worst(rv.review_question(q)) == rv.LOI)
            lines.append(f"✔ {os.path.basename(p)}: nhận dạng {len(qs)} câu, thêm {added} câu vào kho, "
                         f"{bad} câu cần xem lại (chưa rõ đáp án…). Bản LaTeX: {os.path.basename(out)}")
        self.build_tree()
        self.refresh()
        QMessageBox.information(self, "Nhập từ Word", "\n".join(lines) + "\n\nNên mở tab «Rà soát» để kiểm tra lại.")

    def export_other(self):
        ids = self.selected_ids() or self.visible_ids()
        if not ids:
            return
        kinds = ["Word (.docx) – có đánh dấu đáp án và lời giải", "Moodle XML", "Bài làm online (HTML)"]
        k, ok = QInputDialog.getItem(self, "Xuất câu", f"Xuất {len(ids)} câu sang:", kinds, 0, False)
        if not ok:
            return
        qs = [self.bank.get(i) for i in ids]
        ext = {0: "Word (*.docx)", 1: "Moodle XML (*.xml)", 2: "HTML (*.html)"}[kinds.index(k)]
        p, _ = QFileDialog.getSaveFileName(self, "Lưu thành", "cau_hoi." + ext.split("*.")[1].rstrip(")"), ext)
        if not p:
            return
        try:
            if kinds.index(k) == 0:
                from ..wordconv import export_questions_docx
                export_questions_docx(qs, p)
            elif kinds.index(k) == 1:
                from ..online import export_moodle
                export_moodle(qs, p)
            else:
                from ..generator import ExamVersion, sections_from_questions
                from ..online import version_html
                v = ExamVersion("ÔN TẬP", sections_from_questions(qs))
                with open(p, "w", encoding="utf-8") as f:
                    f.write(version_html(v, ten_de="LUYỆN TẬP", thoi_gian=max(15, len(qs) * 3)))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Xuất câu", str(e))
            return
        QMessageBox.information(self, "Xuất câu", f"Đã xuất {len(qs)} câu ra\n{p}")
