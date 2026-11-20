"""Tab «Công cụ»: thao tác trực tiếp trên file .tex."""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QFileDialog, QFormLayout, QGridLayout,
    QGroupBox, QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton,
    QTextBrowser, QVBoxLayout, QWidget)
from ... import tools
from ...parser import parse_file, parse_tex, validate
from ..common import TEN_LOAI, TEN_MUC, scroll_of
from ..dialogs.assign_id import AssignIdDialog
from ..dialogs.pdf import prepare_tex_for_pdf
from ..dialogs.result import versions_report_html
from ..tabs.exam_options import ExamOptionsBox

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ToolsPanel(QWidget):
    """Tab «Công cụ»: xử lí trực tiếp các file .tex (không cần nạp vào kho)."""

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        body = QHBoxLayout(self)
        left = QVBoxLayout()
        body.addWidget(scroll_of(left), 2)

        g = QGroupBox("File .tex nguồn")
        gl = QVBoxLayout(g)
        self.files = QListWidget()
        self.files.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        gl.addWidget(self.files)
        row = QHBoxLayout()
        for text, fn in (("Thêm file…", self.add_files), ("Bỏ file chọn", self.remove_files),
                         ("Xoá danh sách", self.files.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        gl.addLayout(row)
        left.addWidget(g, 2)

        g = QGroupBox("Kiểm tra")
        gl = QHBoxLayout(g)
        for text, fn in (("Soát lỗi soạn thảo", self.check_files), ("Tìm câu trùng", self.find_dups),
                         ("Thống kê theo ID", self.count_ids)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            gl.addWidget(b)
        self.c_vs_bank = QCheckBox("so cả với kho")
        self.c_vs_bank.setChecked(True)
        gl.addWidget(self.c_vs_bank)
        left.addWidget(g)

        g = QGroupBox("Lọc câu theo ID ra file mới")
        fl = QFormLayout(g)
        self.e_loc = QLineEdit("0D2*")
        self.cb_loc = QComboBox()
        self.cb_loc.addItem("Mọi loại câu", "")
        for k, v in TEN_LOAI.items():
            self.cb_loc.addItem(v, k)
        b = QPushButton("Lọc và lưu…")
        b.setObjectName("primary")
        b.clicked.connect(self.filter_ids)
        fl.addRow("Mẫu ID", self.e_loc)
        fl.addRow("Loại câu", self.cb_loc)
        fl.addRow("", b)
        left.addWidget(g)

        g = QGroupBox("Đổi ID hàng loạt")
        fl = QFormLayout(g)
        self.e_map = QPlainTextEdit()
        self.e_map.setPlaceholderText("Mỗi dòng: tiền tố cũ = tiền tố mới\nvd:\n0H9 = 0H4\n0D2 = 0D5")
        self.e_map.setFixedHeight(80)
        b = QPushButton("Đổi ID và lưu…")
        b.clicked.connect(self.convert_ids)
        fl.addRow("Bảng đổi", self.e_map)
        fl.addRow("", b)
        left.addWidget(g)

        g = QGroupBox("Trộn đề trực tiếp từ file (không cần kho)")
        fl = QFormLayout(g)
        self.e_codes = QLineEdit("101, 102, 103, 104")
        self.tool_opts = ExamOptionsBox(win.settings, "tool", show_codes=False)
        self.tool_opts.setMinimumHeight(190)
        b = QPushButton("Trộn file đầu tiên trong danh sách…")
        b.setObjectName("primary")
        b.clicked.connect(self.shuffle_file)
        fl.addRow("Mã đề", self.e_codes)
        fl.addRow(self.tool_opts)
        fl.addRow("", b)
        left.addWidget(g)

        g = QGroupBox("Khác")
        gl = QGridLayout(g)
        for k, (text, fn) in enumerate((("Lấy bảng đáp án", self.get_answers), ("Thêm nguồn cho mọi câu…", self.add_tag),
                                        ("Gộp và sắp xếp theo ID…", self.sort_ids), ("Xoá lời giải…", self.erase_solutions),
                                        ("🏷 Gán ID cho file…", self.assign_ids_file),
                                        ("Tìm và thay thế…", self.file_replace), ("Xoá ID khỏi file…", self.file_remove_ids),
                                        ("Xoá một nguồn…", self.file_remove_tag), ("Lọc câu theo nguồn…", self.file_filter_tag),
                                        ("Trích hình TikZ…", self.file_tikz), ("Tìm câu gần trùng…", self.file_near_dups),
                                        ("Word → LaTeX…", self.word_to_tex), ("LaTeX → Word…", self.tex_to_word),
                                        ("Bài làm online từ file…", self.file_online),
                                        ("📄 Biên dịch PDF các file", self.file_pdf),
                                        ("Mở file trong TeXstudio", self.file_texstudio),
                                        ("Nạp các file vào kho", self.import_to_bank))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            gl.addWidget(b, k // 3, k % 3)
        left.addWidget(g)

        g = QGroupBox("Kết quả")
        gl = QVBoxLayout(g)
        self.out = QTextBrowser()
        gl.addWidget(self.out)
        body.addWidget(g, 3)

    # --- tiện ích
    def paths(self) -> list[str]:
        ps = [self.files.item(i).text() for i in range(self.files.count())]
        if not ps:
            self.add_files()
            ps = [self.files.item(i).text() for i in range(self.files.count())]
        return ps

    def add_files(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex", self.win.settings.value("last_dir", ""),
                                             "LaTeX (*.tex);;Tất cả (*.*)")
        if ps:
            self.win.settings.setValue("last_dir", os.path.dirname(ps[0]))
        have = {self.files.item(i).text() for i in range(self.files.count())}
        for p in ps:
            if p not in have:
                self.files.addItem(p)

    def remove_files(self):
        for it in self.files.selectedItems():
            self.files.takeItem(self.files.row(it))

    def show_result(self, title, html):
        self.out.setHtml(f"<h3>{title}</h3>{html}")

    def _save_path(self, default):
        base = os.path.dirname(self.files.item(0).text()) if self.files.count() else ""
        p, _ = QFileDialog.getSaveFileName(self, "Lưu thành", os.path.join(base, default), "LaTeX (*.tex)")
        return p

    # --- công cụ
    def check_file(self):
        """Gọi từ menu: chọn file rồi soát lỗi ngay."""
        self.add_files()
        if self.files.count():
            self.check_files()

    def check_files(self):
        rows = []
        for p in self.paths():
            for i, q in enumerate(parse_file(p), 1):
                ws = validate(q)
                if self.c_vs_bank.isChecked() and self.win.bank:
                    dup = self.win.bank.find_duplicate(q)
                    if dup:
                        ws.append(f"Trùng câu #{dup} trong kho")
                color = "#c00000" if ws else "#0b7a0b"
                rows.append(f"<tr><td>{os.path.basename(p)}</td><td>{i}</td><td>{q.qtype}</td><td>{q.id_code}</td>"
                            f"<td>{q.answer_text}</td><td style='color:{color}'>{'<br>'.join(ws) or '✔'}</td></tr>")
        self.show_result("Soát lỗi soạn thảo", "<table border=1 cellspacing=0 cellpadding=3><tr><th>File</th><th>Câu</th>"
                  "<th>Loại</th><th>ID</th><th>Đáp án</th><th>Kết quả</th></tr>" + "".join(rows) + "</table>")

    def find_dups(self):
        ps = self.paths()
        groups = tools.find_duplicates(ps)
        html = [f"<p>Tìm thấy <b>{len(groups)}</b> nhóm câu trùng giữa các file.</p>"]
        for k, g in enumerate(groups, 1):
            html.append(f"<p><b>Nhóm {k}:</b> " + "; ".join(
                f"{os.path.basename(f)} – câu {i} [{c}]" for f, i, c in g) + "</p>")
        if self.c_vs_bank.isChecked() and self.win.bank:
            hits = []
            for p in ps:
                for i, q in enumerate(parse_file(p), 1):
                    dup = self.win.bank.find_duplicate(q)
                    if dup:
                        hits.append(f"{os.path.basename(p)} – câu {i} [{q.id_code}] ≡ câu #{dup} trong kho")
            html.append(f"<p>Trùng với kho: <b>{len(hits)}</b> câu</p>" + "<br>".join(hits))
        self.show_result("Tìm câu trùng", "".join(html))

    def count_ids(self):
        by_type, by_ch = tools.count_by_id(self.paths())
        t1 = "".join(f"<tr><td>{TEN_LOAI.get(t, t)}</td><td>{TEN_MUC.get(m, m)}</td><td>{n}</td></tr>"
                     for (t, m), n in sorted(by_type.items()))
        t2 = "".join(f"<tr><td>{c}</td><td>{n}</td></tr>" for c, n in sorted(by_ch.items()))
        self.show_result("Thống kê theo ID",
                  f"<p>Tổng: <b>{sum(by_type.values())}</b> câu</p>"
                  "<table border=1 cellspacing=0 cellpadding=3><tr><th>Loại</th><th>Mức độ</th><th>Số câu</th></tr>"
                  + t1 + "</table><br><table border=1 cellspacing=0 cellpadding=3><tr><th>Lớp-Môn-Chương</th>"
                  "<th>Số câu</th></tr>" + t2 + "</table>")

    def filter_ids(self):
        ps = self.paths()
        if not ps:
            return
        out = self._save_path("loc_id.tex")
        if out:
            n = tools.filter_by_id(ps, self.e_loc.text(), out, self.cb_loc.currentData() or None)
            self.show_result("Lọc câu theo ID", f"<p>Đã lọc <b>{n}</b> câu có ID <code>{self.e_loc.text()}</code> ra<br>{out}</p>")

    def convert_ids(self):
        mapping = tools.parse_mapping(self.e_map.toPlainText())
        if not mapping:
            QMessageBox.warning(self, "Đổi ID", "Chưa nhập bảng đổi (mỗi dòng: cũ = mới).")
            return
        html = []
        for p in self.paths():
            out = self._save_path(os.path.splitext(os.path.basename(p))[0] + "_doiID.tex")
            if out:
                n = tools.convert_ids(p, out, mapping)
                html.append(f"<p>{os.path.basename(p)}: đổi <b>{n}</b> ID → {out}</p>")
        self.show_result("Đổi ID", "".join(html))

    def erase_solutions(self):
        html = []
        for p in self.paths():
            out = self._save_path(os.path.splitext(os.path.basename(p))[0] + "_khongLG.tex")
            if out:
                n = tools.erase_solutions(p, out)
                html.append(f"<p>{os.path.basename(p)}: xoá <b>{n}</b> lời giải → {out}</p>")
        self.show_result("Xoá lời giải", "".join(html))

    def shuffle_file(self):
        ps = self.paths()
        if not ps:
            return
        codes = [c for c in re.split(r"[,;\s]+", self.e_codes.text()) if c]
        if not codes:
            QMessageBox.warning(self, "Trộn đề", "Nhập danh sách mã đề, vd: 101, 102, 103, 104")
            return
        out = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu đề đã trộn", os.path.dirname(ps[0]))
        if not out:
            return
        gp = self.win.gen_panel
        vs, _files = tools.shuffle_file(ps[0], codes, out, options=self.tool_opts.mix_options(),
                                        export_options=self.tool_opts.export_options(),
                                        template_path=gp.e_tpl[0].text() or None, ten_de=gp.e_ten.text(),
                                        truong=gp.e_truong.text(), thoi_gian=gp.e_tg.value())
        self.tool_opts.save()
        self.show_result("Trộn đề từ file", f"<p>File: {os.path.basename(ps[0])}</p>" + versions_report_html(vs, out))

    def _rewrite_files(self, suffix, fn, title):
        """Áp fn(text) -> (text_mới, số_thay) cho từng file, lưu thành file mới."""
        html = []
        for p in self.paths():
            out = self._save_path(os.path.splitext(os.path.basename(p))[0] + suffix + ".tex")
            if not out:
                continue
            with open(p, encoding="utf-8") as f:
                text, n = fn(f.read())
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            html.append(f"<p>{os.path.basename(p)}: <b>{n}</b> chỗ → {out}</p>")
        self.show_result(title, "".join(html))

    def file_replace(self):
        find, ok = QInputDialog.getText(self, "Tìm và thay thế", "Tìm (trong các câu hỏi):")
        if not ok or not find:
            return
        repl, ok = QInputDialog.getText(self, "Tìm và thay thế", f"Thay «{find}» bằng:")
        if ok:
            self._rewrite_files("_thaythe", lambda t: tools.replace_text(t, find, repl), "Tìm và thay thế")

    def file_remove_ids(self):
        self._rewrite_files("_khongID", tools.remove_ids_text, "Xoá ID")

    def file_remove_tag(self):
        tag, ok = QInputDialog.getText(self, "Xoá nguồn", "Nhãn cần xoá (đúng như trong %[...]):")
        if ok and tag.strip():
            self._rewrite_files("_boNguon", lambda t: tools.remove_tag_text(t, tag.strip()), "Xoá nguồn")

    def file_filter_tag(self):
        tag, ok = QInputDialog.getText(self, "Lọc theo nguồn", "Lấy các câu có nhãn chứa:")
        if not ok or not tag.strip():
            return
        ps = self.paths()
        out = self._save_path("loc_nguon.tex") if ps else ""
        if out:
            n = tools.filter_by_tag(ps, tag.strip(), out)
            self.show_result("Lọc theo nguồn", f"<p>Lấy được <b>{n}</b> câu có nguồn chứa «{tag}» → {out}</p>")

    def file_tikz(self):
        ps = self.paths()
        out = QFileDialog.getExistingDirectory(self, "Thư mục lưu hình TikZ", os.path.dirname(ps[0])) if ps else ""
        if out:
            fs = tools.extract_tikz(ps, out)
            self.show_result("Trích hình TikZ", f"<p>Đã trích <b>{len(fs)}</b> hình (mỗi hình một file standalone) "
                             f"vào {out}</p>" + "<br>".join(os.path.basename(f) for f in fs[:50]))

    def file_near_dups(self):
        thr, ok = QInputDialog.getInt(self, "Câu gần trùng", "Độ giống tối thiểu (%)", 80, 30, 100)
        if not ok:
            return
        items = [(p, i, q) for p in self.paths() for i, q in enumerate(parse_file(p), 1)]
        pairs = tools.near_duplicates([q for _, _, q in items], thr / 100)
        rows = "".join(f"<tr><td>{sc:.0%}</td><td>{os.path.basename(items[i][0])} – câu {items[i][1]}</td>"
                       f"<td>{os.path.basename(items[j][0])} – câu {items[j][1]}</td>"
                       f"<td>{' '.join(items[i][2].stem.split())[:90]}</td></tr>" for i, j, sc in pairs)
        self.show_result(f"Câu gần trùng (≥ {thr}%)", f"<p><b>{len(pairs)}</b> cặp.</p><table border=1 cellspacing=0 "
                         "cellpadding=3><tr><th>Giống</th><th>Câu 1</th><th>Câu 2</th><th>Nội dung</th></tr>"
                         + rows + "</table>")

    def word_to_tex(self):
        from ...wordconv import PandocMissing, import_docx
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file Word", self.win.settings.value("last_dir", ""),
                                             "Word (*.docx)")
        html_ = []
        for p in ps:
            try:
                tex = import_docx(p)
            except PandocMissing as e:
                QMessageBox.warning(self, "Thiếu pandoc", str(e))
                return
            out = os.path.splitext(p)[0] + "_tuWord.tex"
            with open(out, "w", encoding="utf-8") as f:
                f.write(tex)
            qs = parse_tex(tex)
            self.files.addItem(out)
            html_.append(f"<p>{os.path.basename(p)} → <b>{len(qs)}</b> câu: {out}</p>")
        if html_:
            self.show_result("Word → LaTeX", "".join(html_) + "<p>File mới đã thêm vào danh sách bên trái – "
                             "bấm «Soát lỗi soạn thảo» để kiểm tra đáp án nhận dạng được.</p>")

    def tex_to_word(self):
        from ...wordconv import PandocMissing, export_questions_docx
        html_ = []
        for p in self.paths():
            out = self._save_path(os.path.splitext(os.path.basename(p))[0] + ".docx").replace(".tex", ".docx")
            if not out:
                continue
            try:
                export_questions_docx(parse_file(p), out)
            except PandocMissing as e:
                QMessageBox.warning(self, "Thiếu pandoc", str(e))
                return
            html_.append(f"<p>{os.path.basename(p)} → {out}</p>")
        self.show_result("LaTeX → Word", "".join(html_))

    def file_online(self):
        from ...generator import ExamVersion, sections_from_questions
        from ...online import version_html
        html_ = []
        for p in self.paths():
            base = os.path.splitext(p)[0]
            out, _ = QFileDialog.getSaveFileName(self, "Lưu bài làm online", base + "_online.html", "HTML (*.html)")
            if not out:
                continue
            qs = parse_file(p)
            v = ExamVersion(os.path.basename(base), sections_from_questions(qs))
            with open(out, "w", encoding="utf-8") as f:
                f.write(version_html(v, ten_de="BÀI LÀM", thoi_gian=self.win.gen_panel.e_tg.value()))
            html_.append(f"<p>{os.path.basename(p)} → {out}</p>")
        self.show_result("Bài làm online", "".join(html_) + "<p>Gửi file HTML cho học sinh (Zalo, email…) – "
                         "mở bằng trình duyệt trên điện thoại hoặc máy tính.</p>")

    def file_texstudio(self):
        from ...editor import open_in_texstudio
        for p in self.paths()[:5]:
            if not open_in_texstudio(p, custom=self.win.settings.value("pdf/texstudio", "")):
                QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def file_pdf(self):
        ps = self.paths()
        if ps:
            res = self.win.build_pdfs(prepare_tex_for_pdf(ps, self.win.gen_panel.e_tpl[0].text() or None))
            self.show_result("Biên dịch PDF", "".join(f"<p>{r.summary()}</p>" for r in res))

    def assign_ids_file(self):
        ps = self.paths()
        if not ps:
            return
        qs = parse_file(ps[0])
        AssignIdDialog(self.win, qs, [f"Câu {i}" for i in range(1, len(qs) + 1)], source_file=ps[0]).exec()

    def get_answers(self):
        rows = tools.get_answers(self.paths())
        html = "".join(f"<tr><td>{os.path.basename(f)}</td><td>{t}</td><td>{i}</td><td>{c}</td><td><b>{a}</b></td></tr>"
                       for f, t, i, c, a in rows)
        self.show_result("Bảng đáp án", "<table border=1 cellspacing=0 cellpadding=3><tr><th>File</th><th>Phần</th>"
                         "<th>Câu</th><th>ID</th><th>Đáp án</th></tr>" + html + "</table>")

    def add_tag(self):
        tag, ok = QInputDialog.getText(self, "Thêm nguồn", "Nhãn nguồn chèn vào mọi câu, vd: GK1-THPT-ABC-2025")
        if not ok or not tag.strip():
            return
        html = []
        for p in self.paths():
            out = self._save_path(os.path.splitext(os.path.basename(p))[0] + "_nguon.tex")
            if out:
                html.append(f"<p>{os.path.basename(p)}: thêm nhãn cho <b>{tools.add_tag(p, out, tag.strip())}</b> câu → {out}</p>")
        self.show_result("Thêm nguồn", "".join(html))

    def sort_ids(self):
        ps = self.paths()
        out = self._save_path("gop_sapxep.tex") if ps else ""
        if out:
            self.show_result("Gộp và sắp xếp", f"<p>Đã ghi <b>{tools.sort_by_id(ps, out)}</b> câu, xếp theo loại câu "
                             f"rồi theo ID → {out}</p>")

    def import_to_bank(self):
        lines = []
        for p in self.paths():
            qs = parse_file(p)
            added = sum(1 for q in qs if self.win.bank.add(q, p))
            lines.append(f"<p>{os.path.basename(p)}: {len(qs)} câu, thêm <b>{added}</b>, trùng {len(qs) - added}</p>")
        self.win.build_tree()
        self.win.refresh()
        self.show_result("Nạp vào kho", "".join(lines))
