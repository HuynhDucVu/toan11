"""Tab «Rà soát»: kiểm tra đáp án – lời giải – LaTeX, tự sửa, bỏ câu sai."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSplitter, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)
from ... import review as rv
from ...parser import parse_file
from ..common import TEN_LOAI, latex_editor
from ..dialogs.edit import EditDialog

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ReviewPanel(QWidget):
    """Tab «Rà soát»: kiểm tra đáp án – lời giải – LaTeX của cả kho hoặc một file, rồi sửa/xoá câu sai."""
    COLS = ["", "Mức", "Câu", "Loại", "ID", "Đáp án", "Vấn đề", "Tự sửa được"]

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        self.items = []          # [{src, idx, q, issues}]
        lay = QVBoxLayout(self)

        g = QGroupBox("Phạm vi rà soát")
        hl = QHBoxLayout(g)
        self.cb_src = QComboBox()
        self.cb_src.addItem("Kho câu hỏi đang mở", "bank")
        self.cb_src.addItem("Một file .tex", "file")
        self.e_file = QLineEdit()
        self.e_file.setPlaceholderText("chọn file .tex cần rà soát")
        bf = QPushButton("…")
        bf.setFixedWidth(40)
        bf.clicked.connect(self.pick_file)
        self.cb_show = QComboBox()
        self.cb_show.addItem("Hiện câu có Lỗi hoặc Cảnh báo", "all")
        self.cb_show.addItem("Chỉ hiện câu có Lỗi", "loi")
        b = QPushButton("RÀ SOÁT")
        b.setObjectName("primary")
        b.clicked.connect(self.run)
        for w_, st in ((QLabel("Nguồn:"), 0), (self.cb_src, 0), (self.e_file, 1), (bf, 0), (self.cb_show, 0), (b, 0)):
            hl.addWidget(w_, st)
        self.cb_src.currentIndexChanged.connect(lambda: self.e_file.setEnabled(self.cb_src.currentData() == "file"))
        self.e_file.setEnabled(False)
        lay.addWidget(g)

        self.summary = QLabel("Chọn nguồn rồi bấm <b>RÀ SOÁT</b>. Phần mềm kiểm tra: số phương án và \\True, "
                              "phương án trùng, lời giải «Chọn X» lệch đáp án, lời giải Đúng/Sai ngược đánh dấu, "
                              "đáp án trả lời ngắn (là số, ≤ 4 kí tự, có trong lời giải), lỗi LaTeX "
                              "(ngoặc, $, \\begin/\\end, \\left/\\right), thiếu ID, thiếu lời giải.")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)

        split = QSplitter(Qt.Orientation.Vertical)
        self.t = QTableWidget(0, len(self.COLS))
        self.t.setHorizontalHeaderLabels(self.COLS)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for c, w_ in enumerate((30, 80, 150, 100, 90, 70)):
            self.t.setColumnWidth(c, w_)
        self.t.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.t.setColumnWidth(7, 280)
        self.t.itemSelectionChanged.connect(self.on_select)
        self.t.doubleClicked.connect(lambda *_: self.edit())
        split.addWidget(self.t)
        self.code = latex_editor(read_only=True)
        split.addWidget(self.code)
        split.setSizes([420, 260])
        lay.addWidget(split, 1)

        g = QGroupBox("Kiểm tra nâng cao")
        gv = QHBoxLayout(g)
        for text, fn, tip in (
                ("🤖 AI giải & kiểm tra đáp án", self.ai_check,
                 "AI giải lại các câu đã đánh dấu (hoặc mọi câu đang hiện) và so đáp án với đáp án \\True. Lệch đáp án ⇒ lỗi «AI: đáp án khác». Không tự đổi đáp án."),
                ("Bổ sung lời giải thiếu bằng AI", self.apply_ai_solutions,
                 "Ghi lời giải do AI viết cho các câu CHƯA có lời giải (bấm «AI giải & kiểm tra» trước). Đáp án không đổi."),
                ("Xoá câu trùng lặp (giữ 1 câu)", self.dedupe,
                 "Nhóm các câu giống hệt nhau, chỉ giữ 1 câu mỗi nhóm (ưu tiên câu có lời giải và ID đầy đủ)."),
                ("Đánh dấu phương án trùng", self.check_dup_choices,
                 "Đánh dấu các câu có hai phương án giống nhau (vd A và C cùng là 3).")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.clicked.connect(fn)
            gv.addWidget(b)
        lay.addWidget(g)

        g = QGroupBox("Sửa tự động")
        gv = QVBoxLayout(g)
        fx = QHBoxLayout()
        fx2 = QHBoxLayout()
        gv.addLayout(fx)
        gv.addLayout(fx2)
        fx.addWidget(QLabel("Khi đáp án lệch lời giải:"))
        self.cb_policy = QComboBox()
        self.cb_policy.addItem("Tin lời giải → sửa đánh dấu \\True", rv.THEO_LOI_GIAI)
        self.cb_policy.addItem("Tin đáp án → sửa chữ trong lời giải", rv.THEO_DAP_AN)
        self.cb_policy.currentIndexChanged.connect(self.fill)
        fx.addWidget(self.cb_policy)
        self.c_concl = QCheckBox("Thêm câu kết luận còn thiếu («Chọn đáp án X», «Vậy đáp án là …»)")
        self.c_concl.setChecked(True)
        self.c_concl.toggled.connect(self.fill)
        fx.addStretch()
        fx2.addWidget(self.c_concl)
        fx2.addStretch()
        fx = fx2
        b = QPushButton("Sửa các câu đã đánh dấu")
        b.clicked.connect(self.fix_checked)
        fx.addWidget(b)
        b = QPushButton("⚡ SỬA TỰ ĐỘNG + BỎ CÂU SAI")
        b.setObjectName("primary")
        b.setToolTip("Sửa mọi câu sửa được, sau đó xoá những câu vẫn còn Lỗi")
        b.clicked.connect(self.fix_all_and_remove)
        fx.addWidget(b)
        lay.addWidget(g)

        row = QHBoxLayout()
        for text, fn in (("Đánh dấu mọi câu Lỗi", self.check_errors), ("Đánh dấu câu sửa được", self.check_fixable),
                         ("Bỏ đánh dấu", self.uncheck_all),
                         ("Sửa tay (kho)", self.edit), ("Xuất báo cáo CSV…", self.export_csv)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        self.b_del = QPushButton("Xoá các câu đã đánh dấu")
        self.b_del.setObjectName("primary")
        self.b_del.clicked.connect(self.delete_checked)
        row.addWidget(self.b_del)
        lay.addLayout(row)

    # ---------------------------------------------------------------- kiểm tra nâng cao
    def _progress_worker(self, fn, title, n):
        from PySide6.QtWidgets import QProgressDialog
        from ..workers import TaskWorker
        import time
        from PySide6.QtWidgets import QApplication
        w = TaskWorker(fn, with_progress=True)
        dlg = QProgressDialog(title, "Dừng", 0, max(n, 1), self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        w.progress.connect(lambda i, _n: dlg.setValue(i))
        dlg.canceled.connect(w.requestInterruption)
        w.start()
        # vòng lặp sự kiện thay cho dlg.exec(): tác vụ xong trước khi hộp thoại mở thì không bị treo
        while not w.isFinished():
            QApplication.processEvents()
            time.sleep(0.02)
        dlg.close()
        w.wait()
        return w

    def ai_check(self):
        """AI giải lại từng câu (đã đánh dấu, hoặc mọi câu đang hiện nếu chưa đánh dấu) và so đáp án."""
        from ..dialogs.ai_settings import ensure_client
        from ... import aitasks
        items = self.checked() or list(self.items)
        if not items:
            QMessageBox.information(self, "AI kiểm tra", "Chưa có câu nào. Bấm RÀ SOÁT trước.")
            return
        if QMessageBox.question(self, "AI kiểm tra", f"AI sẽ giải lại {len(items)} câu (mất khoảng vài giây mỗi câu, "
                                "tốn lượt gọi AI). Tiếp tục?") != QMessageBox.StandardButton.Yes:
            return
        client = ensure_client(self.win)
        if client is None:
            return

        def job(progress, should_stop):
            out = []
            for k, it in enumerate(items):
                if should_stop():
                    break
                progress(k, len(items))
                out.append((it, aitasks.make_solution(client, it["q"], overwrite=False)))
            return out
        w = self._progress_worker(job, "AI đang giải lại các câu…", len(items))
        if w.error:
            QMessageBox.warning(self, "AI kiểm tra", w.error)
            return
        n_lech = n_thieu = 0
        for it, prop in (w.result or []):
            it["ai"] = prop
            new = [i for i in prop.issues if i.code in ("ai_dap_an", "ai_ghi_chu")]
            if any(i.code == "ai_dap_an" for i in new):
                n_lech += 1
            if not it["q"].solution.strip() and prop.question.solution.strip():
                n_thieu += 1
            codes = {i.code for i in it["issues"]}
            it["issues"] = it["issues"] + [i for i in new if i.code not in codes]
            it["level"] = rv.worst(it["issues"]) or it["level"]
        self.items.sort(key=lambda it: it["level"] != rv.LOI)
        self.fill()
        QMessageBox.information(self, "AI kiểm tra", f"Đã kiểm tra {len(w.result or [])} câu.\n"
                                f"• Đáp án AI khác đáp án đang đánh dấu: {n_lech} câu (đã thêm lỗi «AI: đáp án khác», "
                                "kiểm tra tay trước khi sửa).\n"
                                f"• Câu chưa có lời giải, AI đã viết được: {n_thieu} câu (bấm «Bổ sung lời giải thiếu bằng AI»).")

    def apply_ai_solutions(self):
        items = [it for it in self.items if it.get("ai") and not it["q"].solution.strip()
                 and it["ai"].question.solution.strip()]
        if not items:
            QMessageBox.information(self, "Bổ sung lời giải", "Chưa có câu thiếu lời giải nào do AI viết. "
                                    "Bấm «AI giải & kiểm tra đáp án» trước.")
            return
        self.commit([(it, it["ai"].question) for it in items], [], "Bổ sung lời giải thiếu bằng AI")

    def dedupe(self):
        """Xoá câu trùng giống hệt: kho → quét cả kho; file → giữ câu đầu tiên mỗi nhóm trùng."""
        if self.cb_src.currentData() == "bank":
            from ... import cleanup
            res = cleanup.scan(self.win.bank, find_wrong=False, find_exact=True, find_near=False)
            ids = sorted(res.dup_exact)
            if not ids:
                QMessageBox.information(self, "Câu trùng", "Không có câu trùng giống hệt trong kho.")
                return
            if QMessageBox.question(self, "Câu trùng", f"Có {len(ids)} câu trùng lặp. Giữ 1 câu mỗi nhóm và xoá "
                                    f"{len(ids)} câu còn lại?\n(Khôi phục được ở Câu hỏi → Khôi phục câu đã xoá.)") \
                    != QMessageBox.StandardButton.Yes:
                return
            cleanup.apply(self.win.bank, ids)
            self.win.build_tree()
            self.win.refresh()
            self.run()
            QMessageBox.information(self, "Câu trùng", f"Đã xoá {len(ids)} câu trùng.")
            return
        p = self.e_file.text().strip()
        if not p or not os.path.exists(p):
            QMessageBox.information(self, "Câu trùng", "Chọn file .tex trước.")
            return
        seen, removes = {}, []
        for q in parse_file(p):
            if q.fingerprint in seen:
                removes.append({"q": q})
            else:
                seen[q.fingerprint] = q
        if not removes:
            QMessageBox.information(self, "Câu trùng", "File không có câu trùng giống hệt.")
            return
        self.commit([], removes, "Xoá câu trùng lặp")

    def check_dup_choices(self):
        n = 0
        for r, it in enumerate(self.items):
            on = any(i.code == "pa_trung" for i in it["issues"])
            n += on
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if on else Qt.CheckState.Unchecked)
        QMessageBox.information(self, "Phương án trùng", f"Đã đánh dấu {n} câu có phương án giống nhau."
                                if n else "Không có câu nào có phương án giống nhau trong danh sách hiện tại.")

    def pick_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file .tex", self.win.settings.value("last_dir", ""),
                                           "LaTeX (*.tex)")
        if p:
            self.e_file.setText(p)
            self.cb_src.setCurrentIndex(1)

    def run(self):
        mode = self.cb_src.currentData()
        if mode == "file":
            p = self.e_file.text().strip()
            if not p or not os.path.exists(p):
                self.pick_file()
                p = self.e_file.text().strip()
                if not p:
                    return
            qs = parse_file(p)
            src = [(f"{os.path.basename(p)} – câu {i}", q) for i, q in enumerate(qs, 1)]
            base = os.path.dirname(os.path.abspath(p))
        else:
            qs = self.win.bank.search()
            src = [(f"Kho #{q.db_id}", q) for q in qs]
            base = None
        only_err = self.cb_show.currentData() == "loi"
        self.items = []
        n_err = n_warn = 0
        for label, q in src:
            iss = rv.review_question(q, base)
            lv = rv.worst(iss)
            n_err += lv == rv.LOI
            n_warn += lv == rv.CANH_BAO
            if lv and (lv == rv.LOI or not only_err):
                self.items.append({"label": label, "q": q, "issues": iss, "level": lv})
        self.items.sort(key=lambda it: it["level"] != rv.LOI)
        self.fill()
        self.summary.setText(f"Đã rà soát <b>{len(src)}</b> câu: <span style='color:#c00000'><b>{n_err}</b> câu có lỗi</span>, "
                             f"<span style='color:#b36b00'><b>{n_warn}</b> câu có cảnh báo</span>, "
                             f"<span style='color:#0b7a0b'><b>{len(src) - n_err - n_warn}</b> câu đạt</span>."
                             + ("" if mode == "bank" else " Xoá câu sẽ lưu thành <b>file mới</b>, file gốc giữ nguyên."))

    def fill(self):
        self.t.setRowCount(len(self.items))
        for r, it in enumerate(self.items):
            q = it["q"]
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.t.setItem(r, 0, chk)
            color = QColor("#c00000") if it["level"] == rv.LOI else QColor("#b36b00")
            fixed, done = self.plan_fix(q)
            it["fix"] = (fixed, done)
            vals = [it["level"], it["label"], TEN_LOAI[q.qtype], q.id_code, q.answer_text,
                    " • ".join(i.msg for i in it["issues"]), ("🔧 " + "; ".join(done)) if done else "—"]
            for c, v in enumerate(vals, 1):
                cell = QTableWidgetItem(str(v))
                if c in (1, 6):
                    cell.setForeground(color)
                if c == 7 and done:
                    cell.setForeground(QColor("#0b7a0b"))
                cell.setToolTip("\n".join(f"[{i.level}] {i.msg}" for i in it["issues"]))
                self.t.setItem(r, c, cell)
        self.code.clear()

    def on_select(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if rows and rows[0] < len(self.items):
            it = self.items[rows[0]]
            head = "\n".join(f"% [{i.level}] {i.msg}" for i in it["issues"])
            self.code.setPlainText(head + "\n" + (it["q"].raw or it["q"].to_latex()))

    # ---------------------------------------------------------- tự sửa
    def plan_fix(self, q):
        """Câu sau khi tự sửa + danh sách việc sẽ làm (chưa ghi gì)."""
        fixed, done = rv.fix_question(q, self.cb_policy.currentData())
        if self.c_concl.isChecked():
            fixed2, added = rv.add_conclusion(fixed)
            if added:
                fixed = fixed2
                done = done + ["Thêm câu kết luận"]
        return fixed, done

    def check_fixable(self):
        for r, it in enumerate(self.items):
            ok = bool(it.get("fix", (None, []))[1])
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if ok else Qt.CheckState.Unchecked)

    def commit(self, changes, removes, title) -> bool:
        """Ghi các thay đổi: changes = [(item, câu_mới)], removes = [item]. Kho: ghi thẳng; file: lưu file mới."""
        if not changes and not removes:
            QMessageBox.information(self, title, "Không có câu nào cần sửa hoặc xoá.")
            return False
        if self.cb_src.currentData() == "bank":
            msg = f"Sửa {len(changes)} câu và xoá {len(removes)} câu trong kho?"
            if QMessageBox.question(self, title, msg + "\nNên sao lưu kho trước (Tệp → Sao lưu kho).") \
                    != QMessageBox.StandardButton.Yes:
                return False
            for it, nq in changes:
                self.win.bank.update(it["q"].db_id, nq)
            if removes:
                self.win.bank.delete([it["q"].db_id for it in removes])
            self.win.build_tree()
            self.win.refresh()
            QMessageBox.information(self, title, f"Đã sửa {len(changes)} câu, xoá {len(removes)} câu khỏi kho.")
        else:
            src = self.e_file.text().strip()
            base, ext = os.path.splitext(src)
            out, _ = QFileDialog.getSaveFileName(self, "Lưu file đã rà soát", base + "_dasoat" + ext, "LaTeX (*.tex)")
            if not out:
                return False
            with open(src, encoding="utf-8") as f:
                text = f.read()
            text, n_fix = rv.replace_questions_text(text, [(it["q"].raw, nq.to_latex()) for it, nq in changes])
            text, n_del = rv.remove_questions_text(text, [it["q"].raw for it in removes])
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, title, f"Đã sửa {n_fix} câu, bỏ {n_del} câu.\nLưu thành: {out}\n"
                                    "(file gốc giữ nguyên)")
            self.e_file.setText(out)
        self.run()
        return True

    def fix_checked(self):
        items = self.checked()
        if not items:
            QMessageBox.information(self, "Sửa câu", "Chưa đánh dấu câu nào (cột đầu tiên). "
                                    "Bấm «Đánh dấu câu sửa được» để chọn nhanh.")
            return
        changes = [(it, it["fix"][0]) for it in items if it.get("fix", (None, []))[1]]
        self.commit(changes, [], "Sửa tự động")

    def fix_all_and_remove(self):
        """Một bước: sửa mọi câu sửa được, rồi bỏ các câu vẫn còn Lỗi sau khi sửa."""
        if not self.items:
            self.run()
        changes, removes = [], []
        for it in self.items:
            nq, done = it.get("fix", (it["q"], []))
            if done:
                changes.append((it, nq))
            if rv.worst(rv.review_question(nq if done else it["q"])) == rv.LOI:
                removes.append(it)
        changes = [(it, nq) for it, nq in changes if it not in removes]
        self.commit(changes, removes, "Sửa tự động + bỏ câu sai")

    def checked(self):
        return [self.items[r] for r in range(self.t.rowCount())
                if self.t.item(r, 0).checkState() == Qt.CheckState.Checked]

    def check_errors(self):
        for r, it in enumerate(self.items):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if it["level"] == rv.LOI else Qt.CheckState.Unchecked)

    def uncheck_all(self):
        for r in range(self.t.rowCount()):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Unchecked)

    def edit(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if not rows:
            return
        q = self.items[rows[0]]["q"]
        if q.db_id is None:
            QMessageBox.information(self, "Sửa câu", "Câu này nằm trong file .tex – hãy sửa trực tiếp trong file, "
                                    "hoặc nạp file vào kho rồi rà soát kho.")
            return
        if EditDialog(self.win, q.db_id).exec():
            self.win.refresh()
            self.run()

    def delete_checked(self):
        items = self.checked()
        if not items:
            QMessageBox.information(self, "Xoá câu", "Chưa đánh dấu câu nào (cột đầu tiên).")
            return
        if self.cb_src.currentData() == "bank":
            if QMessageBox.question(self, "Xoá câu", f"Xoá {len(items)} câu khỏi kho?\n"
                                    "Nên sao lưu kho trước (Tệp → Sao lưu kho).") != QMessageBox.StandardButton.Yes:
                return
            self.win.bank.delete([it["q"].db_id for it in items])
            self.win.build_tree()
            self.win.refresh()
            QMessageBox.information(self, "Xoá câu", f"Đã xoá {len(items)} câu khỏi kho.")
        else:
            src = self.e_file.text().strip()
            base, ext = os.path.splitext(src)
            out, _ = QFileDialog.getSaveFileName(self, "Lưu file đã bỏ câu sai", base + "_dasoat" + ext, "LaTeX (*.tex)")
            if not out:
                return
            with open(src, encoding="utf-8") as f:
                text, n = rv.remove_questions_text(f.read(), [it["q"].raw for it in items])
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Xoá câu", f"Đã bỏ {n} câu, lưu thành\n{out}\n(file gốc giữ nguyên)")
            self.e_file.setText(out)
        self.run()

    def export_csv(self):
        if not self.items:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Xuất báo cáo rà soát", "bao_cao_ra_soat.csv", "CSV (*.csv)")
        if not p:
            return
        import csv
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w_ = csv.writer(f)
            w_.writerow(["Câu", "Loại", "ID", "Đáp án", "Mức", "Vấn đề"])
            for it in self.items:
                for i in it["issues"]:
                    w_.writerow([it["label"], it["q"].qtype, it["q"].id_code, it["q"].answer_text, i.level, i.msg])
        QMessageBox.information(self, "Báo cáo", f"Đã lưu {p}")
