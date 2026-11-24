"""Các giao diện chuẩn hoá bố cục theo MyLT 2026 v1.0.3.44."""
from __future__ import annotations
import shutil
from pathlib import Path
import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QToolButton,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ..exporters.tikz2pic import Tikz2PicConfig, export_tikz_to_png
from ..exporters.blogger_form_exporter import export_blogger_form_html
from ..exporters.phieu_tltn_2025 import append_phieu_to_pdf, inject_phieu_into_tex
from ..exporters.pdfbuild import compile_tex_to_pdf, compile_tikz_snippet_to_pdf, open_pdf_file
from .pdf_preview import InlinePdfPreviewPanel


# ==============================================================================
# 1. TUỲ CHỌN ĐỀ (Chuẩn bố cục & đầy đủ chức năng MyLT 2026 v1.0.3.44)
# ==============================================================================
class TuyChonDePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.sort_order: list[str] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Nhóm 1: Tuỳ chọn chung
        g1 = QGroupBox("Tuỳ chọn chung")
        grid = QGridLayout(g1)

        self.cbo_so_de = QComboBox()
        self.cbo_so_de.addItems([str(i) for i in range(1, 25)])
        self.cbo_so_de.setCurrentText("4")
        self.cbo_kieu_goc = QComboBox()
        self.cbo_kieu_goc.addItems(["Một đề gốc", "Nhiều đề gốc", "Theo ma trận"])
        self.cbo_qr = QComboBox()
        self.cbo_qr.addItems(["", "QR TNMaker", "QR Chấm Thi", "QR Azota"])
        self.cbo_phieu = QComboBox()
        self.cbo_phieu.addItems(["", "Phiếu THPT QG 2025 (1 mặt)", "Phiếu THPT QG 2025 (2 trang)", "Azota 50A4", "TNMaker 60"])
        self.cbo_excel = QComboBox()
        self.cbo_excel.addItems(["", "Excel chuẩn BGD 2025", "Excel McMIX", "Excel Azota", "Excel SmartTest"])

        grid.addWidget(QLabel("Số đề tạo ra"), 0, 0); grid.addWidget(self.cbo_so_de, 0, 1)
        grid.addWidget(QLabel("Kiểu đề gốc"), 1, 0); grid.addWidget(self.cbo_kieu_goc, 1, 1)
        grid.addWidget(QLabel("Đáp án Qrcode"), 2, 0); grid.addWidget(self.cbo_qr, 2, 1)
        grid.addWidget(QLabel("Phiếu làm bài"), 3, 0); grid.addWidget(self.cbo_phieu, 3, 1)
        grid.addWidget(QLabel("Đáp án Excel"), 4, 0); grid.addWidget(self.cbo_excel, 4, 1)

        # Cột checkbox 1
        self.chk_an_da = QCheckBox("Ẩn đáp án")
        self.chk_hien_lg = QCheckBox("Hiện lời giải")
        self.chk_da_rieng = QCheckBox("Đáp án riêng")
        self.chk_da_cuoi = QCheckBox("Đáp án ở cuối")
        self.chk_file_rieng = QCheckBox("File đề riêng")
        for r, cb in enumerate([self.chk_an_da, self.chk_hien_lg, self.chk_da_rieng, self.chk_da_cuoi, self.chk_file_rieng]):
            grid.addWidget(cb, r, 2)

        # Cột checkbox 2
        self.chk_bien_dich = QCheckBox("Biên dịch đề"); self.chk_bien_dich.setChecked(True)
        self.chk_trang_trong = QCheckBox("Chèn trang trống")
        self.chk_tron_tln = QCheckBox("Trộn trả lời ngắn"); self.chk_tron_tln.setChecked(True)
        self.chk_codinh_ds = QCheckBox("Cố định PA4 câu ĐS")
        self.chk_khong_tron_ds = QCheckBox("Không trộn đúng sai")
        for r, cb in enumerate([self.chk_bien_dich, self.chk_trang_trong, self.chk_tron_tln, self.chk_codinh_ds, self.chk_khong_tron_ds]):
            grid.addWidget(cb, r, 3)

        # Cột 3 & 4
        self.chk_ma_cach = QCheckBox("Mã đề cách")
        self.spn_ma_cach = QSpinBox(); self.spn_ma_cach.setRange(1, 99); self.spn_ma_cach.setValue(1)
        self.chk_ma_3so = QCheckBox("Mã đề 3 số")
        self.btn_tron_vung = QPushButton("Trộn đề theo vùng")
        self.btn_tron_vung.clicked.connect(
            lambda: QMessageBox.information(self, "Trộn đề theo vùng", "Đánh dấu %[group:ten_vung] trong đề gốc để khóa trộn theo từng vùng.")
        )
        r_ma = QHBoxLayout()
        r_ma.addWidget(self.chk_ma_cach); r_ma.addWidget(self.spn_ma_cach)
        r_ma.addWidget(self.chk_ma_3so); r_ma.addWidget(self.btn_tron_vung)
        grid.addLayout(r_ma, 0, 4, 1, 2)

        self.chk_ma_tu_nhap = QCheckBox("Mã đề tự nhập")
        self.ed_ma_tu_nhap = QLineEdit(); self.ed_ma_tu_nhap.setPlaceholderText("VD: 101, 102, 103, 104")
        b_help_ma = QPushButton("?"); b_help_ma.setFixedWidth(26)
        b_help_ma.clicked.connect(lambda: QMessageBox.information(self, "Mã đề tự nhập", "Nhập danh sách mã đề cách nhau bởi dấu phẩy. VD: 101, 102, 103, 104"))
        r_mtn = QHBoxLayout(); r_mtn.addWidget(self.ed_ma_tu_nhap, 1); r_mtn.addWidget(b_help_ma)
        grid.addWidget(self.chk_ma_tu_nhap, 1, 4); grid.addLayout(r_mtn, 1, 5)

        # Sắp xếp câu hỏi: Dropdown chọn nhiều 6 tiêu chí đúng như MyLT 2026
        self.btn_sort_menu = QToolButton()
        self.btn_sort_menu.setText("Chọn mục theo thứ tự cần sắp xếp")
        self.btn_sort_menu.setPopupMode(QToolButton.InstantPopup)
        self.btn_sort_menu.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_sort_menu.setMinimumWidth(220)
        self.sort_menu = QMenu(self.btn_sort_menu)
        self.sort_actions: dict[str, QAction] = {}
        for label in ["Theo lớp", "Theo môn", "Theo chương", "Theo mức độ", "Theo bài", "Theo dạng"]:
            act = QAction(label, self.sort_menu)
            act.setCheckable(True)
            act.toggled.connect(lambda checked, lb=label: self._on_sort_toggled(lb, checked))
            self.sort_menu.addAction(act)
            self.sort_actions[label] = act
        self.btn_sort_menu.setMenu(self.sort_menu)
        grid.addWidget(QLabel("Sắp xếp câu hỏi"), 2, 4); grid.addWidget(self.btn_sort_menu, 2, 5)

        self.chk_xep_matran = QCheckBox("Xếp theo ma trận")
        self.chk_doi_cau_goc = QCheckBox("Đổi câu gốc")
        self.btn_xoa_danh_dau = QPushButton("Xoá đánh dấu câu")
        self.btn_xoa_danh_dau.clicked.connect(
            lambda: QMessageBox.information(self, "Xoá đánh dấu câu", "Đã làm mới trạng thái đánh dấu câu đã dùng cho phiên trộn hiện tại.")
        )
        r_xm = QHBoxLayout()
        r_xm.addWidget(self.chk_xep_matran); r_xm.addWidget(self.chk_doi_cau_goc); r_xm.addWidget(self.btn_xoa_danh_dau)
        grid.addLayout(r_xm, 3, 4, 1, 2)

        self.chk_giu_nguyen = QCheckBox("Giữ nguyên đề")
        self.cbo_tile_da = QComboBox(); self.cbo_tile_da.addItems(["Cân bằng A/B/C/D", "Ngẫu nhiên", "Tự chọn"])
        r_gn = QHBoxLayout()
        r_gn.addWidget(self.chk_giu_nguyen); r_gn.addWidget(QLabel("Tỉ lệ đáp án TN")); r_gn.addWidget(self.cbo_tile_da)
        grid.addLayout(r_gn, 4, 4, 1, 2)
        root.addWidget(g1)

        # Nhóm 2: Tuỳ chọn phiếu Zipgrade - TNMaker - Chấm Thi - QR Code - Azota - UnT
        g2 = QGroupBox("Tuỳ chọn phiếu Zipgrade - TNMaker - Chấm Thi - QR Code - Azota - UnT")
        g2l = QGridLayout(g2)
        labels_row0 = ["Trang riêng", "Chèn ABCD", "Chỉ đáp án", "Ghi chú", "Azota 50A5", "Chấm Thi 50A5"]
        labels_row1 = ["Lên trên", "Phiếu ngang", "SBD 5 số", "HS lớp", "TNMaker 60", "Màu toàn phiếu"]
        self.phieu_checks: dict[str, QCheckBox] = {}
        for c, lb in enumerate(labels_row0):
            cb = QCheckBox(lb)
            if lb in ("Chèn ABCD", "Ghi chú"):
                cb.setChecked(True)
            self.phieu_checks[lb] = cb
            g2l.addWidget(cb, 0, c)
        for c, lb in enumerate(labels_row1):
            cb = QCheckBox(lb)
            if lb == "HS lớp":
                cb.setChecked(True)
            self.phieu_checks[lb] = cb
            g2l.addWidget(cb, 1, c)
        self.cbo_mau_ve = QComboBox(); self.cbo_mau_ve.addItems(["", "Đen", "Xanh dương", "Xanh lá"])
        self.cbo_net_ve = QComboBox(); self.cbo_net_ve.addItems(["", "Mảnh", "Trung bình", "Đậm"])
        self.chk_tieu_de_phieu = QCheckBox("Tiêu đề")
        b_hd_phieu = QPushButton("Hướng dẫn")
        b_hd_phieu.clicked.connect(
            lambda: QMessageBox.information(self, "Hướng dẫn phiếu chấm", "Chọn kiểu phiếu ở mục 'Phiếu làm bài' (VD: Phiếu THPT QG 2025) và các tuỳ chọn hiển thị tương ứng.")
        )
        g2l.addWidget(QLabel("Màu vẽ"), 0, 6); g2l.addWidget(self.cbo_mau_ve, 0, 7); g2l.addWidget(self.chk_tieu_de_phieu, 0, 8)
        g2l.addWidget(QLabel("Nét vẽ"), 1, 6); g2l.addWidget(self.cbo_net_ve, 1, 7); g2l.addWidget(b_hd_phieu, 1, 8)
        root.addWidget(g2)

        # Nhóm 3: Cài đặt tiêu đề
        g3 = QGroupBox("Cài đặt tiêu đề")
        g3l = QGridLayout(g3)
        self.ed_truong = QLineEdit("Trường THPT ...")
        self.ed_gv = QLineEdit("Tổ Toán")
        self.cbo_header = QComboBox(); self.cbo_header.addItems(["Header.tex (Mặc định)", "de_thi_mylt.tex", "de_thi.tex"])
        b_help_hdr = QPushButton("?"); b_help_hdr.setFixedWidth(26)
        b_help_hdr.clicked.connect(lambda: QMessageBox.information(self, "File header", "Chọn mẫu tệp tiêu đề .tex dùng khi xuất bộ đề thi."))
        r_hdr = QHBoxLayout(); r_hdr.addWidget(self.cbo_header, 1); r_hdr.addWidget(b_help_hdr)
        self.ed_ky_thi = QLineEdit("Kiểm tra định kỳ, năm học 2026 - 2027")
        self.ed_mon = QLineEdit("Môn: Toán, lớp 12")
        self.ed_thoi_gian = QLineEdit("45")
        g3l.addWidget(QLabel("Tên trường"), 0, 0); g3l.addWidget(self.ed_truong, 0, 1)
        g3l.addWidget(QLabel("Tên kỳ thi"), 0, 2); g3l.addWidget(self.ed_ky_thi, 0, 3)
        g3l.addWidget(QLabel("Tên giáo viên"), 1, 0); g3l.addWidget(self.ed_gv, 1, 1)
        g3l.addWidget(QLabel("Tên môn thi"), 1, 2); g3l.addWidget(self.ed_mon, 1, 3)
        g3l.addWidget(QLabel("File header"), 2, 0); g3l.addLayout(r_hdr, 2, 1)
        g3l.addWidget(QLabel("Thời gian"), 2, 2); g3l.addWidget(self.ed_thoi_gian, 2, 3)
        root.addWidget(g3)

        # Nhóm 4: Tên file đề tạo ra & Lưu ma trận
        row4 = QHBoxLayout()
        g4a = QGroupBox("Tên file đề tạo ra")
        l4a = QHBoxLayout(g4a); self.ed_ten_file = QLineEdit("De_Kiem_Tra_Toan"); l4a.addWidget(self.ed_ten_file)
        g4b = QGroupBox("Lưu ma trận")
        l4b = QHBoxLayout(g4b); self.ed_ten_mt = QLineEdit(); self.btn_luu_mt = QPushButton("Lưu")
        l4b.addWidget(QLabel("Tên")); l4b.addWidget(self.ed_ten_mt, 1); l4b.addWidget(self.btn_luu_mt)
        row4.addWidget(g4a, 1); row4.addWidget(g4b, 1)
        root.addLayout(row4)
        root.addStretch()

    def _on_sort_toggled(self, label: str, checked: bool):
        if checked and label not in self.sort_order:
            self.sort_order.append(label)
        elif not checked and label in self.sort_order:
            self.sort_order.remove(label)
        self.btn_sort_menu.setText(" → ".join(self.sort_order) if self.sort_order else "Chọn mục theo thứ tự cần sắp xếp")

    def get_options(self) -> dict:
        return {
            "num_exams": int(self.cbo_so_de.currentText() or "4"),
            "code_digits": 3 if self.chk_ma_3so.isChecked() else 4,
            "code_step": self.spn_ma_cach.value() if self.chk_ma_cach.isChecked() else 1,
            "custom_codes": [c.strip() for c in self.ed_ma_tu_nhap.text().split(",") if c.strip()] if self.chk_ma_tu_nhap.isChecked() else [],
            "balance_abcd": self.cbo_tile_da.currentIndex() == 0,
            "sort_order": list(self.sort_order),
            "sort_by_level": "Theo mức độ" in self.sort_order,
            "embed_qr": bool(self.cbo_qr.currentText().strip()),
            "phieu_mode": self.cbo_phieu.currentText().strip(),
            "compile_pdf": self.chk_bien_dich.isChecked(),
            "insert_blank_page": self.chk_trang_trong.isChecked(),
            "title": self.ed_ky_thi.text().strip() or "ĐỀ KIỂM TRA ĐỊNH KÌ TOÁN",
            "school": self.ed_truong.text().strip(),
            "teacher": self.ed_gv.text().strip(),
            "subject": self.ed_mon.text().strip(),
            "duration": self.ed_thoi_gian.text().strip() or "45",
        }


# ==============================================================================
# 2. TIỆN ÍCH 1 (Đầy đủ 10 cụm chức năng + Nút Chuyển / Tạo / Lọc / HDSD chuẩn MyLT 2026)
# ==============================================================================
class TienIch1Panel(QWidget):
    def __init__(self, main_window=None, parent=None):
        super().__init__(parent)
        self.mw = main_window
        self._build_ui()

    def _help(self, title: str, body: str):
        QMessageBox.information(self, f"HDSD — {title}", body)

    def _pick_into(self, target: QLineEdit | QComboBox, title: str, flt: str, append: bool = False):
        from ..paths import app_root_dir
        paths, _ = QFileDialog.getOpenFileNames(self, title, str(app_root_dir()), flt)
        if not paths:
            return
        if isinstance(target, QComboBox):
            if not append:
                target.clear()
            for p in paths:
                target.addItem(p)
            target.setCurrentText(paths[0])
        else:
            if append and target.text().strip():
                target.setText(target.text().strip() + ";" + ";".join(paths))
            else:
                target.setText(";".join(paths))

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(6)

        # 1. Lọc câu hỏi
        g1 = QGroupBox("Lọc câu hỏi. Chọn lọc từ ngân hàng câu hỏi hoặc từ files")
        g1v = QVBoxLayout(g1)
        r1a = QHBoxLayout()
        self.cbo_loc_file = QComboBox(); self.cbo_loc_file.setEditable(True)
        b1_chon = QPushButton("Chọn"); b1_chon.clicked.connect(lambda: self._pick_into(self.cbo_loc_file, "Chọn file .tex", "LaTeX (*.tex)"))
        b1_them = QPushButton("Thêm"); b1_them.clicked.connect(lambda: self._pick_into(self.cbo_loc_file, "Thêm file .tex", "LaTeX (*.tex)", append=True))
        b1_loc = QPushButton("Lọc"); b1_loc.clicked.connect(self._do_loc_cau_hoi)
        for w in (QLabel("File"), self.cbo_loc_file, b1_chon, b1_them, b1_loc):
            r1a.addWidget(w, 1 if w is self.cbo_loc_file else 0)
        r1b = QHBoxLayout()
        self.ed_loc_kw = QLineEdit(); self.ed_loc_kw.setPlaceholderText("Nhập ID (VD: 2D1N1-1) hoặc từ khoá...")
        b1_hd = QPushButton("HDSD"); b1_hd.clicked.connect(lambda: self._help("Lọc câu hỏi", "Chọn 'Từ ngân hàng' hoặc 'Từ Files', nhập mã ID6 (VD: 2D1*) hoặc từ khoá rồi bấm 'Lọc'."))
        b1_opt = QPushButton("Tuỳ chọn"); b1_opt.clicked.connect(lambda: self._help("Tuỳ chọn lọc", "Hỗ trợ lọc theo mã ID6 (không phân biệt hoa thường) hoặc chuỗi con trong nội dung câu hỏi."))
        self.rb_loc_files = QRadioButton("Từ Files")
        self.rb_loc_bank = QRadioButton("Từ ngân hàng"); self.rb_loc_bank.setChecked(True)
        r1b.addWidget(QLabel("ID hoặc từ khoá")); r1b.addWidget(self.ed_loc_kw, 1); r1b.addWidget(b1_hd)
        r1b.addWidget(b1_opt); r1b.addWidget(self.rb_loc_files); r1b.addWidget(self.rb_loc_bank)
        g1v.addLayout(r1a); g1v.addLayout(r1b)
        root.addWidget(g1)

        # 2. Lọc hình vẽ TikZ
        g2 = QGroupBox("Lọc hình vẽ Tikz. Chọn chế độ từ ngân hàng câu hỏi hoặc từ files")
        g2v = QVBoxLayout(g2)
        r2a = QHBoxLayout()
        self.cbo_tikz_file = QComboBox(); self.cbo_tikz_file.setEditable(True)
        b2_chon = QPushButton("Chọn"); b2_chon.clicked.connect(lambda: self._pick_into(self.cbo_tikz_file, "Chọn file .tex", "LaTeX (*.tex)"))
        b2_them = QPushButton("Thêm"); b2_them.clicked.connect(lambda: self._pick_into(self.cbo_tikz_file, "Thêm file .tex", "LaTeX (*.tex)", append=True))
        b2_loc = QPushButton("Lọc"); b2_loc.clicked.connect(self._do_loc_tikz)
        for w in (QLabel("File"), self.cbo_tikz_file, b2_chon, b2_them, b2_loc):
            r2a.addWidget(w, 1 if w is self.cbo_tikz_file else 0)
        r2b = QHBoxLayout()
        self.ed_tikz_kw = QLineEdit(); self.ed_tikz_kw.setPlaceholderText("Từ khoá hình vẽ (để trống để lọc tất cả)...")
        b2_hd = QPushButton("HDSD"); b2_hd.clicked.connect(lambda: self._help("Lọc hình vẽ TikZ", "Trích xuất toàn bộ khối \\begin{tikzpicture}...\\end{tikzpicture} từ file .tex sang tệp tổng hợp và biên dịch PDF nếu tick 'Biên dịch'."))
        self.chk_tikz_comp = QCheckBox("Biên dịch"); self.chk_tikz_comp.setChecked(True)
        self.rb_tikz_files = QRadioButton("Từ Files"); self.rb_tikz_files.setChecked(True)
        self.rb_tikz_bank = QRadioButton("Từ ngân hàng")
        r2b.addWidget(QLabel("Lọc theo từ khoá")); r2b.addWidget(self.ed_tikz_kw, 1); r2b.addWidget(b2_hd)
        r2b.addWidget(self.chk_tikz_comp); r2b.addWidget(self.rb_tikz_files); r2b.addWidget(self.rb_tikz_bank)
        g2v.addLayout(r2a); g2v.addLayout(r2b)
        root.addWidget(g2)

        # 3. Tô phiếu Zipgrade, TNMaker, Chấm Thi, Excel
        g3 = QGroupBox("Tô phiếu Zipgrade, TNMaker, Chấm Thi, Excel, Phiếu TLTN 2025")
        g3v = QVBoxLayout(g3)
        r3a = QHBoxLayout()
        self.rb_phieu_tex = QRadioButton("Theo đề TeX"); self.rb_phieu_tex.setChecked(True)
        self.cbo_phieu_file = QComboBox(); self.cbo_phieu_file.setEditable(True)
        b3_chon = QPushButton("Chọn"); b3_chon.clicked.connect(lambda: self._pick_into(self.cbo_phieu_file, "Chọn file .tex/.pdf", "TeX/PDF (*.tex *.pdf)"))
        self.chk_to_da = QCheckBox("Tô đáp án"); self.chk_to_da.setChecked(True)
        self.cbo_kieu_phieu = QComboBox(); self.cbo_kieu_phieu.addItems(["Phiếu TLTN 2025 (1 mặt)", "Phiếu TLTN 2025 (2 trang)", "Zipgrade", "TNMaker", "Excel BGD"])
        b3_tao = QPushButton("Tạo"); b3_tao.clicked.connect(self._do_ghep_phieu)
        for w in (self.rb_phieu_tex, self.cbo_phieu_file, b3_chon, self.chk_to_da, QLabel("Kiểu phiếu"), self.cbo_kieu_phieu, b3_tao):
            r3a.addWidget(w, 1 if w is self.cbo_phieu_file else 0)
        r3b = QHBoxLayout()
        self.rb_phieu_str = QRadioButton("Theo chuỗi đáp án")
        self.ed_phieu_str = QLineEdit(); self.ed_phieu_str.setPlaceholderText("VD: ABCDACBD...")
        b3_dan = QPushButton("Dán"); b3_dan.clicked.connect(lambda: self.ed_phieu_str.setText(QApplication.clipboard().text()))
        self.chk_tao_phieu = QCheckBox("Tạo phiếu")
        self.ed_ma_de = QLineEdit("101"); self.ed_ma_de.setMaximumWidth(70)
        b3_hd = QPushButton("HDSD"); b3_hd.clicked.connect(
            lambda: self._help(
                "Tô phiếu Zipgrade, TNMaker, Chấm Thi, Excel",
                "- Khi không xuất đáp án Excel, để tạo thêm phiếu làm bài thì tick chọn 'Tạo phiếu'.\n"
                "- Tuỳ chọn phiếu dùng tại tab 'Trộn đề' > 'Tuỳ chọn đề' > 'Tuỳ chọn phiếu'.\n"
                "- Khi tạo 'Từ file TeX', có thể chọn file có nhiều đề hay nhiều file cùng lúc. Khi đó, cần nhập đủ số mã đề tương ứng. Phần mềm sẽ tự nhận và tạo phiếu đáp án tương ứng.\n"
                "  Ví dụ: Trong 1 file TeX có 4 đề thì nhập 4 mã đề.\n"
                "  Nếu nhiều file TeX cùng lúc thì nhập mã đề của từng file. Mã đề các file cách nhau bằng dấu ';'. Ví dụ: File 1 có 2 mã đề 101,102. File 2 có 3 mã đề 101,102,103 thì nhập 101,102;101,102,103.\n"
                "- Khi tạo 'Từ chuỗi đáp án', có thể nhập đáp án nhiều đề cùng lúc. Đáp án các đề cách nhau bằng dấu @, đáp án các phần cách nhau bằng dấu #. Đáp án các câu đúng sai cách nhau bằng dấu phẩy, đáp án các câu trả lời ngắn cách nhau bằng dấu chấm phẩy.\n"
                "  Ví dụ: ADCB#ĐSĐĐ,SSSS#1;2;6@CCCB#SĐĐĐ,ĐSSS#2;4,9;7",
            )
        )
        for w in (self.rb_phieu_str, self.ed_phieu_str, b3_dan, self.chk_tao_phieu, QLabel("Mã đề"), self.ed_ma_de, b3_hd):
            r3b.addWidget(w, 1 if w is self.ed_phieu_str else 0)
        g3v.addLayout(r3a); g3v.addLayout(r3b)
        root.addWidget(g3)

        # Hàng 4: Word/PDF -> TeX (trái) | TeX -> Word (phải)
        row4 = QHBoxLayout()
        g4a = QGroupBox("Chuyển đổi file Word/PDF sang TeX. Chọn một hoặc nhiều tập tin Word/PDF")
        v4a = QVBoxLayout(g4a)
        r4a1 = QHBoxLayout()
        self.cbo_w2t = QComboBox(); self.cbo_w2t.setEditable(True)
        b4a_opt = QPushButton("Tuỳ chọn"); b4a_opt.clicked.connect(self._open_w2t_options)
        b4a_chon = QPushButton("Chọn"); b4a_chon.clicked.connect(lambda: self._pick_into(self.cbo_w2t, "Chọn file Word/PDF/Ảnh", "Word/PDF/Ảnh (*.docx *.pdf *.png *.jpg)"))
        b4a_run = QPushButton("Chuyển"); b4a_run.clicked.connect(self._do_word_pdf_to_tex)
        for w in (QLabel("File"), self.cbo_w2t, b4a_opt, b4a_chon, b4a_run):
            r4a1.addWidget(w, 1 if w is self.cbo_w2t else 0)
        r4a2 = QHBoxLayout()
        b4a_hd = QPushButton("HDSD"); b4a_hd.clicked.connect(lambda: self._help("Word/PDF sang TeX", "Chọn tệp .docx hoặc .pdf rồi bấm 'Chuyển'. Với PDF scan/ảnh, nhập Gemini API Key tại tab 'Phiếu 2025 · Tikz2Pic · Blogger · Config'."))
        b4a_manual = QPushButton("Chuyển PDF/ảnh thủ công"); b4a_manual.clicked.connect(lambda: self._call_mw("_run_ocr"))
        r4a2.addStretch(); r4a2.addWidget(b4a_hd); r4a2.addWidget(b4a_manual)
        v4a.addLayout(r4a1); v4a.addLayout(r4a2)

        g4b = QGroupBox("Chuyển đổi file TeX sang Word. Chọn một hoặc nhiều tập tin TeX")
        v4b = QVBoxLayout(g4b)
        r4b1 = QHBoxLayout()
        self.cbo_t2w = QComboBox(); self.cbo_t2w.setEditable(True)
        b4b_hd = QPushButton("HDSD"); b4b_hd.clicked.connect(lambda: self._help("TeX sang Word", "Chọn tệp .tex chuẩn ex_test rồi bấm 'Chuyển' để xuất sang tệp Word (.docx) giữ nguyên công thức Toán."))
        b4b_chon = QPushButton("Chọn"); b4b_chon.clicked.connect(lambda: self._pick_into(self.cbo_t2w, "Chọn file .tex", "LaTeX (*.tex)"))
        b4b_run = QPushButton("Chuyển"); b4b_run.clicked.connect(self._do_tex_to_word)
        for w in (QLabel("File"), self.cbo_t2w, b4b_hd, b4b_chon, b4b_run):
            r4b1.addWidget(w, 1 if w is self.cbo_t2w else 0)
        r4b2 = QHBoxLayout()
        b4b_opt = QPushButton("Tuỳ chọn"); b4b_opt.clicked.connect(lambda: self._help("Tuỳ chọn TeX -> Word", "Tự động xuất công thức toán sang chuẩn OMML/MathType và giữ định dạng câu hỏi trắc nghiệm."))
        r4b2.addStretch(); r4b2.addWidget(b4b_opt)
        v4b.addLayout(r4b1); v4b.addLayout(r4b2)
        row4.addWidget(g4a, 1); row4.addWidget(g4b, 1)
        root.addLayout(row4)

        # Hàng 5: Tạo đề trắc nghiệm online (trái) | Tìm câu hỏi trùng (phải)
        row5 = QHBoxLayout()
        g5a = QGroupBox("Tạo đề trắc nghiệm online")
        v5a = QVBoxLayout(g5a)
        r5a1 = QHBoxLayout()
        self.ed_online_file = QLineEdit()
        b5a_hd = QPushButton("HDSD"); b5a_hd.clicked.connect(lambda: self._help("Đề trắc nghiệm online", "Xuất đề từ ngân hàng hoặc file .tex sang Moodle XML, Aiken, Quizizz hoặc Microsoft/Google Forms."))
        b5a_chon = QPushButton("Chọn"); b5a_chon.clicked.connect(lambda: self._pick_into(self.ed_online_file, "Chọn file .tex", "LaTeX (*.tex)"))
        b5a_moodle = QPushButton("Moodle"); b5a_moodle.clicked.connect(self._do_export_moodle)
        for w in (QLabel("File"), self.ed_online_file, b5a_hd, b5a_chon, b5a_moodle):
            r5a1.addWidget(w, 1 if w is self.ed_online_file else 0)
        r5a2 = QHBoxLayout()
        b5a_opt = QPushButton("Tuỳ chọn"); b5a_opt.clicked.connect(lambda: self._help("Tuỳ chọn đề online", "Mặc định xuất kèm đáp án đúng và lời giải chi tiết."))
        b5a_aiken = QPushButton("Aiken"); b5a_aiken.clicked.connect(self._do_export_aiken)
        b5a_quiz = QPushButton("Quizizz"); b5a_quiz.clicked.connect(self._do_export_online_gas)
        b5a_ms = QPushButton("Microsoft Forms"); b5a_ms.clicked.connect(self._do_export_online_gas)
        for w in (b5a_opt, b5a_aiken, b5a_quiz, b5a_ms):
            r5a2.addWidget(w)
        v5a.addLayout(r5a1); v5a.addLayout(r5a2)

        g5b = QGroupBox("Tìm câu hỏi trùng. Chọn chế độ từ ngân hàng câu hỏi hoặc từ files")
        v5b = QVBoxLayout(g5b)
        r5b1 = QHBoxLayout()
        self.cbo_dup_file = QComboBox(); self.cbo_dup_file.setEditable(True)
        b5b_chon = QPushButton("Chọn"); b5b_chon.clicked.connect(lambda: self._pick_into(self.cbo_dup_file, "Chọn file .tex", "LaTeX (*.tex)"))
        b5b_them = QPushButton("Thêm"); b5b_them.clicked.connect(lambda: self._pick_into(self.cbo_dup_file, "Thêm file .tex", "LaTeX (*.tex)", append=True))
        b5b_tim = QPushButton("Tìm"); b5b_tim.clicked.connect(self._do_find_duplicates)
        for w in (QLabel("File"), self.cbo_dup_file, b5b_chon, b5b_them, b5b_tim):
            r5b1.addWidget(w, 1 if w is self.cbo_dup_file else 0)
        r5b2 = QHBoxLayout()
        self.cbo_dup_rate = QComboBox(); self.cbo_dup_rate.addItems(["70%", "75%", "80%", "85%", "90%", "95%", "100%"]); self.cbo_dup_rate.setCurrentText("85%")
        self.cbo_dup_scope = QComboBox(); self.cbo_dup_scope.setEditable(True); self.cbo_dup_scope.setMinimumWidth(80)
        self.cbo_dup_scope.addItems(["", "0", "1", "2", "0D", "0H", "1D", "1H", "2D", "2H"])
        self.cbo_dup_scope.setToolTip("Nhập tiền tố mã ID để giới hạn phạm vi tìm trùng (VD: 2D1, 1H3). Để trống = toàn bộ.")
        self.rb_dup_fb = QRadioButton("File > Bank")
        self.rb_dup_files = QRadioButton("Từ Files")
        self.rb_dup_bank = QRadioButton("Từ ngân hàng"); self.rb_dup_bank.setChecked(True)
        for w in (QLabel("Tỉ lệ"), self.cbo_dup_rate, QLabel("Phạm vi"), self.cbo_dup_scope, self.rb_dup_fb, self.rb_dup_files, self.rb_dup_bank):
            r5b2.addWidget(w)
        v5b.addLayout(r5b1); v5b.addLayout(r5b2)
        row5.addWidget(g5a, 1); row5.addWidget(g5b, 1)
        root.addLayout(row5)

        # Hàng 6: Tạo đề trắc nghiệm offline dạng PDF (trái) | Hoá ảnh đề TeX (phải)
        row6 = QHBoxLayout()
        g6a = QGroupBox("Tạo đề trắc nghiệm offline dạng PDF")
        r6a = QHBoxLayout(g6a)
        self.ed_pdf_tex = QLineEdit(); self.ed_pdf_tex.setPlaceholderText("Chọn tệp .tex để biên dịch PDF...")
        b6a_opt = QPushButton("Tuỳ chọn"); b6a_opt.clicked.connect(lambda: self._help("Biên dịch PDF", "Tự động biên dịch tệp .tex bằng pdflatex (tương thích TeX Live 2019/MiKTeX) và mở ngay tệp PDF."))
        b6a_chon = QPushButton("Chọn"); b6a_chon.clicked.connect(lambda: self._pick_into(self.ed_pdf_tex, "Chọn tệp .tex", "LaTeX (*.tex)"))
        b6a_tao = QPushButton("Tạo"); b6a_tao.clicked.connect(self._do_compile_pdf)
        for w in (QLabel("File"), self.ed_pdf_tex, b6a_opt, b6a_chon, b6a_tao):
            r6a.addWidget(w, 1 if w is self.ed_pdf_tex else 0)

        g6b = QGroupBox("Hoá ảnh đề TeX")
        r6b = QHBoxLayout(g6b)
        self.ed_img_tex = QLineEdit(); self.ed_img_tex.setPlaceholderText("Chọn tệp .tex chứa hình TikZ...")
        b6b_t2i = QPushButton("Tikz2Img"); b6b_t2i.clicked.connect(self._do_tikz2img)
        b6b_opt = QPushButton("Tuỳ chọn"); b6b_opt.clicked.connect(lambda: self._help("Hoá ảnh đề TeX", "Biên dịch tự động từng hình TikZ trong đề sang ảnh PNG sắc nét (300 DPI) để chèn Word/Web."))
        b6b_chon = QPushButton("Chọn"); b6b_chon.clicked.connect(lambda: self._pick_into(self.ed_img_tex, "Chọn tệp .tex", "LaTeX (*.tex)"))
        b6b_run = QPushButton("Chuyển"); b6b_run.clicked.connect(self._do_tikz2img)
        for w in (QLabel("File"), self.ed_img_tex, b6b_t2i, b6b_opt, b6b_chon, b6b_run):
            r6b.addWidget(w, 1 if w is self.ed_img_tex else 0)
        row6.addWidget(g6a, 1); row6.addWidget(g6b, 1)
        root.addLayout(row6)

        # Hàng 7: Blogger (trái) | Chuyển ex_test cũ sang mới / dethi sang ex_test (phải)
        row7 = QHBoxLayout()
        g7a = QGroupBox("Tạo đề trắc nghiệm online trên Blogger")
        r7a = QHBoxLayout(g7a)
        b7a_po = QPushButton("Phiếu Online"); b7a_po.clicked.connect(self._do_blogger)
        b7a_tex = QPushButton("Từ TeX"); b7a_tex.clicked.connect(self._do_blogger)
        b7a_img = QPushButton("Từ link ảnh"); b7a_img.clicked.connect(lambda: self._help("Blogger từ link ảnh", "Xuất trang HTML tương tác Blogger có nhúng phiếu chấm điểm tự động và link ảnh câu hỏi."))
        r7a.addStretch(); r7a.addWidget(b7a_po); r7a.addWidget(b7a_tex); r7a.addWidget(b7a_img)

        g7b = QGroupBox("Chuyển đổi cấu trúc gói đề")
        v7b = QVBoxLayout(g7b)
        r7b1 = QHBoxLayout()
        self.rb_extest = QRadioButton("Chuyển ex_test cũ sang mới"); self.rb_extest.setChecked(True)
        self.rb_dethi = QRadioButton("Chuyển dethi sang ex_test")
        r7b1.addWidget(self.rb_extest); r7b1.addWidget(self.rb_dethi); r7b1.addStretch()
        r7b2 = QHBoxLayout()
        self.cbo_conv_file = QComboBox(); self.cbo_conv_file.setEditable(True)
        b7b_chon = QPushButton("Chọn"); b7b_chon.clicked.connect(lambda: self._pick_into(self.cbo_conv_file, "Chọn tệp .tex", "LaTeX (*.tex)"))
        b7b_run = QPushButton("Chuyển"); b7b_run.clicked.connect(self._do_convert_pkg)
        for w in (QLabel("File"), self.cbo_conv_file, b7b_chon, b7b_run):
            r7b2.addWidget(w, 1 if w is self.cbo_conv_file else 0)
        v7b.addLayout(r7b1); v7b.addLayout(r7b2)
        row7.addWidget(g7a, 1); row7.addWidget(g7b, 1)
        root.addLayout(row7)

        root.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def _call_mw(self, method_name: str):
        if self.mw is not None and hasattr(self.mw, method_name):
            getattr(self.mw, method_name)()
        else:
            QMessageBox.information(self, "Thông báo", f"Chức năng {method_name} sẵn sàng.")

    def _do_loc_cau_hoi(self):
        kw = self.ed_loc_kw.text().strip()
        if self.rb_loc_bank.isChecked() and self.mw is not None and hasattr(self.mw, "cau_hoi_mylt"):
            self.mw.tabs.setCurrentIndex(1)
            self.mw.cau_hoi_mylt.rb_bank.setChecked(True)
            self.mw.cau_hoi_mylt._load_questions()
            self.mw.cau_hoi_mylt._apply_filter(keyword=kw)
            return
        p = self.cbo_loc_file.currentText().strip()
        if not p or not Path(p).exists():
            QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex cần lọc trước.")
            return
        if self.mw is not None and hasattr(self.mw, "cau_hoi_mylt"):
            self.mw.tabs.setCurrentIndex(1)
            self.mw.cau_hoi_mylt.rb_files.setChecked(True)
            self.mw.cau_hoi_mylt.source_files = [Path(p)]
            self.mw.cau_hoi_mylt._sync_files_combo()
            self.mw.cau_hoi_mylt._load_questions()
            self.mw.cau_hoi_mylt._apply_filter(keyword=kw)

    def _do_loc_tikz(self):
        p = self.cbo_tikz_file.currentText().strip()
        if not p or not Path(p).exists():
            QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex chứa hình TikZ.")
            return
        txt = Path(p).read_text(encoding="utf-8", errors="replace")
        kw = self.ed_tikz_kw.text().strip().lower()
        blocks = re.findall(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", txt, flags=re.DOTALL)
        if kw:
            blocks = [b for b in blocks if kw in b.lower()]
        if not blocks:
            QMessageBox.information(self, "Lọc TikZ", "Không tìm thấy hình TikZ phù hợp.")
            return
        out = Path(p).with_name(f"{Path(p).stem}_tikz_only.tex")
        doc = "\\documentclass[12pt,a4paper]{article}\n\\usepackage[utf8]{vietnam}\n\\usepackage{tikz,tkz-tab,pgfplots}\n\\begin{document}\n" + "\n\n\\medskip\n\n".join(blocks) + "\n\\end{document}\n"
        out.write_text(doc, encoding="utf-8")
        if self.chk_tikz_comp.isChecked():
            res = compile_tex_to_pdf(str(out), compiler="pdflatex", passes=1)
            if res.success and res.pdf_path:
                open_pdf_file(res.pdf_path)
        QMessageBox.information(self, "Lọc TikZ thành công", f"Đã trích xuất {len(blocks)} hình TikZ vào:\n{out}")

    def _do_ghep_phieu(self):
        if self.rb_phieu_str.isChecked():
            raw_str = self.ed_phieu_str.text().strip()
            if not raw_str:
                QMessageBox.warning(self, "Thiếu chuỗi đáp án", "Hãy nhập hoặc dán chuỗi đáp án (VD: ADCB#ĐSĐĐ,SSSS#1;2;6@CCCB#SĐĐĐ,ĐSSS#2;4,9;7).")
                return
            codes = [c.strip() for c in re.split(r"[,;]+", self.ed_ma_de.text().strip()) if c.strip()]
            exam_blocks = [b.strip() for b in raw_str.split("@") if b.strip()]
            out_csv, _ = QFileDialog.getSaveFileName(self, "Lưu bảng đáp án từ chuỗi", "dap_an_to_phieu.csv", "CSV (*.csv)")
            if not out_csv:
                return
            import csv
            with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
                w = csv.writer(f)
                w.writerow(["Ma_De", "Phan_I_TN", "Phan_II_DS", "Phan_III_TLN"])
                for idx, blk in enumerate(exam_blocks):
                    code = codes[idx] if idx < len(codes) else str(101 + idx)
                    parts = [pt.strip() for pt in blk.split("#")]
                    p1 = parts[0] if len(parts) > 0 else ""
                    p2 = parts[1] if len(parts) > 1 else ""
                    p3 = parts[2] if len(parts) > 2 else ""
                    w.writerow([code, p1, p2, p3])
            QMessageBox.information(
                self,
                "Tạo đáp án từ chuỗi thành công",
                f"Đã xử lý {len(exam_blocks)} mã đề theo chuẩn @ / # / , / ; và xuất tệp:\n{out_csv}",
            )
            return

        p = self.cbo_phieu_file.currentText().strip()
        if not p or not Path(p).exists():
            QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp đề .tex trước khi bấm Tạo.")
            return
        from ..exporters.phieu_tltn_2025 import inject_phieu_into_tex
        mode = "full" if "2 trang" in self.cbo_kieu_phieu.currentText() else "1mat"
        src = Path(p)
        updated = inject_phieu_into_tex(src.read_text(encoding="utf-8", errors="replace"), template_key=mode, copy_to_dir=src.parent)
        out = src.with_name(f"{src.stem}_phieu2025.tex")
        out.write_text(updated, encoding="utf-8")
        QMessageBox.information(self, "Tạo phiếu thành công", f"Đã ghép phiếu vào tệp:\n{out}")

    def _open_w2t_options(self):
        from .word2tex_options_dialog import WordPdfToTexOptionsDialog
        WordPdfToTexOptionsDialog(self).exec()

    def _wrap_with_main_template(self, body: str, out_tex: Path, title: str = "") -> str:
        """Ghép nội dung .tex vào khung Main .tex có sẵn (ưu tiên Main .tex người dùng chọn -> Header.tex -> de_thi.tex)."""
        if r"\begin{document}" in body:
            return body

        # Chép nhd_extest.sty dự phòng vào cùng thư mục để luôn biên dịch được PDF
        sty_src = resource_path("nganhangde/templates/nhd_extest.sty")
        if sty_src.exists():
            sty_dst = out_tex.parent / "nhd_extest.sty"
            if not sty_dst.exists():
                try:
                    shutil.copy2(sty_src, sty_dst)
                except Exception:
                    pass

        main_path: Path | None = None
        if self.mw is not None and hasattr(self.mw, "cau_hoi_mylt"):
            mp_str = self.mw.cau_hoi_mylt.ed_main_tex.text().strip()
            if mp_str and Path(mp_str).exists():
                main_path = Path(mp_str)
        if main_path is None:
            cand = resource_path("nganhangde/templates/map_id/Header.tex")
            if cand.exists():
                main_path = cand

        if main_path is not None and main_path.exists():
            tpl = main_path.read_text(encoding="utf-8", errors="replace")
            if r"\begin{document}" in tpl:
                head, tail = tpl.split(r"\begin{document}", 1)
                return (
                    head.rstrip()
                    + "\n\\providecommand{\\MYLT}[1][]{}\n"
                    + "\\begin{document}\n"
                    + body.strip()
                    + "\n\\end{document}\n"
                )
            return (
                tpl.rstrip()
                + "\n\\providecommand{\\MYLT}[1][]{}\n"
                + "\\begin{document}\n"
                + body.strip()
                + "\n\\end{document}\n"
            )

        de_tpl = resource_path("nganhangde/templates/de_thi.tex")
        if de_tpl.exists():
            tpl = de_tpl.read_text(encoding="utf-8", errors="replace")
            tpl = tpl.replace("<<MODE>>", "loigiai").replace("<<TEN_DE>>", title or out_tex.stem).replace("<<MA_DE>>", "101")
            return tpl.replace("<<NOI_DUNG>>", body.strip())

        return (
            "\\documentclass[12pt,a4paper]{article}\n"
            "\\usepackage[utf8]{vietnam}\n"
            "\\usepackage{amsmath,amssymb,tikz,tkz-tab}\n"
            "\\usepackage[loigiai]{nhd_extest}\n"
            "\\providecommand{\\MYLT}[1][]{}\n"
            "\\begin{document}\n"
            + body.strip()
            + "\n\\end{document}\n"
        )

    def _do_word_pdf_to_tex(self):
        p_raw = self.cbo_w2t.currentText().strip()
        if not p_raw:
            self._pick_into(self.cbo_w2t, "Chọn file Word/PDF/Ảnh", "Word/PDF/Ảnh (*.docx *.pdf *.png *.jpg)")
            p_raw = self.cbo_w2t.currentText().strip()
            if not p_raw:
                return
        if p_raw.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
            self._call_mw("_run_ocr")
            return
        src = Path(p_raw)
        if not src.exists():
            QMessageBox.warning(self, "Không tìm thấy tệp", f"Tệp không tồn tại:\n{src}")
            return
        try:
            from ..converters.word_to_tex import convert_docx_to_questions
            from ..core.config_manager import ConfigManager as _CfgPre
            _cp = _CfgPre()
            _mode = _cp.get("Word2TeX", "mode", "toggle_tex")
            _show_w = _cp.get("Word2TeX", "show_word", "1") == "1"

            if _mode == "gemini":
                gem_key = _cp.get("API", "gemini_api_key", "").strip()
                if not gem_key:
                    QMessageBox.warning(self, "Thiếu Gemini API Key", "Bạn đang chọn chế độ 'Dùng Gemini'. Hãy mở 'Tuỳ chọn' và nhập Gemini API Key trước.")
                    return
                import tempfile as _tf
                from ..converters.mtef_bridge import convert_docx_to_pdf_via_word_com
                from ..ai.pdf_ocr import ocr_pdf_to_extest
                from ..ai.providers import AIConfig
                with _tf.TemporaryDirectory(prefix="w2t_gem_") as _td:
                    tmp_pdf = Path(_td) / f"{src.stem}.pdf"
                    ok_pdf, msg_pdf = convert_docx_to_pdf_via_word_com(src, tmp_pdf)
                    if not ok_pdf:
                        QMessageBox.critical(self, "Lỗi xuất PDF từ Word", msg_pdf)
                        return
                    ai_cfg = AIConfig(provider="gemini", api_key=gem_key, model=_cp.get("API", "gemini_model", "gemini-2.5-flash"))
                    body = ocr_pdf_to_extest(str(tmp_pdf), ai_cfg)
                out_tex = src.with_suffix(".tex")
                full_doc = self._wrap_with_main_template(body, out_tex, title=src.stem)
                out_tex.write_text(full_doc, encoding="utf-8")
                open_pdf_file(str(out_tex))
                QMessageBox.information(self, "Chuyển Word -> TeX (Gemini AI)", f"Đã chuyển đổi, ghép khung Main và mở tệp:\n{out_tex}")
                return

            qs, rep = convert_docx_to_questions(str(src), use_word_com=True, show_word=_show_w, mode=_mode)
            out_tex = src.with_suffix(".tex")
            if qs:
                body = "\n\n".join(q.to_latex(include_solution=True) for q in qs) + "\n"
            else:
                from docx import Document
                doc = Document(str(src))
                body = "\n\n".join(par.text.strip() for par in doc.paragraphs if par.text.strip()) + "\n"
            import json as _json
            from ..core.config_manager import ConfigManager as _Cfg
            _c = _Cfg()
            if _c.get("Word2TeX", "use_personal_rep", "0") == "1":
                try:
                    for _k, _v in _json.loads(_c.get("Word2TeX", "personal_rules_json", "[]")):
                        if _k:
                            body = body.replace(_k, _v)
                except Exception:
                    pass
            full_doc = self._wrap_with_main_template(body, out_tex, title=src.stem)
            out_tex.write_text(full_doc, encoding="utf-8")
            open_pdf_file(str(out_tex))
            QMessageBox.information(
                self,
                "Chuyển Word -> TeX thành công",
                f"Đã chuyển đổi: {src.name}\n"
                f"- Số câu hỏi nhận diện: {len(qs)}\n"
                f"- Công thức OMML: {rep.omml_count} | MathType/OLE: {rep.mathtype_ole_count} ({'ĐÃ CHUYỂN' if rep.mathtype_converted else 'chưa chuyển qua Word COM'}) | Ảnh: {rep.media_image_count}\n"
                f"- Tệp kết quả: {out_tex}" + ("\n- Ghi chú: " + " | ".join(rep.warnings) if rep.warnings else ""),
            )
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi chuyển Word -> TeX", str(exc))

    def _do_tex_to_word(self):
        p_raw = self.cbo_t2w.currentText().strip()
        if not p_raw:
            self._pick_into(self.cbo_t2w, "Chọn file .tex", "LaTeX (*.tex)")
            p_raw = self.cbo_t2w.currentText().strip()
            if not p_raw:
                return
        src = Path(p_raw)
        if not src.exists():
            QMessageBox.warning(self, "Không tìm thấy tệp", f"Tệp không tồn tại:\n{src}")
            return
        try:
            from ..core.parser import parse_tex_questions, read_tex_with_inputs
            from ..converters.tex_to_word import export_questions_to_docx
            qs = parse_tex_questions(read_tex_with_inputs(src), auto_normalize=True)
            if not qs:
                QMessageBox.warning(self, "Trống", "Không tìm thấy câu hỏi \\begin{ex}...\\end{ex} trong tệp .tex.")
                return
            out_docx = src.with_suffix(".docx")
            export_questions_to_docx(qs, str(out_docx), title=src.stem)
            QMessageBox.information(
                self,
                "Chuyển TeX -> Word thành công",
                f"Đã xuất {len(qs)} câu hỏi sang tệp Word:\n{out_docx}",
            )
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi chuyển TeX -> Word", str(exc))

    def _get_online_questions(self):
        from ..core.parser import parse_tex_questions, read_tex_with_inputs
        p_raw = self.ed_online_file.text().strip()
        if p_raw and Path(p_raw).exists():
            return parse_tex_questions(read_tex_with_inputs(p_raw), auto_normalize=True), Path(p_raw)
        return [], None

    def _do_export_moodle(self):
        qs, src = self._get_online_questions()
        if qs and src:
            from ..converters.moodle_xml import export_moodle_xml
            out = src.with_suffix(".xml")
            export_moodle_xml(qs, str(out), category_name=src.stem, asset_dir=str(src.parent))
            QMessageBox.information(self, "Xuất Moodle XML", f"Đã xuất {len(qs)} câu sang:\n{out}")
            return
        self._call_mw("_exp_moodle")

    def _do_export_aiken(self):
        qs, src = self._get_online_questions()
        if not qs:
            p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp .tex xuất Aiken", "", "LaTeX (*.tex)")
            if not p:
                return
            self.ed_online_file.setText(p)
            qs, src = self._get_online_questions()
        if not qs or not src:
            QMessageBox.warning(self, "Trống", "Không tìm thấy câu hỏi hợp lệ để xuất Aiken.")
            return
        from ..converters.aiken_exporter import export_aiken_txt
        out = src.with_name(f"{src.stem}_aiken.txt")
        export_aiken_txt(qs, str(out))
        QMessageBox.information(self, "Xuất Aiken thành công", f"Đã xuất {len(qs)} câu sang:\n{out}")

    def _do_export_online_gas(self):
        qs, src = self._get_online_questions()
        if qs and src:
            from ..exporters.online_gas import export_online_exam_bundle
            out_dir = src.parent / f"{src.stem}_online"
            out_dir.mkdir(parents=True, exist_ok=True)
            export_online_exam_bundle(qs, str(out_dir), exam_title=src.stem)
            QMessageBox.information(self, "Xuất đề Online", f"Đã xuất gói đề Online ({len(qs)} câu) vào:\n{out_dir}")
            return
        self._call_mw("_exp_gas")

    def _do_find_duplicates(self):
        from ..core.parser import parse_tex_questions, read_tex_with_inputs
        from ..core.similarity import jaccard_similarity

        threshold = int(self.cbo_dup_rate.currentText().replace("%", "") or "85") / 100.0
        scope = self.cbo_dup_scope.currentText().strip().upper()

        def _in_scope(qid: str) -> bool:
            return (not scope) or qid.upper().startswith(scope)

        pairs: list[tuple[float, str, str]] = []

        if self.rb_dup_files.isChecked():
            raw_paths = [s.strip() for s in self.cbo_dup_file.currentText().split(";") if s.strip()]
            if not raw_paths:
                QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex để tìm câu trùng (chế độ Từ Files).")
                return
            qs = []
            for rp in raw_paths:
                fp = Path(rp)
                if fp.exists():
                    for q in parse_tex_questions(read_tex_with_inputs(fp), auto_normalize=True):
                        if _in_scope(q.primary_id):
                            qs.append((fp.name, q))
            n = len(qs)
            for i in range(n):
                s1 = f"{qs[i][1].stem} {' '.join(qs[i][1].choices)}".lower()
                for j in range(i + 1, n):
                    s2 = f"{qs[j][1].stem} {' '.join(qs[j][1].choices)}".lower()
                    sim = jaccard_similarity(s1, s2)
                    if sim >= threshold:
                        pairs.append((sim, f"[{qs[i][0]} #{i+1}] {qs[i][1].stem[:55]}", f"[{qs[j][0]} #{j+1}] {qs[j][1].stem[:55]}"))

        elif self.rb_dup_fb.isChecked():
            raw_paths = [s.strip() for s in self.cbo_dup_file.currentText().split(";") if s.strip()]
            if not raw_paths:
                QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex để so sánh với ngân hàng (chế độ File > Bank).")
                return
            if self.mw is None or not hasattr(self.mw, "db") or self.mw.db is None:
                QMessageBox.warning(self, "Ngân hàng", "Chưa kết nối cơ sở dữ liệu ngân hàng.")
                return
            bank_rows = [
                r for r in self.mw.db.conn.execute("SELECT id, qid, stem, stem_plain FROM questions").fetchall()
                if _in_scope(str(r["qid"] or ""))
            ]
            for rp in raw_paths:
                fp = Path(rp)
                if not fp.exists():
                    continue
                for idx, q in enumerate(parse_tex_questions(read_tex_with_inputs(fp), auto_normalize=True), 1):
                    if not _in_scope(q.primary_id):
                        continue
                    s1 = f"{q.stem} {' '.join(q.choices)}".lower()
                    for br in bank_rows[:2000]:
                        sim = jaccard_similarity(s1, str(br["stem_plain"] or ""))
                        if sim >= threshold:
                            pairs.append((sim, f"[File #{idx}] {q.stem[:55]}", f"[Bank ID={br['id']}] {str(br['stem'] or '')[:55]}"))
                            break
        else:
            # Từ ngân hàng
            if self.mw is None or not hasattr(self.mw, "db") or self.mw.db is None:
                self._call_mw("_find_similar")
                return
            bank_rows = [
                r for r in self.mw.db.conn.execute("SELECT id, qid, stem, stem_plain FROM questions LIMIT 1500").fetchall()
                if _in_scope(str(r["qid"] or ""))
            ]
            n = len(bank_rows)
            for i in range(n):
                s1 = str(bank_rows[i]["stem_plain"] or "")
                for j in range(i + 1, n):
                    sim = jaccard_similarity(s1, str(bank_rows[j]["stem_plain"] or ""))
                    if sim >= threshold:
                        pairs.append((sim, f"[Bank #{bank_rows[i]['id']}] {str(bank_rows[i]['stem'] or '')[:55]}", f"[Bank #{bank_rows[j]['id']}] {str(bank_rows[j]['stem'] or '')[:55]}"))

        if not pairs:
            QMessageBox.information(
                self,
                "Tìm câu hỏi trùng",
                f"Không tìm thấy cặp câu trùng nào với tỉ lệ >= {int(threshold*100)}%"
                + (f" trong phạm vi '{scope}'." if scope else "."),
            )
            return

        pairs.sort(key=lambda x: x[0], reverse=True)
        lines = [f"{int(sim*100)}% | {a}  <-->  {b}" for sim, a, b in pairs[:20]]
        extra = f"\n... và còn {len(pairs) - 20} cặp khác." if len(pairs) > 20 else ""
        QMessageBox.information(
            self,
            f"Tìm thấy {len(pairs)} cặp câu trùng (>= {int(threshold*100)}%)",
            "\n".join(lines) + extra,
        )

    def _do_compile_pdf(self):
        p = self.ed_pdf_tex.text().strip()
        if not p or not Path(p).exists():
            QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex cần biên dịch PDF.")
            return
        res = compile_tex_to_pdf(p, compiler="pdflatex", passes=1)
        if res.success and res.pdf_path:
            open_pdf_file(res.pdf_path)
        else:
            diag = "\n".join(f"Dòng {d.line_no}: {d.summary}" for d in res.diagnostics[:4])
            QMessageBox.critical(self, "Lỗi biên dịch PDF", diag or res.stderr or "Không thể biên dịch PDF.")

    def _do_tikz2img(self):
        p = self.ed_img_tex.text().strip()
        if not p or not Path(p).exists():
            QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex cần hoá ảnh TikZ.")
            return
        from ..exporters.tikz2pic import export_tikz_blocks_to_png
        out_dir = Path(p).parent / f"{Path(p).stem}_images"
        imgs = export_tikz_blocks_to_png(Path(p).read_text(encoding="utf-8", errors="replace"), out_dir)
        QMessageBox.information(self, "Tikz2Img", f"Đã xuất {len(imgs)} ảnh PNG vào:\n{out_dir}")

    def _do_blogger(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp đề .tex xuất Blogger", "", "LaTeX (*.tex)")
        if not p:
            return
        from ..exporters.blogger_form_exporter import export_blogger_html
        out = Path(p).with_suffix(".html")
        export_blogger_html(Path(p).read_text(encoding="utf-8", errors="replace"), out)
        QMessageBox.information(self, "Xuất Blogger thành công", f"Đã tạo trang HTML Blogger:\n{out}")

    def _do_convert_pkg(self):
        p = self.cbo_conv_file.currentText().strip()
        if not p or not Path(p).exists():
            QMessageBox.warning(self, "Chọn tệp", "Hãy chọn tệp .tex cần chuyển đổi.")
            return
        src = Path(p)
        txt = src.read_text(encoding="utf-8", errors="replace")
        if self.rb_extest.isChecked():
            txt = convert_extest_old_to_new(txt)
            suffix = "_extest_moi"
        else:
            txt = convert_dethi_to_extest(txt)
            suffix = "_extest"
        out = src.with_name(f"{src.stem}{suffix}.tex")
        out.write_text(txt, encoding="utf-8")
        QMessageBox.information(self, "Chuyển đổi thành công", f"Đã lưu tệp:\n{out}")


# ==============================================================================
# 3. TAB VẼ HÌNH (Chuẩn bố cục MyLT 2026 v1.0.3.44)
# ==============================================================================
class VeHinhMyLT2026Tab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.steps: list[tuple[str, str]] = []  # (code_line, loai)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Thanh công cụ 9 nhóm như MyLT 2026
        bar = QHBoxLayout()
        presets = [
            ("Điểm", r"\coordinate (A) at (0,0);", "Điểm"),
            ("Đoạn thẳng", r"\draw (0,0)--(4,0);", "Đoạn thẳng"),
            ("Đường tròn", r"\draw (0,0) circle (2);", "Đường tròn"),
            ("Ellipse", r"\draw (0,0) ellipse (2.5 and 1.2);", "Ellipse"),
            ("Đường cong", r"\draw (0,0) .. controls (1,2) and (3,2) .. (4,0);", "Đường cong"),
            ("Kí hiệu", r"\draw[thick] (0,0) rectangle (0.3,0.3);", "Kí hiệu"),
            ("Tô miền", r"\fill[teal!20] (0,0)--(3,0)--(1.5,2.5)--cycle;", "Tô miền"),
            ("Hình mẫu", r"\coordinate (A) at (0,0); \coordinate (B) at (4,0); \coordinate (C) at (1.5,3); \draw (A)--(B)--(C)--cycle;", "Hình mẫu"),
        ]
        for label, snippet, kind in presets:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, s=snippet, k=kind: self._add_step(s, k))
            bar.addWidget(b)
        bar.addStretch()
        root.addLayout(bar)

        # Vùng giữa: Trái (Bảng Các bước đã vẽ) | Giữa (D, E, ▲, ▼) | Phải (Xem trước + Code)
        mid = QHBoxLayout()

        g_left = QGroupBox("Các bước đã vẽ")
        vl = QVBoxLayout(g_left)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["STT", "Nội dung", "Loại"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        vl.addWidget(self.tbl)
        mid.addWidget(g_left, 5)

        col_mid = QVBoxLayout()
        col_mid.addStretch()
        for sym, fn in [("D", self._del_step), ("E", self._edit_step), ("▲", lambda: self._move_step(-1)), ("▼", lambda: self._move_step(1))]:
            b = QPushButton(sym); b.setFixedWidth(34); b.clicked.connect(fn); col_mid.addWidget(b)
        col_mid.addStretch()
        mid.addLayout(col_mid)

        right_sp = QSplitter(Qt.Vertical)
        self.preview_panel = InlinePdfPreviewPanel(auto_checked=True)
        g_prev = self.preview_panel

        g_code = QGroupBox("Code")
        vc = QVBoxLayout(g_code)
        self.ed_code = QPlainTextEdit()
        vc.addWidget(self.ed_code)

        right_sp.addWidget(g_prev); right_sp.addWidget(g_code)
        mid.addWidget(right_sp, 4)
        root.addLayout(mid, 1)

        # Thanh nút dưới cùng
        bot = QHBoxLayout()
        bot.addStretch()
        b_new = QPushButton("Hình mới"); b_new.clicked.connect(self._clear_all)
        b_pdf = QPushButton("Xem PDF"); b_pdf.clicked.connect(self._view_pdf)
        b_copy = QPushButton("Copy code"); b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_code.toPlainText()))
        b_rebuild = QPushButton("Sửa code"); b_rebuild.clicked.connect(self._rebuild_code)
        b_copy_img = QPushButton("Copy hình"); b_copy_img.clicked.connect(self._copy_img)
        for b in (b_new, b_pdf, b_copy, b_rebuild, b_copy_img):
            bot.addWidget(b)
        bot.addStretch()
        root.addLayout(bot)

    def _add_step(self, code_line: str, kind: str):
        self.steps.append((code_line, kind))
        self._refresh_table()

    def _del_step(self):
        row = self.tbl.currentRow()
        if 0 <= row < len(self.steps):
            self.steps.pop(row)
            self._refresh_table()

    def _edit_step(self):
        row = self.tbl.currentRow()
        if 0 <= row < len(self.steps):
            txt, ok = QInputDialog.getText(self, "Sửa bước vẽ", "Mã TikZ:", text=self.steps[row][0])
            if ok and txt.strip():
                self.steps[row] = (txt.strip(), self.steps[row][1])
                self._refresh_table()

    def _move_step(self, delta: int):
        row = self.tbl.currentRow()
        nxt = row + delta
        if 0 <= row < len(self.steps) and 0 <= nxt < len(self.steps):
            self.steps[row], self.steps[nxt] = self.steps[nxt], self.steps[row]
            self._refresh_table()
            self.tbl.selectRow(nxt)

    def _clear_all(self):
        self.steps.clear()
        self._refresh_table()

    def _refresh_table(self):
        self.tbl.setRowCount(len(self.steps))
        for i, (code_line, kind) in enumerate(self.steps):
            self.tbl.setItem(i, 0, QTableWidgetItem(str(i + 1)))
            self.tbl.setItem(i, 1, QTableWidgetItem(code_line))
            self.tbl.setItem(i, 2, QTableWidgetItem(kind))
        self._rebuild_code()


    def _view_pdf(self):
        code = self.ed_code.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Trống", "Chưa có mã TikZ để biên dịch PDF.")
            return
        self.preview_panel.compile_and_show_tikz(code)

    def _copy_img(self):
        if self.preview_panel.copy_image_to_clipboard():
            QMessageBox.information(self, "Copy hình", "Đã sao chép hình ảnh vào clipboard.")
        else:
            QMessageBox.warning(self, "Chưa có hình", "Hãy bấm 'Xem PDF' để biên dịch hình trước.")

    def _rebuild_code(self):
        body = "\n  ".join(s[0] for s in self.steps)
        full = "\\begin{tikzpicture}[scale=1,>=stealth]\n  " + body + "\n\\end{tikzpicture}" if body else ""
        self.ed_code.setPlainText(full)


# ==============================================================================
# 4. TAB ĐỒ THỊ (Chuẩn bố cục MyLT 2026 v1.0.3.44)
# ==============================================================================
class DoThiMyLT2026Tab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.giong_points: list[tuple[str, str]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Thanh trên cùng 4 nhóm hàm số
        bar = QHBoxLayout()
        self.cbo_func = QComboBox()
        self.cbo_func.addItems([
            "x^3 - 3*x + 1",
            "x^4 - 2*x^2 - 1",
            "(2*x - 1)/(x - 1)",
            "x^2 - 2*x - 3",
            "sin(deg(x))",
        ])
        self.cbo_func.setEditable(True)
        b_gen_now = QPushButton("Tạo code")
        b_gen_now.clicked.connect(self._generate_code)
        bar.addWidget(QLabel("Hàm số y = f(x):"))
        bar.addWidget(self.cbo_func, 1)
        bar.addWidget(b_gen_now)
        root.addLayout(bar)

        # Vùng giữa: Trái (Tuỳ chỉnh 2 trục + Giá trị + Điểm gióng) | Giữa (Code) | Phải (Xem trước)
        sp = QSplitter(Qt.Horizontal)

        left = QWidget()
        vl = QVBoxLayout(left)

        g_truc = QGroupBox("Tuỳ chỉnh 2 trục")
        ft = QGridLayout(g_truc)
        self.ed_xmin = QLineEdit("-3"); self.ed_xmax = QLineEdit("3")
        self.ed_ymin = QLineEdit("-3"); self.ed_ymax = QLineEdit("4")
        ft.addWidget(QLabel("Trục Ox"), 0, 0); ft.addWidget(self.ed_xmin, 0, 1); ft.addWidget(QLabel("< x <"), 0, 2); ft.addWidget(self.ed_xmax, 0, 3)
        ft.addWidget(QLabel("Trục Oy"), 1, 0); ft.addWidget(self.ed_ymin, 1, 1); ft.addWidget(QLabel("< y <"), 1, 2); ft.addWidget(self.ed_ymax, 1, 3)
        vl.addWidget(g_truc)

        g_val = QGroupBox("Các giá trị trên 2 trục")
        fv = QFormLayout(g_val)
        self.ed_xvals = QLineEdit("-2,-1,1,2")
        self.ed_yvals = QLineEdit("-1,1,3")
        fv.addRow("Trục Ox:", self.ed_xvals)
        fv.addRow("Trục Oy:", self.ed_yvals)
        vl.addWidget(g_val)

        g_pt = QGroupBox("Điểm gióng")
        fp = QHBoxLayout(g_pt)
        self.ed_px = QLineEdit("1"); self.ed_py = QLineEdit("-1")
        b_add_pt = QPushButton("Thêm"); b_add_pt.clicked.connect(self._add_giong)
        fp.addWidget(QLabel("x =")); fp.addWidget(self.ed_px); fp.addWidget(QLabel("y =")); fp.addWidget(self.ed_py); fp.addWidget(b_add_pt)
        vl.addWidget(g_pt)
        vl.addStretch()

        g_code = QGroupBox("Code")
        vc = QVBoxLayout(g_code)
        self.ed_code = QPlainTextEdit()
        vc.addWidget(self.ed_code)

        self.preview_panel = InlinePdfPreviewPanel(auto_checked=True)
        g_prev = self.preview_panel

        sp.addWidget(left); sp.addWidget(g_code); sp.addWidget(g_prev)
        sp.setSizes([280, 520, 340])
        root.addWidget(sp, 1)

        # Thanh nút dưới cùng
        bot = QHBoxLayout()
        bot.addStretch()
        b_new = QPushButton("Hình mới"); b_new.clicked.connect(self._reset)
        b_pdf = QPushButton("Xem PDF"); b_pdf.clicked.connect(self._view_pdf)
        b_copy = QPushButton("Copy code"); b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_code.toPlainText()))
        b_copy_img = QPushButton("Copy hình"); b_copy_img.clicked.connect(self._copy_img)
        b_create = QPushButton("Tạo code"); b_create.clicked.connect(self._generate_code)
        for b in (b_new, b_pdf, b_copy, b_copy_img, b_create):
            bot.addWidget(b)
        bot.addStretch()
        root.addLayout(bot)

    def _add_giong(self):
        px, py = self.ed_px.text().strip(), self.ed_py.text().strip()
        if px and py:
            self.giong_points.append((px, py))
            self._generate_code()

    def _reset(self):
        self.giong_points.clear()
        self.ed_code.clear()

    def _generate_code(self):
        expr = self.cbo_func.currentText().strip() or "x^3 - 3*x + 1"
        # Chuyển biến x thành (\x) đúng chuẩn cú pháp TikZ plot (\x, {...})
        tikz_expr = re.sub(r"(?<![a-zA-Z\\])x(?![a-zA-Z])", lambda _: r"(\x)", expr)
        xmin, xmax = self.ed_xmin.text().strip() or "-3", self.ed_xmax.text().strip() or "3"
        ymin, ymax = self.ed_ymin.text().strip() or "-3", self.ed_ymax.text().strip() or "4"
        giong_lines = []
        for px, py in self.giong_points:
            giong_lines.append(f"  \\draw[dashed] ({px},0)--({px},{py})--(0,{py});")
            giong_lines.append(f"  \\fill ({px},{py}) circle (1.5pt);")
        extra = ("\n" + "\n".join(giong_lines)) if giong_lines else ""
        code = (
            "\\begin{tikzpicture}[scale=0.9,>=stealth]\n"
            f"  \\draw[->] ({xmin},0)--({xmax},0) node[below]{{$x$}};\n"
            f"  \\draw[->] (0,{ymin})--(0,{ymax}) node[left]{{$y$}};\n"
            f"  \\node[below left] at (0,0) {{$O$}};\n"
            + (f"  \\foreach \\xv in {{{self.ed_xvals.text().strip()}}} \\draw (\\xv,0.08)--(\\xv,-0.08) node[below]{{${{\\xv}}$}};\n" if self.ed_xvals.text().strip() else "")
            + (f"  \\foreach \\yv in {{{self.ed_yvals.text().strip()}}} \\draw (0.08,\\yv)--(-0.08,\\yv) node[left]{{${{\\yv}}$}};\n" if self.ed_yvals.text().strip() else "")
            + f"  \\begin{{scope}}\n"
            f"    \\clip ({xmin},{ymin}) rectangle ({xmax},{ymax});\n"
            f"    \\draw[thick,samples=150,domain={xmin}:{xmax}] plot (\\x, {{{tikz_expr}}});\n"
            f"  \\end{{scope}}{extra}\n"
            "\\end{tikzpicture}"
        )
        self.ed_code.setPlainText(code)
        if self.preview_panel.is_auto_preview():
            self.preview_panel.compile_and_show_tikz(code)


    def _view_pdf(self):
        code = self.ed_code.toPlainText().strip()
        if not code:
            self._generate_code()
            code = self.ed_code.toPlainText().strip()
        self.preview_panel.compile_and_show_tikz(code)

    def _copy_img(self):
        if self.preview_panel.copy_image_to_clipboard():
            QMessageBox.information(self, "Copy hình", "Đã sao chép hình ảnh vào clipboard.")
        else:
            QMessageBox.warning(self, "Chưa có hình", "Hãy bấm 'Xem PDF' để biên dịch hình trước.")
