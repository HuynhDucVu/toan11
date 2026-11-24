import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton,
    QStackedWidget, QVBoxLayout, QWidget,
)
from pydantic import BaseModel

from ..ai.essay_grader import grade_essay_with_ai
from ..ai.providers import AIConfig, AIProviderClient
from ..core.db import QuestionBankDB
from ..core.drawgen import (
    IntervalSpec, generate_function_graph_tikz, generate_linear_inequality_region_tikz,
    generate_number_line_tikz, generate_solid_geometry_tikz, generate_variation_table_tikz,
)
from ..core.parser import Question, parse_tex_questions
from ..exporters.pdfbuild import compile_tex_to_pdf
from ..exporters.topic_book import export_topic_book_tex
from .pdf_preview import make_qimage_from_pdf_page
from .workers import run_in_background


class _IDProposal(BaseModel):
    primary_id: str
    confidence: float
    reason: str


class _SimilarQuestion(BaseModel):
    qtype: str
    stem: str
    choices: list[str] = []
    correct: list[bool] = []
    short_ans: str = ""
    solution: str = ""
    suggested_id: str = ""


class TopicBookTab(QWidget):
    def __init__(self, db: QuestionBankDB, parent=None):
        super().__init__(parent)
        self.db = db
        lay = QVBoxLayout(self)
        form = QFormLayout()
        self.inp_filter_id = QLineEdit("1D*")
        self.inp_filter_kw = QLineEdit()
        self.inp_filter_kw.setPlaceholderText("Từ khóa lọc thêm (để trống nếu lấy toàn bộ theo ID)...")
        self.inp_title = QLineEdit("CHUYÊN ĐỀ ĐẠI SỐ VÀ GIẢI TÍCH 11")
        self.inp_author = QLineEdit("Tổ Toán")
        self.inp_school = QLineEdit("TRƯỜNG THPT")
        self.chk_toc = QCheckBox("Tự động tạo trang bìa và Mục lục (\\tableofcontents)")
        self.chk_toc.setChecked(True)
        self.chk_sol = QCheckBox("Kèm lời giải chi tiết (\\loigiai)")
        self.chk_sol.setChecked(True)
        form.addRow("Lọc theo mẫu ID (VD: 1D2*, 2H5*):", self.inp_filter_id)
        form.addRow("Lọc thêm từ khóa FTS5:", self.inp_filter_kw)
        form.addRow("Tên chuyên đề:", self.inp_title)
        form.addRow("Tác giả / Nhóm biên soạn:", self.inp_author)
        form.addRow("Tên trường:", self.inp_school)
        form.addRow("", self.chk_toc)
        form.addRow("", self.chk_sol)
        lay.addLayout(form)
        hb = QHBoxLayout()
        b_exp = QPushButton("Xuất quyển Chuyên đề (.tex)")
        b_pdf = QPushButton("Xuất & Biên dịch PDF ngay")
        b_exp.clicked.connect(lambda: self._export(False))
        b_pdf.clicked.connect(lambda: self._export(True))
        hb.addWidget(b_exp)
        hb.addWidget(b_pdf)
        lay.addLayout(hb)
        self.txt_log = QPlainTextEdit()
        self.txt_log.setReadOnly(True)
        lay.addWidget(self.txt_log)

    def _export(self, compile_pdf: bool):
        rows = self.db.search(keyword=self.inp_filter_kw.text(), id_glob=self.inp_filter_id.text(), limit=2000)
        qs = [p[0] for r in rows if (p := parse_tex_questions(r["raw"]))]
        if not qs:
            QMessageBox.warning(self, "Biên soạn chuyên đề", "Không tìm thấy câu hỏi nào khớp bộ lọc.")
            return
        out_tex, _ = QFileDialog.getSaveFileName(self, "Lưu tệp Chuyên đề", "chuyen_de.tex", "LaTeX (*.tex)")
        if not out_tex:
            return
        export_topic_book_tex(
            qs, out_tex, book_title=self.inp_title.text(), author=self.inp_author.text(),
            school=self.inp_school.text(), include_toc=self.chk_toc.isChecked(),
            solution_mode="inline" if self.chk_sol.isChecked() else "none",
        )
        self.txt_log.setPlainText(f"Đã xuất {len(qs)} câu hỏi thành chuyên đề tại:\n{out_tex}")
        if compile_pdf:
            self.txt_log.appendPlainText("Đang biên dịch PDF (2 lượt để tạo mục lục)...")
            run_in_background(
                compile_tex_to_pdf, out_tex, passes=2,
                on_finished=lambda r: self.txt_log.appendPlainText(
                    f"THÀNH CÔNG: {r.pdf_path}" if r.success else "LỖI:\n" + "\n".join(f"- Dòng {d.line_no}: {d.summary} -> {d.suggestion_vi}" for d in r.diagnostics)
                ),
                on_error=lambda e: self.txt_log.appendPlainText(e),
            )


class DrawStudioProTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        left, right = QVBoxLayout(), QVBoxLayout()
        self.cb_tool = QComboBox()
        self.cb_tool.addItems([
            "1. Đồ thị hàm số (Tiệm cận & Tích phân)",
            "2. Bảng biến thiên / Xét dấu (tkz-tab)",
            "3. Trục số & Miền nghiệm hệ BPT",
            "4. Hình học không gian 3D (Chóp / Lăng trụ)",
        ])
        self.stack = QStackedWidget()
        self.cb_tool.currentIndexChanged.connect(self.stack.setCurrentIndex)

        w1 = QWidget(); f1 = QFormLayout(w1)
        self.g_expr = QLineEdit("(\\x+1)/(\\x-1)")
        self.g_xmin = QDoubleSpinBox(); self.g_xmin.setRange(-20, 20); self.g_xmin.setValue(-4)
        self.g_xmax = QDoubleSpinBox(); self.g_xmax.setRange(-20, 20); self.g_xmax.setValue(5)
        self.g_asym_x = QLineEdit("1"); self.g_asym_y = QLineEdit("1"); self.g_shade = QLineEdit("2, 4")
        f1.addRow("Biểu thức TikZ (dùng \\x):", self.g_expr)
        f1.addRow("x min / x max:", self._pair(self.g_xmin, self.g_xmax))
        f1.addRow("Tiệm cận đứng x =:", self.g_asym_x)
        f1.addRow("Tiệm cận ngang/xiên y =:", self.g_asym_y)
        f1.addRow("Tô miền tích phân [a, b]:", self.g_shade)
        self.stack.addWidget(w1)

        w2 = QWidget(); f2 = QFormLayout(w2)
        self.b_x = QLineEdit(r"$-\infty$, $0$, $2$, $+\infty$")
        self.b_yp = QLineEdit(r", +, 0, -, 0, +, ")
        self.b_y = QLineEdit(r"-/$-\infty$, +/$4$, -/$0$, +/$+\infty$")
        f2.addRow("Dòng x:", self.b_x); f2.addRow("Dòng y' (tkzTabLine):", self.b_yp); f2.addRow("Dòng y (tkzTabVar):", self.b_y)
        self.stack.addWidget(w2)

        w3 = QWidget(); f3 = QFormLayout(w3)
        self.n_iv = QLineEdit("-2, 3"); self.n_ineq = QLineEdit("1,1,2,<=; 1,0,0,>=")
        f3.addRow("Khoảng trục số [a, b):", self.n_iv); f3.addRow("Hệ BPT (a,b,c,op cách ';'):", self.n_ineq)
        self.stack.addWidget(w3)

        w4 = QWidget(); f4 = QFormLayout(w4)
        self.s_type = QComboBox(); self.s_type.addItems(["pyramid_sabcd_perp", "pyramid_sabc_perp", "prism_triangular"])
        self.s_h = QDoubleSpinBox(); self.s_h.setRange(1, 10); self.s_h.setValue(3.5)
        self.s_w = QDoubleSpinBox(); self.s_w.setRange(1, 10); self.s_w.setValue(4.2)
        f4.addRow("Loại hình 3D:", self.s_type); f4.addRow("Chiều cao / Cạnh đáy:", self._pair(self.s_h, self.s_w))
        self.stack.addWidget(w4)

        b_gen, b_prev = QPushButton("Sinh mã TikZ"), QPushButton("Biên dịch xem trước hình")
        b_gen.clicked.connect(self._generate); b_prev.clicked.connect(self._preview_tikz)
        left.addWidget(self.cb_tool); left.addWidget(self.stack)
        hb = QHBoxLayout(); hb.addWidget(b_gen); hb.addWidget(b_prev); left.addLayout(hb)
        self.txt_code = QPlainTextEdit(); left.addWidget(self.txt_code, stretch=1)

        self.lbl_img = QLabel("Khung xem trước hình TikZ sau khi biên dịch.")
        self.lbl_img.setAlignment(Qt.AlignCenter); self.lbl_img.setMinimumWidth(420)
        right.addWidget(self.lbl_img, stretch=1)
        lay.addLayout(left, stretch=3); lay.addLayout(right, stretch=2)

    @staticmethod
    def _pair(w1, w2) -> QWidget:
        box = QWidget(); h = QHBoxLayout(box); h.setContentsMargins(0, 0, 0, 0); h.addWidget(w1); h.addWidget(w2)
        return box

    def _generate(self):
        idx = self.cb_tool.currentIndex()
        if idx == 0:
            ax = float(self.g_asym_x.text()) if self.g_asym_x.text().strip() else None
            ay = self.g_asym_y.text().strip() or None
            sh = tuple(float(x.strip()) for x in self.g_shade.text().split(",", 1)) if "," in self.g_shade.text() else None
            code = generate_function_graph_tikz(self.g_expr.text(), xmin=self.g_xmin.value(), xmax=self.g_xmax.value(), asymptote_x=ax, asymptote_y_expr=ay, shade_integral=sh)
        elif idx == 1:
            code = generate_variation_table_tikz([x.strip() for x in self.b_x.text().split(",")], [x.strip() for x in self.b_yp.text().split(",")], [x.strip() for x in self.b_y.text().split(",")])
        elif idx == 2:
            a, b = [float(x.strip()) for x in self.n_iv.text().split(",", 1)]
            ineqs = [(float(p[0]), float(p[1]), float(p[2]), p[3].strip()) for s in self.n_ineq.text().split(";") if s.strip() for p in [s.split(",")]]
            code = generate_number_line_tikz([IntervalSpec(a, b, True, False)]) + "\n\n" + generate_linear_inequality_region_tikz(ineqs)
        else:
            code = generate_solid_geometry_tikz(self.s_type.currentText(), height=self.s_h.value(), base_w=self.s_w.value())
        self.txt_code.setPlainText(code)

    def _preview_tikz(self):
        code = self.txt_code.toPlainText().strip()
        if not code:
            self._generate(); code = self.txt_code.toPlainText().strip()
        tmp_dir = Path(tempfile.mkdtemp(prefix="tikz_prev_"))
        tex_f = tmp_dir / "fig.tex"
        tex_f.write_text(r"\documentclass[border=4pt]{standalone}\usepackage{amsmath,amssymb,tikz,tkz-tab}\usetikzlibrary{calc,patterns}\begin{document}" + "\n" + code + "\n\\end{document}\n", encoding="utf-8")
        self.lbl_img.setText("Đang biên dịch hình TikZ...")

        def _done(res):
            if res.success and res.pdf_path:
                qimg, _ = make_qimage_from_pdf_page(res.pdf_path, 0, 2.0)
                self.lbl_img.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl_img.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.lbl_img.setText("Lỗi biên dịch TikZ:\n" + "\n".join(d.summary for d in res.diagnostics))

        run_in_background(compile_tex_to_pdf, str(tex_f), on_finished=_done, on_error=lambda e: self.lbl_img.setText(e))


class AIStationTab(QWidget):
    def __init__(self, db: QuestionBankDB, get_ai_config_fn, parent=None):
        super().__init__(parent)
        self.db = db
        self.get_ai_config = get_ai_config_fn
        self._last_generated: Question | None = None

        lay = QVBoxLayout(self)
        g_in = QGroupBox("Dán mã nguồn 1 câu hỏi ex_test (hoặc bài làm tự luận học sinh)")
        v_in = QVBoxLayout(g_in)
        self.txt_in = QPlainTextEdit()
        self.txt_in.setPlaceholderText(r"\begin{ex} ... \choice{...}{...}{...}{...} \loigiai{...} \end{ex}")
        v_in.addWidget(self.txt_in)
        lay.addWidget(g_in, stretch=1)

        hb = QHBoxLayout()
        for lbl, fn in [
            ("AI Gán mã ID6 (6–12)", self._auto_id),
            ("AI Sinh câu tương tự", self._gen_similar),
            ("Lưu câu mới vào Kho", self._save_generated),
            ("AI Chấm bài tự luận", self._grade_essay),
        ]:
            b = QPushButton(lbl); b.clicked.connect(fn); hb.addWidget(b)
        lay.addLayout(hb)

        self.txt_out = QPlainTextEdit()
        lay.addWidget(self.txt_out, stretch=1)

    def _auto_id(self):
        src = self.txt_in.toPlainText().strip()
        if not src:
            return
        client = AIProviderClient(self.get_ai_config())
        self.txt_out.setPlainText("Đang gọi AI gán mã ID6...")
        run_in_background(
            client.generate_structured, f"Hãy xác định mã ID6 Toán GDPT 2018 (VD: 1D2H2-1) cho câu hỏi:\n{src}", _IDProposal,
            on_finished=lambda r: self.txt_out.setPlainText(f"Mã đề xuất: %[{r.parsed.primary_id}]\nĐộ tin cậy: {r.parsed.confidence:.0%}\nLý do: {r.parsed.reason}" if r.parsed else r.text),
            on_error=lambda e: self.txt_out.setPlainText(e),
        )

    def _gen_similar(self):
        src = self.txt_in.toPlainText().strip()
        if not src:
            return
        client = AIProviderClient(self.get_ai_config())
        prompt = "Hãy sáng tác 1 câu hỏi Toán tương tự (đổi số liệu, dùng \\dfrac, \\overrightarrow, \\Leftrightarrow) từ câu gốc:\n" + src
        self.txt_out.setPlainText("Đang gọi AI sinh câu tương tự...")

        def _done(res):
            if res.parsed:
                p: _SimilarQuestion = res.parsed
                q = Question(p.qtype, p.stem, p.choices, p.correct, p.short_ans, p.solution, [p.suggested_id] if p.suggested_id else [])
                self._last_generated = q
                self.txt_out.setPlainText(q.to_latex(True))
            else:
                self.txt_out.setPlainText(res.text)

        run_in_background(client.generate_structured, prompt, _SimilarQuestion, on_finished=_done, on_error=lambda e: self.txt_out.setPlainText(e))

    def _save_generated(self):
        if not self._last_generated:
            QMessageBox.information(self, "Lưu kho", "Chưa có câu tương tự nào vừa sinh.")
            return
        _, ok = self.db.add_question(self._last_generated)
        QMessageBox.information(self, "Lưu kho", "Đã lưu câu mới vào kho!" if ok else "Câu hỏi bị trùng lặp với kho hiện có.")

    def _grade_essay(self):
        src = self.txt_in.toPlainText().strip()
        if not src:
            return
        self.txt_out.setPlainText("Đang gọi AI chấm bài tự luận...")
        run_in_background(
            grade_essay_with_ai, "Đề tự luận trong nội dung dưới đây", "Chấm theo các bước chuẩn xác", src, 3.0, self.get_ai_config(),
            on_finished=lambda rep: self.txt_out.setPlainText(f"Điểm đề xuất: {rep.suggested_score}/{rep.max_score}\n\nNhận xét từng bước:\n- " + "\n- ".join(rep.step_feedback) + f"\n\nTổng kết: {rep.summary_comment}"),
            on_error=lambda e: self.txt_out.setPlainText(e),
        )
