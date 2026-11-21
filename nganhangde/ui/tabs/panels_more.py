"""Các tab bổ sung: Ma trận, Tiện ích xuất & chuyển đổi, Soạn thảo, Thông tin."""
from __future__ import annotations

import os
import tempfile
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QFileDialog, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
    QTextBrowser, QVBoxLayout, QWidget)

from ..common import latex_editor

if TYPE_CHECKING:
    from ..main_window import MainWindow


def _open(path):
    QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(path)))


# ====================================================================== Ma trận
class MatrixPanel(QWidget):
    """Xem ma trận hiện tại (của tab Trộn đề → Theo ma trận) dưới dạng bảng CV 7991, kiểm tra kho, xuất file."""

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Ma trận lấy từ bảng <b>Trộn đề → Theo ma trận</b> (sửa dòng ở đó). Bảng dưới trình bày theo "
                             "Công văn 7991: hàng là chủ đề (chương), cột là dạng câu × cấp độ tư duy."))
        row = QHBoxLayout()
        gp = win.gen_panel
        for text, fn in (("🔄 Làm mới", self.reload), ("Mở ma trận (.json/.xlsx)…", lambda: (gp.load_matrix(), self.reload())),
                         ("Lưu ma trận…", gp.save_matrix), ("Ma trận từ đề có sẵn…", lambda: (gp.matrix_from_exam(), self.reload())),
                         ("Xuất ma trận CV 7991…", gp.export_cv7991), ("In ma trận đặc tả…", gp.print_matrix),
                         ("🤖 Bù câu thiếu bằng AI…", lambda: win.ai_assistant(1))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        self.t = QTableWidget()
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        lay.addWidget(self.t, 2)
        self.info = QTextBrowser()
        lay.addWidget(self.info, 1)

    def reload(self):
        from ... import aitasks, matrix
        from ...generator import Rule
        rules = [Rule.from_dict(r) for r in self.win.gen_panel.rules_dicts()]
        sc = self.win.gen_panel.export_options().scoring_obj()
        rows, total, points = matrix.build_table(rules, self.win.bank.idmap(), sc)
        heads = [f"{pn}\n{ln}" for _, pn in matrix.PARTS for _, ln in matrix.LEVELS]
        self.t.setColumnCount(len(heads) + 2)
        self.t.setHorizontalHeaderLabels(["Chủ đề"] + heads + ["Tổng"])
        self.t.setRowCount(len(rows) + 1)
        for r, (name, cells) in enumerate(rows + [("TỔNG", total)]):
            self.t.setItem(r, 0, QTableWidgetItem(name))
            c = 1
            for p, _ in matrix.PARTS:
                for lv, _ in matrix.LEVELS:
                    n = cells.get((p, lv))
                    it = QTableWidgetItem(str(n) if n else "")
                    it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.t.setItem(r, c, it)
                    c += 1
            self.t.setItem(r, c, QTableWidgetItem(str(sum(cells.values()))))
        self.t.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        unknown = sum(n for (_, lv), n in total.items() if lv == "?")
        gaps = aitasks.gaps(self.win.bank, rules)
        html = ("<p><b>Điểm:</b> " + " · ".join(f"{n}: {points[p]:g}" for p, n in matrix.PARTS if points[p]) +
                f" · <b>Tổng {sum(points.values()):g} điểm</b></p>")
        if unknown:
            html += f"<p style='color:#b36b00'>{unknown} câu chưa rõ cấp độ (mẫu ID không có mức độ, cột Mức độ trống).</p>"
        html += ("<p style='color:#0b7a0b'>Kho đủ câu cho mọi dòng ma trận.</p>" if not gaps else
                 "<p style='color:#c00000'><b>Kho còn thiếu:</b> " + "; ".join(
                     f"dòng {i + 1} ({rules[i].qtype} {rules[i].id}) thiếu {n}" for i, n in gaps) + "</p>")
        self.info.setHtml(html)

    def showEvent(self, e):
        super().showEvent(e)
        self.reload()


# ====================================================================== Tiện ích: xuất & chuyển đổi
class ConvertPanel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        g = QGroupBox("Nguồn câu hỏi")
        f = QFormLayout(g)
        self.e_files = QLineEdit()
        self.e_files.setPlaceholderText("một hoặc nhiều file .tex (để trống = các câu đang chọn ở tab Câu hỏi)")
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(self._pick)
        r = QHBoxLayout()
        r.addWidget(self.e_files)
        r.addWidget(b)
        f.addRow("File", r)
        lay.addWidget(g)
        grid = QGridLayout()
        items = [
            ("Đề online", [("⚙ Màu & Google Form nhận kết quả…", self.online_settings), ("Moodle XML", self.moodle), ("Aiken (Moodle/LMS)", self.aiken), ("Quizizz (Excel)", self.quizizz),
                           ("Microsoft Forms (Word)", self.msforms), ("Google Forms (Apps Script)", self.gforms),
                           ("Google Forms dạng ảnh", self.gforms_img),
                           ("Blogger (HTML)", self.blogger), ("Bài làm online (HTML)", self.online)]),
            ("Phiếu trả lời", [("Phiếu trắng (in)", self.sheet_blank), ("Phiếu tô sẵn theo đề .tex", self.sheet_from_file),
                               ("Phiếu tô theo chuỗi đáp án", self.sheet_from_string)]),
            ("Hình vẽ", [("Hoá ảnh hình TikZ (PNG)", self.tikz_png), ("Trích hình TikZ ra file", self.tikz_files)]),
            ("Chuyển đổi", [("Đề LaTeX thường → ex_test", self.plain_ex), ("Word → LaTeX", self.word_tex),
                            ("LaTeX → Word", self.tex_word), ("Trình chiếu HTML", self.slides)]),
        ]
        for col, (title, btns) in enumerate(items):
            gb = QGroupBox(title)
            v = QVBoxLayout(gb)
            for text, fn in btns:
                bb = QPushButton(text)
                bb.clicked.connect(fn)
                v.addWidget(bb)
            v.addStretch()
            grid.addWidget(gb, 0, col)
        lay.addLayout(grid)
        row = QHBoxLayout()
        row.addWidget(QLabel("Chuỗi đáp án (tô phiếu):"))
        self.e_key = QLineEdit()
        self.e_key.setPlaceholderText("vd 0101|I:ABCDA…|II:1010,0011|III:0,5;12  (như nội dung mã QR đáp án)")
        row.addWidget(self.e_key, 1)
        row.addWidget(QLabel("Phiếu trắng: TN/ĐS/TLN"))
        self.sp = []
        for v_ in (40, 8, 6):
            s = QSpinBox()
            s.setRange(0, 60)
            s.setValue(v_)
            self.sp.append(s)
            row.addWidget(s)
        lay.addLayout(row)
        self.out = QTextBrowser()
        lay.addWidget(self.out, 1)

    def _pick(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file", "", "LaTeX (*.tex);;Word/PDF (*.docx *.pdf)")
        if ps:
            self.e_files.setText("; ".join(ps))

    def paths(self):
        return [p.strip() for p in self.e_files.text().split(";") if p.strip()]

    def questions(self):
        from ...parser import parse_file
        ps = [p for p in self.paths() if p.lower().endswith(".tex")]
        if ps:
            return [q for p in ps for q in parse_file(p)]
        return [q for q in (self.win.bank.get(i) for i in self.win.selected_ids()) if q is not None]

    def _need(self):
        qs = self.questions()
        if not qs:
            QMessageBox.information(self, "Tiện ích", "Chọn file .tex hoặc chọn câu ở tab Câu hỏi.")
        return qs

    def _save(self, title, name, filt):
        base = os.path.dirname(self.paths()[0]) if self.paths() else ""
        p, _ = QFileDialog.getSaveFileName(self, title, os.path.join(base, name), filt)
        return p

    def _done(self, msg, path=None):
        self.out.append(msg)
        if path:
            _open(path)

    def _version(self, qs):
        from ...generator import ExamVersion, sections_from_questions
        v = ExamVersion("101")
        v.sections = sections_from_questions(qs)
        return v

    # --- đề online
    def online_settings(self):
        from ..dialogs.online_settings import OnlineSettingsDialog
        OnlineSettingsDialog(self.win).exec()

    def moodle(self):
        from ...online import export_moodle
        qs = self._need()
        p = qs and self._save("Moodle XML", "moodle.xml", "XML (*.xml)")
        if p:
            base = os.path.dirname(self.paths()[0]) if self.paths() else None
            self._done(f"Moodle: {len(qs)} câu → {export_moodle(qs, p, base_dir=base)}")

    def aiken(self):
        from ...exportx import aiken
        qs = self._need()
        p = qs and self._save("Aiken", "aiken.txt", "Văn bản (*.txt)")
        if p:
            text, skip = aiken(qs)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(text)
            self._done(f"Aiken: {len(qs) - skip} câu trắc nghiệm → {p}" + (f" (bỏ {skip} câu không phải TN)" if skip else ""))

    def quizizz(self):
        from ...exportx import quizizz_xlsx
        qs = self._need()
        p = qs and self._save("Quizizz", "quizizz.xlsx", "Excel (*.xlsx)")
        if p:
            quizizz_xlsx(qs, p)
            self._done(f"Quizizz: {p} – vào Quizizz → Tạo → Nhập từ bảng tính (Spreadsheet).")

    def msforms(self):
        from ...exportx import msforms_docx
        qs = self._need()
        p = qs and self._save("Microsoft Forms", "msforms.docx", "Word (*.docx)")
        if p:
            try:
                msforms_docx(qs, p)
            except Exception as e:  # noqa: BLE001 – thiếu pandoc
                QMessageBox.warning(self, "Microsoft Forms", str(e))
                return
            self._done(f"Microsoft Forms: {p} – vào forms.office.com → Nhập nhanh (Quick import), rồi đánh dấu đáp án.")

    def gforms(self):
        from ...gas import apps_script
        qs = self._need()
        p = qs and self._save("Google Forms", "google_form.gs", "Apps Script (*.gs)")
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(apps_script(self._version(qs), ten_de=self.win.gen_panel.e_ten.text()))
            self._done(f"Google Forms: {p} – dán vào script.google.com, chạy hàm taoDe.", p)

    def gforms_img(self):
        from PySide6.QtWidgets import QApplication
        from ...gas import export_gas_images
        qs = self._need()
        d = qs and QFileDialog.getExistingDirectory(self, "Thư mục lưu ảnh và file .gs")
        if not d:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            fs = export_gas_images([self._version(qs)], d, ten_de=self.win.gen_panel.e_ten.text())
        except (RuntimeError, ImportError) as e:
            QMessageBox.warning(self, "Google Forms dạng ảnh", str(e))
            return
        finally:
            QApplication.restoreOverrideCursor()
        self._done(f"Google Forms dạng ảnh: {fs[0]} – tải thư mục ảnh lên Drive, dán mã thư mục vào FOLDER_ID, chạy taoDe.",
                   os.path.dirname(fs[0]))

    def blogger(self):
        from ...exportx import blogger_html
        qs = self._need()
        p = qs and self._save("Blogger", "blogger.html", "HTML (*.html)")
        if p:
            with open(p, "w", encoding="utf-8") as fh:
                o = self.win.gen_panel.export_options()
                fh.write(blogger_html(self._version(qs), ten_de=self.win.gen_panel.e_ten.text(), style=o.online_style,
                                      gform=o.gform))
            self._done(f"Blogger: {p} – mở file bằng Notepad, chép toàn bộ, dán vào bài viết ở chế độ «Xem HTML».")

    def online(self):
        from ...online import export_html
        qs = self._need()
        if qs:
            d = QFileDialog.getExistingDirectory(self, "Thư mục lưu bài online")
            if d:
                o = self.win.gen_panel.export_options()
                fs = export_html([self._version(qs)], d, ten_de=self.win.gen_panel.e_ten.text(),
                                 style=o.online_style, gform=o.gform)
                self._done(f"Bài online: {fs[0]}", fs[0])

    # --- phiếu
    def _sheet(self, doc, name):
        p = self._save("Phiếu trả lời", name, "LaTeX (*.tex)")
        if not p:
            return
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(doc)
        res = self.win.build_pdfs([p], "Biên dịch phiếu", open_single=True)
        self._done(f"Phiếu: {p}" + (" – đã biên dịch PDF." if res and res[0].ok else ""))

    def sheet_blank(self):
        from ...omr import sheet_document
        self._sheet(sheet_document(None, {"TN": self.sp[0].value(), "DS": self.sp[1].value(),
                                          "KQ": self.sp[2].value()}), "phieu_trang.tex")

    def sheet_from_file(self):
        from ...omr import sheet_document
        qs = self._need()
        if qs:
            self._sheet(sheet_document([self._version(qs)]), "phieu_to_san.tex")

    def sheet_from_string(self):
        from ...omr import sheet_tikz
        s = self.e_key.text().strip()
        if not s:
            QMessageBox.information(self, "Tô phiếu", "Nhập chuỗi đáp án, vd 0101|I:ABCD|II:1010|III:0,5")
            return
        parts = s.split("|")
        code = parts[0] if parts and ":" not in parts[0] else ""
        key = {"TN": [], "DS": [], "KQ": []}
        for p_ in parts:
            if p_.startswith("I:"):
                key["TN"] = [c for c in p_[2:].strip().upper() if c in "ABCD"]
            elif p_.startswith("II:"):
                key["DS"] = [[c == "1" for c in x.strip()] for x in p_[3:].split(",") if x.strip()]
            elif p_.startswith("III:"):
                key["KQ"] = [x.strip() for x in p_[4:].split(";") if x.strip()]
        body = sheet_tikz(max(len(key["TN"]), 1), len(key["DS"]), len(key["KQ"]), code, key,
                          code_digits=max(3, len(code)))
        self._sheet("\\documentclass{article}\n\\usepackage[utf8]{vietnam}\n\\usepackage{tikz}\n"
                    "\\usepackage[a4paper,margin=1cm]{geometry}\n\\pagestyle{empty}\n\\begin{document}\n"
                    "\\noindent\\centering\n" + body + "\n\\end{document}\n", "phieu_theo_chuoi.tex")

    # --- hình
    def tikz_png(self):
        from PySide6.QtWidgets import QApplication
        from ...exportx import tikz_from_files, tikz_to_png
        ps = [p for p in self.paths() if p.lower().endswith(".tex")]
        if not ps:
            QMessageBox.information(self, "Hoá ảnh", "Chọn file .tex chứa hình TikZ.")
            return
        pics = tikz_from_files(ps)
        if not pics:
            self._done("Không có hình TikZ nào.")
            return
        d = QFileDialog.getExistingDirectory(self, "Thư mục lưu ảnh", os.path.dirname(ps[0]))
        if not d:
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            out, res = tikz_to_png(pics, d)
        finally:
            QApplication.restoreOverrideCursor()
        if not res.ok:
            self._done(f"<span style='color:#c00000'>Biên dịch lỗi: {res.summary()}</span>")
        else:
            self._done(f"Đã xuất {len(out)} ảnh PNG vào {d}", d)

    def tikz_files(self):
        from ...tools import extract_tikz
        ps = [p for p in self.paths() if p.lower().endswith(".tex")]
        d = ps and QFileDialog.getExistingDirectory(self, "Thư mục lưu hình", os.path.dirname(ps[0]))
        if d:
            self._done(f"Đã trích {len(extract_tikz(ps, d))} hình vào {d}", d)

    # --- chuyển đổi
    def plain_ex(self):
        from ...exportx import plain_to_ex
        ps = [p for p in self.paths() if p.lower().endswith(".tex")]
        if not ps:
            QMessageBox.information(self, "Chuyển đổi", "Chọn file đề LaTeX dạng thường («Câu 1. … A. … B. …»).")
            return
        for p in ps:
            with open(p, encoding="utf-8", errors="replace") as fh:
                out = plain_to_ex(fh.read())
            q = os.path.splitext(p)[0] + "_ex_test.tex"
            with open(q, "w", encoding="utf-8") as fh:
                fh.write(out)
            self._done(f"{os.path.basename(p)} → {q} ({out.count(chr(92) + 'begin{ex}')} câu)")

    def word_tex(self):
        self.win.tools_panel.word_to_tex()

    def tex_word(self):
        self.win.tools_panel.tex_to_word()

    def slides(self):
        from ...slides import export_slides
        qs = self._need()
        p = qs and self._save("Trình chiếu", "trinh_chieu.html", "HTML (*.html)")
        if p:
            self._done(f"Trình chiếu: {export_slides(qs, p)}", p)


# ====================================================================== Soạn thảo
SNIPPETS = [
    ("Câu TN", "\\begin{ex}%[ID]\n\n\\choice\n{}\n{\\True }\n{}\n{}\n\\loigiai{\n\n}\n\\end{ex}\n"),
    ("Câu Đúng/Sai", "\\begin{ex}%[ID]\n\n\\choiceTF\n{\\True }\n{}\n{\\True }\n{}\n\\loigiai{\n\\begin{itemchoice}\n"
                     "\\itemch Đúng. \n\\itemch Sai. \n\\itemch Đúng. \n\\itemch Sai. \n\\end{itemchoice}\n}\n\\end{ex}\n"),
    ("Câu trả lời ngắn", "\\begin{ex}%[ID]\n\n\\shortans[oly]{}\n\\loigiai{\n\n}\n\\end{ex}\n"),
    ("Câu tự luận", "\\begin{bt}%[ID]\n\n\\loigiai{\n\n}\n\\end{bt}\n"),
    ("$…$", "$$"), ("\\dfrac", "\\dfrac{}{}"), ("\\sqrt", "\\sqrt{}"), ("Hệ", "\\heva{&\\\\&}"),
    ("Hình TikZ", "\\begin{center}\n\\begin{tikzpicture}\n\n\\end{tikzpicture}\n\\end{center}\n"),
]


class EditorPanel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        self.win, self.path = win, ""
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        row2 = QHBoxLayout()
        for text, fn in (("Mới", self.new), ("Mở…", self.open), ("Lưu", self.save), ("Lưu thành…", self.save_as),
                         ("✅ Rà soát", self.review), ("📄 Biên dịch PDF", self.compile), ("Mở TeXstudio", self.texstudio),
                         ("Nạp vào kho", self.to_bank), ("🔢 Câu đổi số tự động", self.autogen),
                         ("🤖 Câu đổi số AI", lambda: self.ai(5)),
                         ("🤖 Lời giải AI", lambda: self.ai(6))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            (row if text in ("Mới", "Mở…", "Lưu", "Lưu thành…", "✅ Rà soát", "📄 Biên dịch PDF", "Mở TeXstudio")
             else row2).addWidget(b)
        row.addStretch()
        self.l_file = QLabel("(chưa lưu)")
        row.addWidget(self.l_file)
        row2.addStretch()
        lay.addLayout(row)
        lay.addLayout(row2)
        row = QHBoxLayout()
        row.addWidget(QLabel("Chèn:"))
        for text, snip in SNIPPETS:
            b = QPushButton(text)
            b.clicked.connect(lambda _=False, s=snip: self.insert(s))
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
        sp = QSplitter(Qt.Orientation.Vertical)
        self.ed = latex_editor()
        sp.addWidget(self.ed)
        self.out = QTextBrowser()
        sp.addWidget(self.out)
        sp.setSizes([600, 150])
        lay.addWidget(sp, 1)

    def insert(self, s):
        self.ed.insertPlainText(s)
        self.ed.setFocus()

    def new(self):
        self.ed.clear()
        self.path = ""
        self.l_file.setText("(chưa lưu)")

    def open(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở file", "", "LaTeX (*.tex)")
        if p:
            with open(p, encoding="utf-8", errors="replace") as fh:
                self.ed.setPlainText(fh.read())
            self.path = p
            self.l_file.setText(p)

    def save(self):
        if not self.path:
            return self.save_as()
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(self.ed.toPlainText())
        self.out.append(f"Đã lưu {self.path}")
        return True

    def save_as(self):
        p, _ = QFileDialog.getSaveFileName(self, "Lưu file", "de_moi.tex", "LaTeX (*.tex)")
        if not p:
            return False
        self.path = p
        self.l_file.setText(p)
        return self.save()

    def review(self):
        from ... import review as rv
        from ...parser import parse_tex
        qs = parse_tex(self.ed.toPlainText())
        base = os.path.dirname(self.path) if self.path else None
        lines = []
        for i, q in enumerate(qs, 1):
            for iss in rv.review_question(q, base):
                color = "#c00000" if iss.level == rv.LOI else "#b36b00"
                lines.append(f"<span style='color:{color}'>Câu {i} [{q.id_code or '—'}] {iss.level}: {iss.msg}</span>")
        self.out.setHtml(f"<p><b>{len(qs)} câu</b> – " + ("không có lỗi." if not lines else f"{len(lines)} vấn đề:</p>"
                                                            + "<br>".join(lines)))

    def compile(self):
        from ..dialogs.pdf import prepare_tex_for_pdf
        if not self.path:
            d = tempfile.mkdtemp(prefix="nhd_soan_")
            p = os.path.join(d, "soan_thao.tex")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(self.ed.toPlainText())
        else:
            self.save()
            p = self.path
        files = prepare_tex_for_pdf([p], self.win.gen_panel.e_tpl[0].text() or None)
        self.win.build_pdfs(files, "Biên dịch file đang soạn", open_single=True)

    def texstudio(self):
        from ...editor import open_in_texstudio
        if self.save() and not open_in_texstudio(self.path, 0, self.win.settings.value("pdf/texstudio", "")):
            _open(self.path)

    def autogen(self):
        """Câu đổi số tự động (không cần AI): chọn dạng, số câu → chèn vào cuối trang soạn thảo."""
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QListWidget, QListWidgetItem
        from ... import autogen
        dlg = QDialog(self)
        dlg.setWindowTitle("Câu đổi số tự động")
        v = QVBoxLayout(dlg)
        v.addWidget(QLabel("Chọn các dạng bài (Toán 12 – hàm số). Mỗi câu có ID, 4 phương án, hình và lời giải; "
                           "số liệu ngẫu nhiên, không trùng nhau."))
        lst = QListWidget()
        for k, (name, _) in autogen.PROBLEMS.items():
            it = QListWidgetItem(name)
            it.setData(Qt.ItemDataRole.UserRole, k)
            it.setCheckState(Qt.CheckState.Unchecked)
            lst.addItem(it)
        v.addWidget(lst)
        row = QHBoxLayout()
        row.addWidget(QLabel("Số câu mỗi dạng"))
        sp = QSpinBox()
        sp.setRange(1, 50)
        sp.setValue(5)
        row.addWidget(sp)
        row.addStretch()
        v.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        v.addWidget(bb)
        self._autogen_dlg = (dlg, lst, sp)
        if not dlg.exec():
            return
        self._autogen_apply(lst, sp.value())

    def _autogen_apply(self, lst, n):
        from ... import autogen
        kinds = [lst.item(i).data(Qt.ItemDataRole.UserRole) for i in range(lst.count())
                 if lst.item(i).checkState() == Qt.CheckState.Checked]
        blocks = [b for k in kinds for b in autogen.generate(k, n)]
        if blocks:
            self.ed.appendPlainText("\n" + "\n\n".join(blocks) + "\n")
        self.out.append(f"Đã thêm {len(blocks)} câu đổi số tự động ({len(kinds)} dạng). Bấm «Rà soát» hoặc "
                        "«Biên dịch PDF» để xem, «Nạp vào kho» để lưu.")

    def ai(self, tab):
        """Mở Trợ lý AI với các câu trong trang soạn thảo (hoặc trong đoạn đang bôi đen)."""
        from ...parser import parse_tex
        from ..dialogs.ai_assistant import AiAssistantDialog
        sel = self.ed.textCursor().selectedText().replace("\u2029", "\n")
        qs = parse_tex(sel) if sel.strip() else []
        qs = qs or parse_tex(self.ed.toPlainText())
        if not qs:
            QMessageBox.information(self, "Trợ lý AI", "Trang soạn thảo chưa có câu hỏi nào (\\begin{ex}…\\end{ex}).")
            return
        AiAssistantDialog(self.win, tab, questions=qs, editor=self).exec()

    def to_bank(self):
        from ...parser import parse_tex
        qs = parse_tex(self.ed.toPlainText())
        n = sum(1 for q in qs if self.win.bank.add(q, self.path))
        self.win.build_tree()
        self.win.refresh()
        self.out.append(f"Đã nạp {n}/{len(qs)} câu vào kho (câu trùng bỏ qua).")


# ====================================================================== Thông tin
class InfoPanel(QWidget):
    def __init__(self, win: MainWindow):
        super().__init__()
        from ... import __version__
        self.win = win
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setOpenExternalLinks(True)
        tb.setHtml(f"""<h2>Ngân hàng đề thi – phiên bản {__version__}</h2>
<p>Quản lí ngân hàng câu hỏi LaTeX (ex_test), trộn đề theo ma trận và chuẩn đề thi tốt nghiệp THPT 2026, rà soát đáp án –
lời giải, phiếu chấm, đề online, phòng thi LAN, trợ lý AI, vẽ hình TikZ.</p>
<table cellpadding=4>
<tr><td><b>Trộn đề</b></td><td>theo ma trận ID · tự chọn câu · theo file (trộn theo vùng) · đề tương tự đề mẫu</td></tr>
<tr><td><b>Câu hỏi</b></td><td>lọc theo lớp – môn – chương – bài – dạng – mức độ, tìm không dấu, gán ID, AI ID, sửa, xem PDF</td></tr>
<tr><td><b>Ma trận</b></td><td>bảng CV 7991, kiểm tra kho, xuất Excel/Word, bù câu thiếu bằng AI</td></tr>
<tr><td><b>Tiện ích</b></td><td>công cụ file, rà soát, Moodle/Aiken/Quizizz/MS Forms/Google Forms/Blogger, phiếu trả lời,
hoá ảnh TikZ, chuyển đổi Word/LaTeX, sinh câu, thống kê</td></tr>
<tr><td><b>Vẽ hình · Đồ thị · BBT&amp;XD · Biểu diễn nghiệm</b></td><td>dựng hình theo bước, hình khối, đồ thị (tiệm cận, tô miền,
theo cực trị), bảng biến thiên, bảng xét dấu, trục số, miền nghiệm, đường tròn lượng giác</td></tr>
<tr><td><b>Soạn thảo</b></td><td>soạn câu ex_test có mẫu chèn nhanh, rà soát, biên dịch PDF</td></tr>
</table>
<p>Thư mục phần mềm: <code>{__import__('nganhangde.appdirs', fromlist=['home']).home()}</code>
(config.ini, du_lieu, mau_de, map_id, de_xuat, sao_luu, anh, online, tam – xem DOC_TOI.txt)<br>
Kho câu hỏi: <code>{getattr(win.bank, 'path', '')}</code></p>
<p>Mã nguồn và bản cập nhật: <a href="https://github.com/HuynhDucVu/toan11/releases">github.com/HuynhDucVu/toan11</a></p>""")
        lay.addWidget(tb, 1)
        row = QHBoxLayout()
        for text, fn in (("Kiểm tra cập nhật…", lambda: win.check_update()),
                         ("Mở thư mục phần mềm", win.open_app_folder),
                         ("Hướng dẫn trên GitHub", lambda: QDesktopServices.openUrl(
                             QUrl("https://github.com/HuynhDucVu/toan11#readme")))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)
