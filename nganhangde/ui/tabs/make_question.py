"""Tab «Sinh câu»: sinh biến thể từ câu mẫu có tham số."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from ...exporter import export_questions
from ..common import latex_editor

if TYPE_CHECKING:
    from ..main_window import MainWindow


class MakeQuestionPanel(QWidget):
    """Tab «Sinh câu»: từ câu mẫu có tham số (%@ …, @{…}) sinh nhiều biến thể, kiểm tra rồi thêm vào kho."""
    HELP = ("<b>Cú pháp câu mẫu</b> (mỗi khai báo một dòng bắt đầu bằng <code>%@</code>):<br>"
            "<code>%@ a = 1..9</code> số nguyên · <code>%@ b = -5..5 khac 0</code> loại trừ · "
            "<code>%@ c = [2,3,5]</code> chọn trong danh sách · <code>%@ d = 0.5..3 buoc 0.5</code> số thực · "
            "<code>%@ D = b*b-4*a*c</code> biểu thức · <code>%@ dk: D &gt; 0</code> điều kiện.<br>"
            "Trong đề/phương án/lời giải viết <code>@{biểu thức}</code>. Hàm: <code>frac(p,q)</code> phân số tối giản, "
            "<code>dec(x,2)</code> thập phân dấu phẩy, <code>term(b,'x')</code> «+ 3x»/«- x», <code>coef(a,'x')</code>, "
            "<code>sq(12)</code>=2√3, <code>C(n,k)</code>, <code>A(n,k)</code>, <code>fact</code>, <code>gcd</code>…")

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        self.qs = []
        lay = QHBoxLayout(self)
        left = QVBoxLayout()
        lay.addLayout(left, 3)
        g = QGroupBox("Câu mẫu có tham số")
        gl = QVBoxLayout(g)
        row = QHBoxLayout()
        from ... import mathgen as mg
        for text, fn in (("Mẫu trắc nghiệm", lambda: self.ed.setPlainText(mg.SAMPLE)),
                         ("Mẫu trả lời ngắn", lambda: self.ed.setPlainText(mg.SAMPLE_KQ)),
                         ("Mở file mẫu…", self.open_tpl), ("Lưu mẫu…", self.save_tpl)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        gl.addLayout(row)
        self.ed = latex_editor()
        self.ed.setPlainText(win.settings.value("makeso/tpl", mg.SAMPLE))
        gl.addWidget(self.ed, 1)
        hl = QLabel(self.HELP)
        hl.setWordWrap(True)
        gl.addWidget(hl)
        left.addWidget(g, 1)

        right = QVBoxLayout()
        lay.addLayout(right, 2)
        g = QGroupBox("Sinh biến thể")
        f = QFormLayout(g)
        self.sp_n = QSpinBox()
        self.sp_n.setRange(1, 500)
        self.sp_n.setValue(10)
        self.e_seed = QLineEdit()
        self.e_seed.setPlaceholderText("để trống = ngẫu nhiên")
        f.addRow("Số biến thể mỗi câu mẫu", self.sp_n)
        f.addRow("Hạt giống (seed)", self.e_seed)
        b = QPushButton("🔢 SINH")
        b.setObjectName("primary")
        b.clicked.connect(self.run)
        f.addRow(b)
        right.addWidget(g)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        right.addWidget(self.msg)
        self.t = QTableWidget(0, 3)
        self.t.setHorizontalHeaderLabels(["#", "Đáp án", "Đề bài"])
        self.t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.itemSelectionChanged.connect(self.show)
        right.addWidget(self.t, 2)
        self.code = latex_editor(read_only=True)
        right.addWidget(self.code, 2)
        row = QHBoxLayout()
        for text, fn in (("Thêm tất cả vào kho", self.add_bank), ("Lưu ra file .tex…", self.save_tex)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        right.addLayout(row)

    def open_tpl(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở file câu mẫu", "", "LaTeX (*.tex)")
        if p:
            with open(p, encoding="utf-8") as f:
                self.ed.setPlainText(f.read())

    def save_tpl(self):
        p, _ = QFileDialog.getSaveFileName(self, "Lưu câu mẫu", "cau_mau.tex", "LaTeX (*.tex)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(self.ed.toPlainText())

    def run(self):
        from ... import mathgen as mg
        text = self.ed.toPlainText()
        self.win.settings.setValue("makeso/tpl", text)
        seed = int(self.e_seed.text()) if self.e_seed.text().strip().lstrip("-").isdigit() else None
        try:
            if text.count("\\begin{ex}") > 1:
                self.qs, warns = mg.generate_file(text, self.sp_n.value(), seed)
            else:
                self.qs, warns = mg.generate(text, self.sp_n.value(), seed)
        except mg.TemplateError as e:
            self.msg.setText(f"<span style='color:#c00000'><b>Lỗi câu mẫu:</b> {e}</span>")
            return
        self.t.setRowCount(len(self.qs))
        for r, q in enumerate(self.qs):
            for c, v in enumerate((str(r + 1), q.answer_text, " ".join(q.stem.split()))):
                self.t.setItem(r, c, QTableWidgetItem(v))
        self.msg.setText(f"<b>Đã sinh {len(self.qs)} câu</b> (đã kiểm tra đáp án, lời giải, LaTeX; loại câu trùng)."
                         + ("<br><span style='color:#b36b00'>" + "<br>".join(warns[:5]) + "</span>" if warns else ""))
        if self.qs:
            self.t.selectRow(0)

    def show(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if rows and rows[0] < len(self.qs):
            self.code.setPlainText(self.qs[rows[0]].to_latex())

    def add_bank(self):
        if not self.qs:
            return
        added = sum(1 for q in self.qs if self.win.bank.add(q, "sinh-so"))
        self.win.build_tree()
        self.win.refresh()
        QMessageBox.information(self, "Sinh câu", f"Đã thêm {added} câu vào kho ({len(self.qs) - added} câu đã có).")

    def save_tex(self):
        if not self.qs:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu các câu đã sinh", "cau_sinh.tex", "LaTeX (*.tex)")
        if p:
            export_questions(self.qs, p)
