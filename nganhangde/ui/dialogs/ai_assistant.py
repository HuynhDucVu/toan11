"""Trợ lý AI: sinh câu tương tự, bù câu thiếu ma trận, PDF → LaTeX, chấm tự luận.

Mọi câu AI sinh ra hiện trong bảng để giáo viên duyệt (có kết quả rà soát), rồi mới thêm vào kho / lưu file.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QDialog, QDoubleSpinBox, QFileDialog, QFormLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QProgressDialog, QPushButton,
    QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from ..common import latex_editor
from ..workers import TaskWorker
from .ai_settings import AiSettingsDialog, ensure_client

if TYPE_CHECKING:
    from ..main_window import MainWindow


class AiAssistantDialog(QDialog):
    def __init__(self, win: MainWindow, tab: int = 0):
        super().__init__(win)
        self.win = win
        self.props = []
        self.setWindowTitle("Trợ lý AI")
        self.resize(1100, 720)
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.l_prov = QLabel()
        top.addWidget(self.l_prov)
        top.addStretch()
        b = QPushButton("Cài đặt AI…")
        b.clicked.connect(lambda: (AiSettingsDialog(win).exec(), self._show_provider()))
        top.addWidget(b)
        lay.addLayout(top)
        self._show_provider()
        self.tabs = QTabWidget()
        self.tabs.addTab(self._tab_similar(), "Câu tương tự")
        self.tabs.addTab(self._tab_gaps(), "Bù câu thiếu ma trận")
        self.tabs.addTab(self._tab_pdf(), "PDF → LaTeX")
        self.tabs.addTab(self._tab_grade(), "Chấm tự luận")
        self.tabs.setCurrentIndex(tab)
        self.tabs.setMaximumHeight(230)
        lay.addWidget(self.tabs)

        sp = QSplitter(Qt.Orientation.Horizontal)
        self.t = QTableWidget(0, 4)
        self.t.setHorizontalHeaderLabels(["Chọn", "Loại · ID", "Rà soát", "Nguồn"])
        self.t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.currentCellChanged.connect(lambda r, *_: self._show(r))
        sp.addWidget(self.t)
        self.view = latex_editor()
        self.view.setReadOnly(True)
        self.grade_view = QTextBrowser()
        right = QTabWidget()
        right.addTab(self.view, "LaTeX")
        right.addTab(self.grade_view, "Kết quả chấm")
        self.right = right
        sp.addWidget(right)
        sp.setSizes([480, 600])
        lay.addWidget(sp, 1)
        row = QHBoxLayout()
        note = QLabel("<i>AI có thể giải sai – kiểm tra đáp án, lời giải trước khi dùng. Câu có lỗi rà soát được "
                      "bỏ chọn sẵn.</i>")
        row.addWidget(note)
        row.addStretch()
        for text, fn in (("Thêm câu đã chọn vào kho", self.add_to_bank), ("Lưu ra file .tex…", self.save_tex)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)

    # ---------------------------------------------------------------- các tab
    def _show_provider(self):
        from ... import ai
        st = self.win.settings
        p = st.value("ai/provider", "gemini") or "gemini"
        m = st.value(ai._k(p, "model"), "") or ai.default_model(p)
        has = bool(st.value(ai._k(p, "key"), ""))
        self.l_prov.setText(f"Đang dùng: <b>{ai.provider_name(p)}</b> – {m}"
                            + ("" if has else " <span style='color:#c00000'>(chưa có khoá API)</span>"))

    def _tab_similar(self):
        w = QWidget()
        f = QFormLayout(w)
        self.sp_sim = QSpinBox()
        self.sp_sim.setRange(1, 10)
        self.sp_sim.setValue(3)
        self.c_harder = QCheckBox("Khó hơn câu mẫu một mức")
        f.addRow(QLabel("Chọn một hoặc vài câu trong bảng câu hỏi ở cửa sổ chính, AI soạn các câu mới cùng dạng, "
                        "cùng ID (giữ định dạng ex_test, có lời giải)."))
        f.addRow("Số câu cho mỗi câu mẫu", self.sp_sim)
        f.addRow(self.c_harder)
        b = QPushButton("🤖 Sinh câu tương tự")
        b.setObjectName("primary")
        b.clicked.connect(self.run_similar)
        f.addRow(b)
        return w

    def _tab_gaps(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.l_gaps = QLabel()
        self.l_gaps.setWordWrap(True)
        v.addWidget(QLabel("Dựa vào ma trận ở tab <b>Tạo đề</b>: dòng nào kho thiếu câu thì AI soạn thêm cho đủ "
                           "(dựa trên câu có sẵn cùng dạng, hoặc tên dạng trong Map ID)."))
        v.addWidget(self.l_gaps)
        row = QHBoxLayout()
        b = QPushButton("Kiểm tra ma trận")
        b.clicked.connect(self.check_gaps)
        b2 = QPushButton("🤖 Bù câu thiếu")
        b2.setObjectName("primary")
        b2.clicked.connect(self.run_gaps)
        row.addWidget(b)
        row.addWidget(b2)
        row.addStretch()
        v.addLayout(row)
        v.addStretch()
        return w

    def _tab_pdf(self):
        w = QWidget()
        f = QFormLayout(w)
        self.e_pdf = QLineEdit()
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(lambda: self._pick(self.e_pdf, "PDF (*.pdf)"))
        r = QHBoxLayout()
        r.addWidget(self.e_pdf)
        r.addWidget(b)
        self.sp_pages = QSpinBox()
        self.sp_pages.setRange(1, 30)
        self.sp_pages.setValue(10)
        f.addRow(QLabel("Chuyển đề PDF (file gốc hoặc bản chụp/scan) sang LaTeX ex_test. Chỉ dùng Gemini hoặc Claude. "
                        "Hình vẽ được đánh dấu %[HINH: …] để thầy/cô vẽ lại."))
        f.addRow("File PDF", r)
        f.addRow("Số trang mỗi lần gửi", self.sp_pages)
        b = QPushButton("🤖 Chuyển sang LaTeX")
        b.setObjectName("primary")
        b.clicked.connect(self.run_pdf)
        f.addRow(b)
        return w

    def _tab_grade(self):
        w = QWidget()
        h = QHBoxLayout(w)
        self.e_q = QPlainTextEdit()
        self.e_q.setPlaceholderText("Đề bài (để trống: lấy câu đang chọn ở cửa sổ chính)")
        self.e_rub = QPlainTextEdit()
        self.e_rub.setPlaceholderText("Đáp án – barem (để trống: lấy lời giải của câu)")
        self.e_ans = QPlainTextEdit()
        self.e_ans.setPlaceholderText("Bài làm của học sinh (gõ/dán chữ) – hoặc chọn file PDF bên dưới")
        col = QVBoxLayout()
        self.e_ans_pdf = QLineEdit()
        self.e_ans_pdf.setPlaceholderText("PDF bài làm (bản chụp)")
        b = QPushButton("…")
        b.clicked.connect(lambda: self._pick(self.e_ans_pdf, "PDF (*.pdf)"))
        self.sp_max = QDoubleSpinBox()
        self.sp_max.setRange(0.25, 10)
        self.sp_max.setSingleStep(0.25)
        self.sp_max.setValue(1.0)
        g = QPushButton("🤖 Chấm")
        g.setObjectName("primary")
        g.clicked.connect(self.run_grade)
        col.addWidget(QLabel("Điểm tối đa"))
        col.addWidget(self.sp_max)
        col.addWidget(self.e_ans_pdf)
        col.addWidget(b)
        col.addWidget(g)
        col.addStretch()
        for e in (self.e_q, self.e_rub, self.e_ans):
            h.addWidget(e)
        h.addLayout(col)
        return w

    def _pick(self, edit, filt):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file", "", filt)
        if p:
            edit.setText(p)

    # ---------------------------------------------------------------- chạy
    def _run(self, fn, *args, label="Đang hỏi AI…", progress=False, **kw):
        w = TaskWorker(fn, *args, with_progress=progress, **kw)
        dlg = QProgressDialog(label, "Dừng", 0, 0, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        w.progress.connect(lambda i, n: (dlg.setMaximum(n), dlg.setValue(i)))
        dlg.canceled.connect(w.requestInterruption)
        w.finished.connect(dlg.close)
        w.start()
        dlg.exec()
        w.wait()
        if w.error:
            QMessageBox.warning(self, "Trợ lý AI", w.error)
            return None
        return w.result

    def _selected_questions(self):
        ids = self.win.selected_ids()
        return [q for q in (self.win.bank.get(i) for i in ids) if q is not None]

    def run_similar(self):
        from ... import aitasks
        qs = self._selected_questions()
        if not qs:
            QMessageBox.information(self, "Câu tương tự", "Chọn ít nhất một câu trong bảng câu hỏi ở cửa sổ chính.")
            return
        client = ensure_client(self.win)
        if client is None:
            return
        n, harder = self.sp_sim.value(), self.c_harder.isChecked()

        def job(progress, should_stop):
            out = []
            for k, q in enumerate(qs):
                if should_stop():
                    break
                progress(k, len(qs))
                out += aitasks.similar(client, q, n, harder)
            return out
        res = self._run(job, progress=True, label="AI đang soạn câu tương tự…")
        if res is not None:
            self._set_props(res)

    def check_gaps(self):
        from ... import aitasks
        from ...generator import Rule
        rules = [Rule.from_dict(r) for r in self.win.gen_panel.rules_dicts()]
        g = aitasks.gaps(self.win.bank, rules)
        self.l_gaps.setText("Ma trận đủ câu." if not g else
                            "Còn thiếu: " + "; ".join(f"dòng {i + 1} ({rules[i].qtype} {rules[i].id}) thiếu {n}"
                                                      for i, n in g))
        return rules, g

    def run_gaps(self):
        from ... import aitasks
        rules, g = self.check_gaps()
        if not g:
            return
        client = ensure_client(self.win)
        if client is None:
            return
        res = self._run(aitasks.fill_gaps, client, self.win.bank, rules, progress=True,
                        label="AI đang soạn câu bù ma trận…")
        if res is not None:
            self._set_props(res)

    def run_pdf(self):
        from ... import ai, aitasks
        p = self.e_pdf.text().strip()
        if not os.path.isfile(p):
            QMessageBox.information(self, "PDF → LaTeX", "Chọn file PDF.")
            return
        client = ensure_client(self.win)
        if client is None:
            return
        if client.provider not in ai.PDF_OK:
            QMessageBox.information(self, "PDF → LaTeX", "Chức năng này cần Gemini hoặc Claude – đổi ở Cài đặt AI.")
            return
        res = self._run(aitasks.pdf_to_latex, client, p, self.sp_pages.value(), progress=True,
                        label="AI đang đọc PDF…")
        if res is not None:
            self._set_props(res)
            if not res:
                QMessageBox.information(self, "PDF → LaTeX", "Không nhận ra câu hỏi nào trong file.")

    def run_grade(self):
        from ... import ai, aitasks
        qs = self._selected_questions()
        qtext = self.e_q.toPlainText().strip() or (qs[0].stem if qs else "")
        rubric = self.e_rub.toPlainText().strip() or (qs[0].solution if qs else "")
        if not qtext:
            QMessageBox.information(self, "Chấm tự luận", "Nhập đề bài hoặc chọn câu trong kho.")
            return
        pdf = self.e_ans_pdf.text().strip()
        ans = self.e_ans.toPlainText().strip()
        if not ans and not os.path.isfile(pdf):
            QMessageBox.information(self, "Chấm tự luận", "Nhập bài làm của học sinh hoặc chọn file PDF bài làm.")
            return
        client = ensure_client(self.win)
        if client is None:
            return
        data = None
        if ans:
            kw = {"answer_text": ans}
        else:
            if client.provider not in ai.PDF_OK:
                QMessageBox.information(self, "Chấm tự luận", "Chấm từ PDF cần Gemini hoặc Claude.")
                return
            with open(pdf, "rb") as f:
                data = f.read()
            kw = {"answer_pdf": data}
        r = self._run(aitasks.grade_essay, client, qtext, rubric, self.sp_max.value(), label="AI đang chấm…", **kw)
        if r is None:
            return
        rows = "".join(f"<tr><td>{x.get('y', '')}</td><td align=center>{x.get('diem', '')}</td>"
                       f"<td>{x.get('ghi_chu', '')}</td></tr>" for x in r.get("chi_tiet", []))
        self.grade_view.setHtml(f"<h3>Điểm gợi ý: {r['diem']:g} / {self.sp_max.value():g}</h3>"
                                f"<p>{r.get('nhan_xet', '')}</p><table border=1 cellspacing=0 cellpadding=4>"
                                f"<tr><th>Ý</th><th>Điểm</th><th>Ghi chú</th></tr>{rows}</table>"
                                "<p><i>Điểm do AI gợi ý – giáo viên quyết định điểm cuối cùng.</i></p>")
        self.right.setCurrentIndex(1)

    # ---------------------------------------------------------------- kết quả
    def _set_props(self, props):
        self.props = props
        self.t.setRowCount(len(props))
        for r, p in enumerate(props):
            c = QTableWidgetItem()
            c.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            c.setCheckState(Qt.CheckState.Checked if p.ok else Qt.CheckState.Unchecked)
            self.t.setItem(r, 0, c)
            self.t.setItem(r, 1, QTableWidgetItem(f"{p.question.qtype} · {p.question.id_code or '—'}"))
            msg = "OK" if not p.issues else "; ".join(i.msg for i in p.issues[:2])
            it = QTableWidgetItem(msg)
            it.setForeground(QColor("#0b7a0b" if p.ok else "#c00000"))
            it.setToolTip("\n".join(f"[{i.level}] {i.msg}" for i in p.issues))
            self.t.setItem(r, 2, it)
            self.t.setItem(r, 3, QTableWidgetItem(p.source))
        if props:
            self.t.selectRow(0)
            self._show(0)
        self.right.setCurrentIndex(0)

    def _show(self, r):
        if 0 <= r < len(self.props):
            self.view.setPlainText(self.props[r].question.to_latex(True))

    def chosen(self):
        return [p.question for r, p in enumerate(self.props)
                if self.t.item(r, 0) and self.t.item(r, 0).checkState() == Qt.CheckState.Checked]

    def add_to_bank(self):
        qs = self.chosen()
        if not qs:
            return
        n = sum(1 for q in qs if self.win.bank.add(q))
        self.win.build_tree()
        self.win.refresh()
        QMessageBox.information(self, "Trợ lý AI", f"Đã thêm {n}/{len(qs)} câu vào kho (câu trùng bị bỏ qua). "
                                "Các câu được gắn nhãn %[AI] để dễ lọc lại.")

    def save_tex(self):
        qs = self.chosen()
        if not qs:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu câu AI", "cau_AI.tex", "LaTeX (*.tex)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write("\n\n".join(q.to_latex(True) for q in qs) + "\n")
