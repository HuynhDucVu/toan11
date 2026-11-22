"""«Tuỳ chọn đề» theo bố cục MyLT 2026: một màn hình gồm Tuỳ chọn chung · Tuỳ chọn phiếu · Cài đặt tiêu đề · Tên file · Lưu ma trận.

Panel này là giao diện chính; mọi giá trị được đẩy sang các ô của «Nâng cao» (GeneratorPanel – nơi còn ma trận, thang điểm,
online/Word…) bằng apply(), nên cả hai nơi luôn cùng một bộ tuỳ chọn. Các ô «phiếu» (Trang riêng, SBD 5 số…) chỉ được lưu
cấu hình – bản này chưa dùng chúng khi in phiếu (xem tooltip)."""
from __future__ import annotations

import json
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout, QWidget)

from ...appdirs import folder

EXCEL_ITEMS = (("", ""), ("Không tạo", "none"), ("Bảng dọc", "doc"), ("Bảng ngang", "ngang"), ("Kiểu McMix", "doc"),
               ("Azota 2024", "doc"), ("TNMaker", "mylt"), ("TNMaker 2024", "mylt"), ("Kiểu SmartTest", "doc"))
SORT_ITEMS = ("Theo lớp", "Theo môn", "Theo chương", "Theo mức độ", "Theo bài", "Theo dạng")
SHEET_CHECKS = (("tren", "Lên trên"), ("trang_rieng", "Trang riêng"), ("abcd", "Chèn ABCD"), ("ngang", "Phiếu ngang"),
                ("chi_dap_an", "Chỉ đáp án"), ("sbd5", "SBD 5 số"), ("ghi_chu", "Ghi chú"), ("hs_lop", "HS lớp"),
                ("azota", "Azota 50A5"), ("tnmaker60", "TNMaker 60"), ("chamthi", "Chấm Thi 50A5"),
                ("mau_phieu", "Màu toàn phiếu"), ("tieu_de", "Tiêu đề"))
SHEET_DEFAULT_ON = {"abcd", "ghi_chu", "hs_lop"}


class CheckCombo(QComboBox):
    """Ô chọn nhiều mục (tick) như «Sắp xếp câu hỏi» của MyLT."""

    def __init__(self, items, hint):
        super().__init__()
        self.hint = hint
        self.m = QStandardItemModel(self)
        self.setModel(self.m)
        for t in items:
            it = QStandardItem(t)
            it.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.m.appendRow(it)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.m.itemChanged.connect(self._show)
        self._show()

    def checked(self) -> list[str]:
        return [self.m.item(i).text() for i in range(self.m.rowCount())
                if self.m.item(i).checkState() == Qt.CheckState.Checked]

    def set_checked(self, names):
        for i in range(self.m.rowCount()):
            self.m.item(i).setCheckState(Qt.CheckState.Checked if self.m.item(i).text() in names else Qt.CheckState.Unchecked)
        self._show()

    def _show(self, *_):
        self.lineEdit().setText(", ".join(self.checked()) or self.hint)


class MyltOptionsPanel(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.st = win.settings
        self.gp = win.gen_panel
        self._lock = False
        lay = QVBoxLayout(self)
        # ---------------------------------------------------------------- Tuỳ chọn chung
        g = QGroupBox("Tuỳ chọn chung")
        gl = QGridLayout(g)
        self.cb_n = QComboBox()
        for n in list(range(1, 13)) + [16, 20, 24, 30, 40, 50]:
            self.cb_n.addItem(str(n), n)
        self.cb_orig = QComboBox()
        self.cb_orig.addItem("Một đề gốc", False)
        self.cb_orig.addItem("Mỗi mã một đề gốc", True)
        self.cb_qr = QComboBox()
        for t, d in (("", ""), ("Không", ""), ("Kiểu gọn", "gon"), ("Kiểu MD", "md"), ("JSON", "json")):
            self.cb_qr.addItem(t, d)
        self.cb_sheet = QComboBox()
        for t, d in (("", ""), ("Phiếu TLTN THPT QG 2025", "tltn"), ("Phiếu trắng + phiếu khoá", "sheet")):
            self.cb_sheet.addItem(t, d)
        self.cb_xlsx = QComboBox()
        for t, d in EXCEL_ITEMS:
            self.cb_xlsx.addItem(t, d)
        self.cb_xlsx.setToolTip("TNMaker / TNMaker 2024: bố cục «MyLT» (số câu liên tục). Bảng dọc / ngang: mỗi mã một cột / một dòng. "
                                "McMix, Azota 2024, SmartTest: dùng bảng dọc gần đúng – chưa kiểm tra với phần mềm đó.")
        for r, (lab, w) in enumerate((("Số đề tạo ra", self.cb_n), ("Kiểu đề gốc", self.cb_orig),
                                      ("Đáp án Qrcode", self.cb_qr), ("Phiếu làm bài", self.cb_sheet),
                                      ("Đáp án Excel", self.cb_xlsx))):
            gl.addWidget(QLabel(lab), r, 0)
            gl.addWidget(w, r, 1)
        self.ck: dict[str, QCheckBox] = {}

        def check(key, text, r, c, tip=""):
            cb = QCheckBox(text)
            if tip:
                cb.setToolTip(tip)
            self.ck[key] = cb
            gl.addWidget(cb, r, c)
        for r, (k, t, tip) in enumerate((
                ("an_dap_an", "Ẩn đáp án", "Đáp án trong file đề nằm trong môi trường bật/tắt bằng 1 lệnh (\\showansfalse)"),
                ("hien_loi_giai", "Hiện lời giải", "(chưa áp dụng) – lời giải luôn nằm trong file loigiai_<mã>.tex"),
                ("dap_an_rieng", "Đáp án riêng", "(chưa áp dụng) – đáp án luôn xuất riêng: dap_an.csv và file Excel"),
                ("dap_an_cuoi", "Đáp án ở cuối", "In bảng đáp án ở trang cuối file đề"),
                ("de_rieng", "File đề riêng", "Mỗi mã đề một thư mục riêng"))):
            check(k, t, r, 2, tip)
        for r, (k, t, tip) in enumerate((
                ("bien_dich", "Biên dịch đề", "Biên dịch ra PDF ngay sau khi tạo đề (cần LaTeX trên máy)"),
                ("trang_trong", "Chèn trang trống", "Thêm trang trống để mỗi đề có số trang chẵn (in 2 mặt)"),
                ("tron_kq", "Trộn trả lời ngắn", ""), ("co_dinh_pa4", "Cố định PA4 câu ĐS", "Câu Đúng/Sai giữ ý d) ở cuối"),
                ("khong_tron_ds", "Không trộn đúng sai", "Giữ nguyên thứ tự ý a, b, c, d"),
                )):
            check(k, t, r, 3, tip)
        check("giu_nguyen", "Giữ nguyên đề", 5, 3, "Không trộn gì cả (thứ tự câu, phương án, ý Đúng/Sai)")
        gl.addWidget(QLabel(""), 5, 2)
        # cột 4: mã đề + sắp xếp
        self.ck["ma_cach"] = QCheckBox("Mã đề cách")
        self.sp_cach = QSpinBox()
        self.sp_cach.setRange(1, 100)
        self.ck["ma_3so"] = QCheckBox("Mã đề 3 số")
        self.ck["ma_3so"].setToolTip("Bỏ tick: mã 4 số (0101…)")
        self.ck["ma_tu_nhap"] = QCheckBox("Mã đề tự nhập")
        self.e_ma = QLineEdit()
        self.e_ma.setPlaceholderText("vd 132, 209, 357")
        b_q = QPushButton("?")
        b_q.setFixedWidth(26)
        b_q.clicked.connect(lambda: QMessageBox.information(
            self, "Mã đề", "Nhập các mã đề cách nhau dấu phẩy, vd 132, 209, 357, 485. Có nhập thì «Số đề tạo ra» "
                           "không dùng nữa."))
        gl.addWidget(self.ck["ma_cach"], 0, 4)
        gl.addWidget(self.sp_cach, 0, 5)
        gl.addWidget(self.ck["ma_3so"], 0, 6)
        b_zone = QPushButton("Trộn đề theo vùng")
        b_zone.clicked.connect(self.pick_region)
        gl.addWidget(b_zone, 0, 7)
        gl.addWidget(self.ck["ma_tu_nhap"], 1, 4, 1, 2)
        gl.addWidget(self.e_ma, 1, 6)
        gl.addWidget(b_q, 1, 7)
        gl.addWidget(QLabel("Sắp xếp câu hỏi"), 2, 4)
        self.cc_sort = CheckCombo(SORT_ITEMS, "Chọn mục theo thứ tự cần sắp xếp")
        gl.addWidget(self.cc_sort, 2, 5, 1, 3)
        self.ck["theo_ma_tran"] = QCheckBox("Xếp theo ma trận")
        self.ck["doi_cau_goc"] = QCheckBox("Đổi câu gốc")
        self.ck["doi_cau_goc"].setToolTip("Xem trước bộ câu và đổi từng câu trước khi trộn")
        b_clear = QPushButton("Xoá đánh dấu câu")
        b_clear.setToolTip("Đặt lại bộ đếm «đã lấy ra đề» của mọi câu về 0")
        b_clear.clicked.connect(self.clear_marks)
        gl.addWidget(self.ck["theo_ma_tran"], 3, 4, 1, 2)
        gl.addWidget(self.ck["doi_cau_goc"], 3, 6)
        gl.addWidget(b_clear, 3, 7)
        gl.addWidget(QLabel("Tỉ lệ đáp án TN"), 4, 4)
        self.cb_ratio = QComboBox()
        self.cb_ratio.setEditable(True)
        for t in ("", "1,1,1,1", "2,2,3,3", "3,3,2,2", "2,3,3,2", "3,2,2,3"):
            self.cb_ratio.addItem(t)
        self.cb_ratio.setToolTip("Tỉ lệ đáp án A:B:C:D; trống = chia đều")
        gl.addWidget(self.cb_ratio, 4, 5, 1, 3)
        lay.addWidget(g)
        # ---------------------------------------------------------------- phiếu
        g = QGroupBox("Tuỳ chọn phiếu Zipgrade - TNMaker - Chấm Thi - QR Code - Azota - UnT")
        pl = QGridLayout(g)
        self.sheet: dict[str, QCheckBox] = {}
        for i, (k, t) in enumerate(SHEET_CHECKS):
            cb = QCheckBox(t)
            cb.setToolTip("Lưu cấu hình phiếu – bản này chưa áp dụng vào phiếu PDF")
            cb.setChecked(str(self.st.value(f"mo/sheet_{k}", k in SHEET_DEFAULT_ON)).lower() == "true")
            self.sheet[k] = cb
            pl.addWidget(cb, i % 2, i // 2)
        self.cb_color = QComboBox()
        self.cb_line = QComboBox()
        for cb_, items in ((self.cb_color, ("", "Đen", "Xanh", "Đỏ")), (self.cb_line, ("", "Mảnh", "Vừa", "Đậm"))):
            cb_.addItems(items)
        pl.addWidget(QLabel("Màu vẽ"), 0, 7)
        pl.addWidget(self.cb_color, 0, 8)
        pl.addWidget(QLabel("Nét vẽ"), 1, 7)
        pl.addWidget(self.cb_line, 1, 8)
        b = QPushButton("Hướng dẫn")
        b.clicked.connect(lambda: QMessageBox.information(
            self, "Tuỳ chọn phiếu", "Phiếu trả lời (TLTN THPT QG 2025: 40·8·6 câu) do ô «Phiếu làm bài» điều khiển. "
                                    "Các ô tick ở đây lưu cấu hình theo MyLT; bản này chưa dùng chúng khi vẽ phiếu."))
        pl.addWidget(b, 1, 9)
        lay.addWidget(g)
        # ---------------------------------------------------------------- tiêu đề
        g = QGroupBox("Cài đặt tiêu đề")
        tl = QGridLayout(g)
        self.e_truong = QLineEdit()
        self.e_gv = QLineEdit()
        self.cb_header = QComboBox()
        self.e_ky = QLineEdit()
        self.e_mon = QLineEdit()
        self.e_tg = QLineEdit()
        b_h = QPushButton("?")
        b_h.setFixedWidth(26)
        b_h.clicked.connect(lambda: QMessageBox.information(
            self, "File header", "File header = file mẫu đề .tex trong thư mục TEMPLATE (vd Header_MyLT.tex, de_thi.tex). "
                                 "Chép thêm file vào TEMPLATE là có thêm lựa chọn."))
        tl.addWidget(QLabel("Tên trường"), 0, 0)
        tl.addWidget(self.e_truong, 0, 1, 1, 2)
        tl.addWidget(QLabel("Tên kỳ thi"), 0, 3)
        tl.addWidget(self.e_ky, 0, 4)
        tl.addWidget(QLabel("Tên giáo viên"), 1, 0)
        tl.addWidget(self.e_gv, 1, 1, 1, 2)
        tl.addWidget(QLabel("Tên môn thi"), 1, 3)
        tl.addWidget(self.e_mon, 1, 4)
        tl.addWidget(QLabel("File header"), 2, 0)
        tl.addWidget(self.cb_header, 2, 1)
        tl.addWidget(b_h, 2, 2)
        tl.addWidget(QLabel("Thời gian"), 2, 3)
        tl.addWidget(self.e_tg, 2, 4)
        tl.setColumnStretch(1, 1)
        tl.setColumnStretch(4, 1)
        lay.addWidget(g)
        row = QHBoxLayout()
        g = QGroupBox("Tên file đề tạo ra")
        v = QVBoxLayout(g)
        self.e_file_name = QLineEdit()
        self.e_file_name.setPlaceholderText("trống = de_<mã>.tex; vd KT15p → KT15p_<mã>.tex")
        v.addWidget(self.e_file_name)
        row.addWidget(g, 1)
        g = QGroupBox("Lưu ma trận")
        h = QHBoxLayout(g)
        h.addWidget(QLabel("Tên"))
        self.e_matrix = QLineEdit()
        h.addWidget(self.e_matrix, 1)
        b = QPushButton("Lưu")
        b.clicked.connect(self.save_matrix)
        h.addWidget(b)
        row.addWidget(g, 1)
        lay.addLayout(row)
        lay.addStretch()
        self.pull()
        for w in self.findChildren(QCheckBox):
            w.toggled.connect(self.apply)
        for w in (self.cb_n, self.cb_orig, self.cb_qr, self.cb_sheet, self.cb_xlsx, self.cb_header):
            w.currentIndexChanged.connect(self.apply)
        for w in (self.e_ma, self.e_truong, self.e_gv, self.e_ky, self.e_mon, self.e_tg, self.e_file_name):
            w.textChanged.connect(self.apply)
        self.cb_ratio.currentTextChanged.connect(self.apply)
        self.sp_cach.valueChanged.connect(self.apply)
        self.cc_sort.m.itemChanged.connect(self.apply)
        win.opt_panel = self
        self.apply()

    # ---------------------------------------------------------------- dữ liệu
    def n_codes(self) -> int:
        return int(self.cb_n.currentData() or 1)

    def _reload_headers(self):
        from ...appdirs import path as app_path
        import glob
        self.cb_header.blockSignals(True)
        self.cb_header.clear()
        self.cb_header.addItem("", "")
        for p in sorted(glob.glob(os.path.join(app_path("mau_de"), "*.tex"))):
            if not os.path.basename(p).startswith("_"):
                self.cb_header.addItem(os.path.basename(p), p)
        self.cb_header.setCurrentIndex(max(0, self.cb_header.findData(self.gp.e_tpl[0].text())))
        self.cb_header.blockSignals(False)

    def pull(self):
        """Đọc giá trị hiện có của GeneratorPanel (đã nạp từ cấu hình) vào các ô."""
        gp, o, mix = self.gp, self.gp.opts, self.gp.opts.mix
        self._lock = True
        self.cb_n.setCurrentIndex(max(0, self.cb_n.findData(gp.e_n.value())))
        self.cb_orig.setCurrentIndex(1 if gp.c_diff.isChecked() else 0)
        self.cb_qr.setCurrentIndex(max(0, self.cb_qr.findData(o.cb_qrfmt.currentData())) if o.c_qr.isChecked() else 0)
        self.cb_sheet.setCurrentIndex(1 if o.c_tltn.isChecked() else 2 if o.c_sheet.isChecked() else 0)
        lay = o.cb_layout.currentData()
        self.cb_xlsx.setCurrentIndex(0 if not o.c_xlsx.isChecked() else
                                     {"mylt": 7, "doc": 2, "ngang": 3}.get(lay, 7))
        self.ck["an_dap_an"].setChecked(o.c_toggle.isChecked())
        self.ck["dap_an_cuoi"].setChecked(o.c_ans_end.isChecked())
        self.ck["de_rieng"].setChecked(o.c_folder.isChecked())
        self.ck["bien_dich"].setChecked(gp.c_pdf.isChecked())
        self.ck["trang_trong"].setChecked(o.c_even.isChecked())
        self.ck["tron_kq"].setChecked(mix.boxes["shuffle_kq"].isChecked())
        self.ck["co_dinh_pa4"].setChecked(mix.boxes["fix_ds_last"].isChecked())
        self.ck["khong_tron_ds"].setChecked(not mix.boxes["shuffle_ds"].isChecked())
        self.ck["giu_nguyen"].setChecked(str(self.st.value("mo/giu_nguyen", False)).lower() == "true")
        self.ck["hien_loi_giai"].setChecked(str(self.st.value("mo/hien_loi_giai", False)).lower() == "true")
        self.ck["dap_an_rieng"].setChecked(str(self.st.value("mo/dap_an_rieng", False)).lower() == "true")
        self.ck["ma_3so"].setChecked(o.cb_digits.currentData() == 3)
        self.ck["ma_cach"].setChecked(o.sp_step.value() > 1)
        self.sp_cach.setValue(o.sp_step.value())
        self.ck["ma_tu_nhap"].setChecked(bool(gp.e_ma.text().strip()))
        self.e_ma.setText(gp.e_ma.text())
        self.cc_sort.set_checked([x for x in str(self.st.value("mo/sort", "")).split("|") if x])
        self.ck["theo_ma_tran"].setChecked(mix.cb_order.currentData() == "matrix")
        self.ck["doi_cau_goc"].setChecked(gp.c_preview.isChecked())
        self.cb_ratio.setCurrentText(mix.e_ratio.text())
        self.e_truong.setText(gp.e_truong.text())
        self.e_gv.setText(gp.hdr["GIAO_VIEN"].text())
        self.e_ky.setText(gp.hdr["KY_THI"].text())
        self.e_mon.setText(gp.hdr["MON_THI"].text())
        self.e_tg.setText(str(gp.e_tg.value()))
        self.e_file_name.setText(str(self.st.value("mo/file_name", "")))
        self.cb_color.setCurrentText(str(self.st.value("mo/color", "")))
        self.cb_line.setCurrentText(str(self.st.value("mo/line", "")))
        self._reload_headers()
        self._lock = False

    def showEvent(self, e):
        super().showEvent(e)
        self._reload_headers()

    def apply(self, *_):
        """Đẩy giá trị các ô sang GeneratorPanel (nguồn duy nhất mà bộ xuất đề đọc)."""
        if self._lock:
            return
        gp, o, mix = self.gp, self.gp.opts, self.gp.opts.mix
        gp.e_n.setValue(self.n_codes())
        gp.c_diff.setChecked(bool(self.cb_orig.currentData()))
        qr = self.cb_qr.currentData()
        o.c_qr.setChecked(bool(qr))
        if qr:
            o.cb_qrfmt.setCurrentIndex(max(0, o.cb_qrfmt.findData(qr)))
        sheet = self.cb_sheet.currentData()
        o.c_tltn.setChecked(sheet == "tltn")
        o.c_sheet.setChecked(sheet == "sheet")
        x = self.cb_xlsx.currentData()
        if x:
            o.c_xlsx.setChecked(x != "none")
            if x != "none":
                o.cb_profile.setCurrentIndex(max(0, o.cb_profile.findData("tnmaker")))
                o.cb_layout.setCurrentIndex(max(0, o.cb_layout.findData(x)))
        o.c_toggle.setChecked(self.ck["an_dap_an"].isChecked())
        o.c_ans_end.setChecked(self.ck["dap_an_cuoi"].isChecked())
        o.c_folder.setChecked(self.ck["de_rieng"].isChecked())
        gp.c_pdf.setChecked(self.ck["bien_dich"].isChecked() and gp.c_pdf.isEnabled())
        o.c_even.setChecked(self.ck["trang_trong"].isChecked())
        keep = self.ck["giu_nguyen"].isChecked()
        mix.boxes["shuffle_kq"].setChecked(self.ck["tron_kq"].isChecked() and not keep)
        mix.boxes["fix_ds_last"].setChecked(self.ck["co_dinh_pa4"].isChecked())
        mix.boxes["shuffle_ds"].setChecked(not self.ck["khong_tron_ds"].isChecked() and not keep)
        if keep:
            mix.boxes["shuffle_q"].setChecked(False)
            mix.boxes["shuffle_tn"].setChecked(False)
        o.cb_digits.setCurrentIndex(o.cb_digits.findData(3 if self.ck["ma_3so"].isChecked() else 4))
        o.sp_step.setValue(self.sp_cach.value() if self.ck["ma_cach"].isChecked() else 1)
        gp.e_ma.setText(self.e_ma.text() if self.ck["ma_tu_nhap"].isChecked() else "")
        sort = self.cc_sort.checked()
        id_sort = [s for s in sort if s in ("Theo lớp", "Theo môn", "Theo chương", "Theo bài", "Theo dạng")]
        mix.boxes["sort_by_level"].setChecked("Theo mức độ" in sort)
        mix.cb_order.setCurrentIndex(max(0, mix.cb_order.findData("matrix" if self.ck["theo_ma_tran"].isChecked()
                                                                 else "id" if id_sort else "")))
        gp.c_preview.setChecked(self.ck["doi_cau_goc"].isChecked())
        mix.e_ratio.setText(self.cb_ratio.currentText().strip())
        gp.e_truong.setText(self.e_truong.text())
        for k, e in (("GIAO_VIEN", self.e_gv), ("KY_THI", self.e_ky), ("MON_THI", self.e_mon)):
            gp.hdr[k].setText(e.text())
        if self.e_tg.text().strip().isdigit():
            gp.e_tg.setValue(int(self.e_tg.text()))
        if self.cb_header.currentData():
            gp.e_tpl[0].setText(self.cb_header.currentData())
        # cấu hình chỉ để lưu
        for k, c in self.sheet.items():
            self.st.setValue(f"mo/sheet_{k}", c.isChecked())
        for k in ("giu_nguyen", "hien_loi_giai", "dap_an_rieng"):
            self.st.setValue(f"mo/{k}", self.ck[k].isChecked())
        self.st.setValue("mo/sort", "|".join(sort))
        self.st.setValue("mo/file_name", self.e_file_name.text())
        self.st.setValue("mo/color", self.cb_color.currentText())
        self.st.setValue("mo/line", self.cb_line.currentText())

    # ---------------------------------------------------------------- nút
    def pick_region(self):
        mix = self.gp.opts.mix
        items = [mix.cb_region.itemText(i) for i in range(mix.cb_region.count())]
        cur = mix.cb_region.currentIndex()
        t, ok = QInputDialog.getItem(self, "Trộn đề theo vùng", "Trộn riêng từng vùng theo:", items, cur, False)
        if ok:
            mix.cb_region.setCurrentIndex(items.index(t))

    def clear_marks(self):
        pool = self.win.pool_bank()
        if pool is None:
            return
        if QMessageBox.question(self, "Xoá đánh dấu câu", "Đặt lại số lần «đã lấy ra đề» của mọi câu về 0?") \
                != QMessageBox.StandardButton.Yes:
            return
        pool.con.execute("UPDATE questions SET used_count=0")
        pool.con.commit()
        self.win.refresh()

    def save_matrix(self):
        name = self.e_matrix.text().strip()
        if not name:
            QMessageBox.information(self, "Lưu ma trận", "Nhập tên ma trận.")
            return
        gp = self.gp
        rules = gp.rules_dicts()
        if not rules:
            QMessageBox.information(self, "Lưu ma trận", "Ma trận chưa có dòng nào (lập ở tab Ma trận / «Nâng cao»).")
            return
        d = folder("ma_tran")
        os.makedirs(d, exist_ok=True)
        safe = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in name)
        p = os.path.join(d, safe + ".json")
        cfg = {"ten_de": gp.e_ten.text(), "truong": gp.e_truong.text(), "thoi_gian": gp.e_tg.value(), "rules": rules}
        if gp.codes():
            cfg["ma_de"] = gp.codes()
        with open(p, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Lưu ma trận", f"Đã lưu: {p}")

    def generate(self):
        """«Tạo đề» khi đang ở trang này: dùng trang nguồn đã dùng gần nhất (mặc định: Tạo đề theo ID)."""
        self.apply()
        inner = self.win.mix_tab.inner_tabs
        order = [self.win.idgrid_panel, self.win.pick_panel, self.win.filemix_panel, self.win.similar_panel]
        last = getattr(self.win, "_last_mix_page", None)
        target = last if last in order else order[0]
        inner.setCurrentWidget(target)
        target.generate()
