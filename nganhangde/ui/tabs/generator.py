"""Tab «Tạo đề»: thông tin đề, ma trận, sinh mã đề."""
from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)
from ...exporter import export_versions
from ...generator import NotEnoughQuestions, Rule, THPT_2026, check_structure, make_versions, matrix_from_questions
from ...parser import parse_file
from ..common import TEN_LOAI, TEN_MUC, resource_dir, scroll_of
from ..dialogs.result import ResultDialog
from ..dialogs.swap import SwapDialog
from ..tabs.exam_options import ExamOptionsBox

if TYPE_CHECKING:
    from ..main_window import MainWindow


class GeneratorPanel(QWidget):
    """Tab «Tạo đề»: lập ma trận → sinh nhiều mã đề → xuất .tex/.csv (→ PDF nếu có xelatex)."""
    COLS = ["Loại câu", "Mẫu ID", "Mức độ", "Số câu", "Kho có"]

    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win = win
        self.st = win.settings
        outer = QVBoxLayout(self)
        body = QHBoxLayout()
        outer.addLayout(body, 1)
        lay = QVBoxLayout()
        left = scroll_of(lay)
        left.setMinimumWidth(460)            # đủ rộng cho ô nhập, không bị cắt chữ
        body.addWidget(left, 2)

        g = QGroupBox("Thông tin đề")
        fl = QFormLayout(g)
        self.e_ten = QLineEdit(self.st.value("gen/ten", "ĐỀ KIỂM TRA"))
        self.e_truong = QLineEdit(self.st.value("gen/truong", ""))
        self.e_tg = QSpinBox()
        self.e_tg.setRange(5, 300)
        self.e_tg.setValue(int(self.st.value("gen/tg", 90)))
        self.e_n = QSpinBox()
        self.e_n.setRange(1, 50)
        self.e_n.setValue(int(self.st.value("gen/n", 4)))
        self.e_ma = QLineEdit(self.st.value("gen/ma", ""))
        self.e_ma.setPlaceholderText("để trống = sinh theo «Tuỳ chọn trộn đề → Mã đề»; hoặc nhập 132, 209, …")
        self.e_seed = QLineEdit()
        self.e_seed.setPlaceholderText("để trống = ngẫu nhiên; nhập số để tạo lại đúng bộ đề cũ")
        self.e_out = self._path_row(self.st.value("gen/out", os.path.join(resource_dir(), "de_xuat")), folder=True)
        self.e_tpl = self._path_row(self.st.value("gen/tpl", ""), folder=False)
        self.e_tpl[0].setPlaceholderText("để trống = mau_de\\de_thi.tex trong thư mục phần mềm")
        fl.addRow("Tên đề", self.e_ten)
        fl.addRow("Trường", self.e_truong)
        self.hdr = {}
        for key, label, ph in (("SO_GD", "Sở/Phòng GD", "SỞ GD&ĐT …"), ("KY_THI", "Kì thi", "KIỂM TRA CUỐI HỌC KÌ II"),
                               ("MON_THI", "Môn", "TOÁN 10"), ("NAM_HOC", "Năm học", "2025 – 2026"),
                               ("GIAO_VIEN", "Giáo viên ra đề", "")):
            e = QLineEdit(self.st.value(f"gen/hdr_{key}", ""))
            e.setPlaceholderText(ph)
            self.hdr[key] = e
            fl.addRow(label, e)
        fl.addRow("Thời gian (phút)", self.e_tg)
        fl.addRow("Số mã đề", self.e_n)
        fl.addRow("Danh sách mã đề", self.e_ma)
        fl.addRow("Hạt giống (seed)", self.e_seed)
        fl.addRow("Thư mục xuất", self.e_out[1])
        fl.addRow("File mẫu .tex", self.e_tpl[1])
        self.c_diff = QCheckBox("Mỗi mã đề một bộ câu khác nhau")
        self.sp_overlap = QSpinBox()
        self.sp_overlap.setRange(0, 100)
        self.sp_overlap.setValue(int(self.st.value("gen/overlap", 100)))
        self.sp_overlap.setSuffix(" %")
        self.sp_overlap.setToolTip("Khi mỗi mã một bộ câu: tỉ lệ câu trùng tối đa giữa 2 mã đề (100% = không giới hạn)")
        self.c_preview = QCheckBox("Xem trước bộ câu để «đổi câu» trước khi trộn")
        self.c_unused = QCheckBox("Ưu tiên câu ít được dùng")
        self.c_unused.setChecked(True)
        self.c_pdf = QCheckBox("Biên dịch luôn ra PDF (dùng LaTeX trên máy: TeX Live/MiKTeX – như TeXstudio)")
        self.c_pdf.setEnabled(bool(win.engine(quiet=True)))
        self.c_pdf.setChecked(str(self.st.value("gen/pdf", False)).lower() == "true" and self.c_pdf.isEnabled())
        for c in (self.c_diff,):
            fl.addRow("", c)
        fl.addRow("  Trùng tối đa giữa 2 mã", self.sp_overlap)
        self.sp_recent = QSpinBox()
        self.sp_recent.setRange(0, 50)
        self.sp_recent.setValue(int(self.st.value("gen/recent", 0)))
        self.sp_recent.setSuffix(" đợt gần nhất")
        self.sp_recent.setSpecialValueText("không tránh")
        self.sp_recent.setToolTip("Không lấy lại câu đã dùng trong N đợt ra đề gần nhất (xem Đề thi → Lịch sử ra đề)")
        fl.addRow("Tránh câu đã dùng trong", self.sp_recent)
        for c in (self.c_unused, self.c_preview, self.c_pdf):
            fl.addRow("", c)
        lay.addWidget(g)

        g = QGroupBox("Tuỳ chọn trộn đề")
        ol = QVBoxLayout(g)
        b = QPushButton("⭐ Áp dụng chuẩn đề thi tốt nghiệp THPT 2026")
        b.setToolTip("12 câu trắc nghiệm · 4 câu Đúng/Sai · 6 câu trả lời ngắn · 90 phút · 24 mã 0101…0124 · "
                     "giữ thứ tự ý Đúng/Sai · đánh số lại từng phần · lời dẫn chính thức · thang điểm · đáp án TNMaker")
        b.clicked.connect(self.apply_thpt2026)
        ol.addWidget(b)
        self.c_check2026 = QCheckBox("Kiểm tra ma trận theo cấu trúc 12 – 4 – 6 khi tạo đề")
        self.c_check2026.setChecked(str(self.st.value("gen/check2026", False)).lower() == "true")
        ol.addWidget(self.c_check2026)
        self.opts = ExamOptionsBox(self.st, "gen")
        self.mix = self.opts.mix
        ol.addWidget(self.opts)
        lay.addWidget(g)
        g2 = QGroupBox("Hướng dẫn")
        hl = QVBoxLayout(g2)
        hint = QLabel("<b>Mẫu ID</b> dùng kí tự đại diện:<br>"
                      "&nbsp;• <code>0D2*</code> – lớp 10, Đại số, chương 2<br>"
                      "&nbsp;• <code>0H9?3-*</code> – chương 9 Hình, bài 3, mọi mức độ<br>"
                      "&nbsp;• <code>0D[08]*</code> – chương 0 hoặc 8<br>"
                      "Cột <b>Kho có</b> màu đỏ nghĩa là kho chưa đủ câu cho dòng đó.<br>"
                      "Kết quả: <code>de_&lt;mã&gt;.tex</code>, <code>loigiai_&lt;mã&gt;.tex</code>, "
                      "<code>dap_an.csv</code>.")
        hint.setWordWrap(True)
        hl.addWidget(hint)
        lay.addWidget(g2)
        lay.addStretch()

        lay = QVBoxLayout()
        body.addLayout(lay, 3)
        g = QGroupBox("Ma trận đề")
        gl = QVBoxLayout(g)
        self.t = QTableWidget(0, len(self.COLS))
        self.t.setHorizontalHeaderLabels(self.COLS)
        self.t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.itemChanged.connect(lambda it: it.column() == 1 and self.update_avail())
        gl.addWidget(self.t)
        from PySide6.QtWidgets import QGridLayout
        grid = QGridLayout()
        for k, (text, fn) in enumerate((("Thêm dòng", self.add_row), ("Xoá dòng", self.del_row),
                                        ("Kiểm tra số câu", self.update_avail), ("Mở ma trận…", self.load_matrix),
                                        ("Lưu ma trận…", self.save_matrix),
                                        ("Ma trận từ đề có sẵn…", self.matrix_from_exam),
                                        ("In ma trận đặc tả…", self.print_matrix),
                                        ("Ma trận CV 7991…", self.export_cv7991))):
            b = QPushButton(text)
            b.clicked.connect(fn)
            grid.addWidget(b, k // 4, k % 4)
        gl.addLayout(grid)
        self.l_total = QLabel()
        self.l_total.setWordWrap(True)
        gl.addWidget(self.l_total)
        lay.addWidget(g, 1)

        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("TẠO ĐỀ")
        b.setObjectName("primary")
        b.setMinimumWidth(160)
        b.clicked.connect(self.generate)
        row.addWidget(b)
        outer.addLayout(row)

        saved = self.st.value("gen/matrix", "")
        rules = json.loads(saved) if saved else [
            {"qtype": "TN", "id": "*", "count": 12}, {"qtype": "DS", "id": "*", "count": 4},
            {"qtype": "KQ", "id": "*", "count": 6}]
        for r in rules:
            self.add_row(r)
        self.update_avail()

    def _path_row(self, value, folder):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        e = QLineEdit(value)
        b = QPushButton("…")
        b.setFixedWidth(40)

        def pick():
            if folder:
                p = QFileDialog.getExistingDirectory(self, "Chọn thư mục", e.text())
            else:
                p, _ = QFileDialog.getOpenFileName(self, "Chọn file mẫu", e.text(), "LaTeX (*.tex)")
            if p:
                e.setText(p)
        b.clicked.connect(pick)
        h.addWidget(e)
        h.addWidget(b)
        return e, w

    # --- ma trận
    def add_row(self, r=None):
        r = r if isinstance(r, dict) else {"qtype": "TN", "id": "*", "count": 1}
        i = self.t.rowCount()
        self.t.blockSignals(True)          # chưa tính «Kho có» khi dòng chưa dựng xong
        self.t.insertRow(i)
        cb = QComboBox()
        for k, v in TEN_LOAI.items():
            cb.addItem(v, k)
        cb.setCurrentIndex(list(TEN_LOAI).index(r.get("qtype", "TN")))
        cb.currentIndexChanged.connect(self.update_avail)
        self.t.setCellWidget(i, 0, cb)
        self.t.setItem(i, 1, QTableWidgetItem(r.get("id", "*")))
        md = QComboBox()
        md.addItem("Tất cả", "")
        for k, v in TEN_MUC.items():
            md.addItem(v, k)
        md.setCurrentIndex(max(0, md.findData(r.get("muc_do") or "")))
        md.currentIndexChanged.connect(self.update_avail)
        self.t.setCellWidget(i, 2, md)
        sp = QSpinBox()
        sp.setRange(1, 200)
        sp.setValue(int(r.get("count", 1)))
        sp.valueChanged.connect(self.update_avail)
        self.t.setCellWidget(i, 3, sp)
        it = QTableWidgetItem("")
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.t.setItem(i, 4, it)
        self.t.blockSignals(False)

    def del_row(self):
        for r in sorted({i.row() for i in self.t.selectedIndexes()}, reverse=True):
            self.t.removeRow(r)
        self.update_avail()

    def rules_dicts(self):
        out = []
        for i in range(self.t.rowCount()):
            if None in (self.t.cellWidget(i, 0), self.t.cellWidget(i, 2), self.t.cellWidget(i, 3)):
                continue                   # dòng đang dựng dở
            out.append({"qtype": self.t.cellWidget(i, 0).currentData(),
                        "id": (self.t.item(i, 1).text().strip() if self.t.item(i, 1) else "") or "*",
                        "muc_do": self.t.cellWidget(i, 2).currentData() or None,
                        "count": self.t.cellWidget(i, 3).value()})
        return out

    def update_avail(self):
        if not self.win.bank:
            return
        total, ok = 0, True
        for i, r in enumerate(self.rules_dicts()):
            n = len(self.win.bank.search(qtype=r["qtype"], id_like=r["id"], muc_do=r["muc_do"]))
            it = self.t.item(i, 4)
            if it:
                it.setText(str(n))
                it.setForeground(QColor("#0b7a0b" if n >= r["count"] else "#c00000"))
            total += r["count"]
            ok &= n >= r["count"]
        self.l_total.setText(f"Tổng: <b>{total}</b> câu" + ("" if ok else
                             " – <span style='color:#c00000'>có dòng thiếu câu</span>"))

    def load_matrix(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở ma trận", "", "Ma trận (*.json *.xlsx)")
        if not p:
            return
        if p.lower().endswith(".xlsx"):
            from ...matrix import import_xlsx
            try:
                rules = import_xlsx(p)
            except ValueError as e:
                QMessageBox.warning(self, "Nạp ma trận", str(e))
                return
            self.t.setRowCount(0)
            for r in rules:
                self.add_row({"qtype": r.qtype, "id": r.id, "muc_do": r.muc_do or "", "text": r.text or "",
                              "count": r.count})
            self.update_avail()
            return
        with open(p, encoding="utf-8") as f:
            cfg = json.load(f)
        self.t.setRowCount(0)
        for r in cfg.get("rules", []):
            self.add_row(r)
        self.e_ten.setText(cfg.get("ten_de", self.e_ten.text()))
        self.e_truong.setText(cfg.get("truong", self.e_truong.text()))
        self.e_tg.setValue(int(cfg.get("thoi_gian", self.e_tg.value())))
        if cfg.get("ma_de"):
            self.e_ma.setText(", ".join(cfg["ma_de"]))
            self.e_n.setValue(len(cfg["ma_de"]))
        self.update_avail()

    def save_matrix(self):
        p, _ = QFileDialog.getSaveFileName(self, "Lưu ma trận", "ma_tran.json", "Ma trận (*.json)")
        if not p:
            return
        cfg = {"ten_de": self.e_ten.text(), "truong": self.e_truong.text(), "thoi_gian": self.e_tg.value(),
               "rules": self.rules_dicts()}
        if self.codes():
            cfg["ma_de"] = self.codes()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)

    def codes(self):
        return [c.strip() for c in re.split(r"[,;\s]+", self.e_ma.text()) if c.strip()]

    # --- sinh đề
    def generate(self):
        rd = self.rules_dicts()
        if not rd:
            QMessageBox.warning(self, "Lỗi", "Ma trận chưa có dòng nào.")
            return
        rules = [Rule.from_dict(r) for r in rd]
        if self.c_check2026.isChecked():
            diff = check_structure(rules)
            if diff and QMessageBox.question(self, "Lệch cấu trúc đề 2026", "\n".join(diff) + "\n\nVẫn tạo đề?") \
                    != QMessageBox.StandardButton.Yes:
                return
        codes = self.codes() or self.opts.codes(self.e_n.value())
        seed = int(self.e_seed.text()) if self.e_seed.text().strip().isdigit() else None
        sections = None
        excl = self.win.bank.recent_question_ids(self.sp_recent.value()) if self.sp_recent.value() else set()
        try:
            if self.c_preview.isChecked() and not self.c_diff.isChecked():
                import random as _r
                from ...generator import pick_questions
                sections = pick_questions(self.win.bank, rules, _r.Random(seed), self.c_unused.isChecked(), excl)
                dlg = SwapDialog(self, sections, rules)
                if not dlg.exec():
                    return
                sections = dlg.sections
            ov = self.sp_overlap.value()
            vs = make_versions(self.win.bank, rules, len(codes), codes=codes,
                               seed=seed, same_questions=not self.c_diff.isChecked(),
                               prefer_unused=self.c_unused.isChecked(), options=self.opts.mix_options(),
                               max_overlap=(ov / 100 if self.c_diff.isChecked() and ov < 100 else None),
                               sections=sections, exclude_ids=excl)
        except NotEnoughQuestions as e:
            QMessageBox.warning(self, "Không đủ câu", str(e))
            return
        out = self.e_out[0].text()
        try:
            files = export_versions(vs, out, template_path=self.e_tpl[0].text() or None,
                                    ten_de=self.e_ten.text(), truong=self.e_truong.text(),
                                    thoi_gian=self.e_tg.value(), options=self.export_options())
        except (OSError, ValueError) as e:
            QMessageBox.critical(self, "Lỗi ghi file", str(e))
            return
        self.win.bank.mark_used({q.db_id for v in vs for q in v.all_questions()})
        self.win.bank.log_batch(vs, ten_de=self.e_ten.text(), seed=seed, matrix=rd, out_dir=out)
        self.win.refresh()
        for k, v in (("ten", self.e_ten.text()), ("truong", self.e_truong.text()), ("tg", self.e_tg.value()),
                     ("n", self.e_n.value()), ("ma", self.e_ma.text()), ("out", out),
                     ("tpl", self.e_tpl[0].text()), ("matrix", json.dumps(rd, ensure_ascii=False))):
            self.st.setValue(f"gen/{k}", v)
        self.opts.save()
        self.st.setValue("gen/check2026", self.c_check2026.isChecked())
        self.st.setValue("gen/overlap", self.sp_overlap.value())
        self.st.setValue("gen/recent", self.sp_recent.value())
        for k, e in self.hdr.items():
            self.st.setValue(f"gen/hdr_{k}", e.text())
        self.st.setValue("gen/pdf", self.c_pdf.isChecked())
        extra = ""
        if self.c_pdf.isChecked():
            res = self.win.build_pdfs([f for f in files if f.endswith(".tex")], "Biên dịch đề ra PDF",
                                      open_single=False)
            ok = sum(r.ok for r in res)
            extra = (f"<p><b>Biên dịch PDF:</b> {ok}/{len(res)} file thành công.</p>"
                     + "".join(f"<p style='color:#c00000'>{r.summary()}</p>" for r in res if not r.ok))
        ResultDialog(self, vs, out, extra).exec()

    def export_options(self):
        from ..dialogs.online_settings import load
        o = self.opts.export_options()
        o.header = {k: e.text() for k, e in self.hdr.items()}
        o.online_style, o.gform = load(self.win.settings)
        return o

    def print_matrix(self):
        rd = self.rules_dicts()
        if not rd:
            return
        p, _ = QFileDialog.getSaveFileName(self, "In ma trận đặc tả", "ma_tran_dac_ta.xlsx",
                                           "Excel (*.xlsx);;LaTeX (*.tex)")
        if p:
            from ...exporter import matrix_spec
            matrix_spec(self.win.bank, [Rule.from_dict(r) for r in rd], p)
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def export_cv7991(self):
        rd = self.rules_dicts()
        if not rd:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Ma trận theo CV 7991", "ma_tran_CV7991.xlsx",
                                           "Excel (*.xlsx);;Word (*.docx)")
        if not p:
            return
        from ... import matrix
        rules = [Rule.from_dict(r) for r in rd]
        sc = self.export_options().scoring_obj()
        try:
            if p.lower().endswith(".docx"):
                matrix.export_docx(rules, p, self.win.bank.idmap(), sc, self.e_ten.text())
            else:
                matrix.export_xlsx(rules, p, self.win.bank.idmap(), sc, self.e_ten.text())
        except Exception as e:      # pandoc thiếu, file đang mở…
            QMessageBox.warning(self, "Ma trận CV 7991", str(e))
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def apply_thpt2026(self):
        self.opts.apply_thpt2026()
        self.e_n.setValue(THPT_2026["so_ma"])
        self.e_ma.clear()
        self.e_tg.setValue(THPT_2026["phut"])
        self.c_check2026.setChecked(True)
        rules = [Rule.from_dict(r) for r in self.rules_dicts()]
        diff = check_structure(rules)
        if diff and QMessageBox.question(
                self, "Ma trận chuẩn 2026", "Ma trận hiện tại lệch cấu trúc chuẩn:\n" + "\n".join(diff)
                + "\n\nĐặt lại ma trận thành 12 trắc nghiệm · 4 Đúng/Sai · 6 trả lời ngắn (mọi ID)?\n"
                "(Chọn No để giữ ma trận và tự chỉnh)") == QMessageBox.StandardButton.Yes:
            self.t.setRowCount(0)
            for qt in ("TN", "DS", "KQ"):
                self.add_row({"qtype": qt, "id": "*", "count": THPT_2026[qt]})
            self.update_avail()
        QMessageBox.information(self, "Chuẩn 2026", "Đã đặt: 24 mã đề 0101…0124, 90 phút, giữ thứ tự ý Đúng/Sai, "
                                "đánh số lại từng phần, lời dẫn chính thức, thang điểm, đáp án Excel cho TNMaker.\n"
                                "Xem/sửa ở mục «Tuỳ chọn trộn đề».")

    def matrix_from_exam(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file đề mẫu (.tex)", self.st.value("last_dir", ""),
                                           "LaTeX (*.tex)")
        if not p:
            return
        levels = {"Cùng bài (khuyên dùng)": "bai", "Cùng dạng": "dang", "Cùng chương": "chuong"}
        lv, ok = QInputDialog.getItem(self, "Ma trận từ đề có sẵn",
                                      "Lấy câu tương đương theo mức nào?", list(levels), 0, False)
        if not ok:
            return
        rules = matrix_from_questions(parse_file(p), levels[lv])
        self.t.setRowCount(0)
        for r in rules:
            self.add_row({"qtype": r.qtype, "id": r.id, "muc_do": r.muc_do, "count": r.count})
        self.update_avail()
