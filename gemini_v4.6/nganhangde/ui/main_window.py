import os
import sys
import tempfile
import webbrowser
from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPlainTextEdit, QPushButton, QRadioButton, QSpinBox,
    QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..ai.pdf_ocr import ocr_pdf_to_extest
from ..ai.providers import AIConfig
from ..converters.moodle_xml import export_moodle_xml
from ..converters.tex_to_word import export_questions_to_docx
from ..converters.word_to_tex import convert_docx_to_questions
from ..core.batch_tracker import list_exam_batches, record_exam_batch
from ..core.db import QuestionBankDB
from ..core.drawgen import (
    IntervalSpec, generate_function_graph_tikz, generate_linear_inequality_region_tikz,
    generate_number_line_tikz, generate_solid_geometry_tikz, generate_variation_table_tikz,
)
from ..core.generator import ExamVariant, generate_exam_batch
from ..core.idmap_builtin import GDPT2018_MATH_CATALOG, describe_id6, export_id6_lookup_html
from ..core.matrix_cv7991 import ExamMatrix, MatrixRule
from ..core.parser import Question, parse_tex_questions
from ..core.review import audit_question
from ..core.similarity import find_similar_questions
from ..exporters.arena_host import LanArenaServer, detect_lan_ip
from ..exporters.omr_excel import OMR_PROFILES, export_answer_csv_bom, export_omr_excel
from ..exporters.online_gas import export_online_exam_bundle
from ..exporters.pdfbuild import compile_tex_to_pdf, detect_tex_compiler
from ..exporters.spec_docx_xlsx import export_cv7991_docx, export_cv7991_excel
from ..exporters.tex_exporter import export_exam_tex_suite
from ..paths import resource_path, user_data_dir
from .data_tree import WorkspaceDataTree
from .mylt_pro_tabs import AIStationTab, TopicBookTab
from .mylt2025_suite_tab import MyLT2025SuiteTab
from .tien_ich_2_tab import TienIch2Tab
from .doi_so_tab import DoiSoTab
from .mylt2026_exact_widgets import TuyChonDePanel, TienIch1Panel, VeHinhMyLT2026Tab, DoThiMyLT2026Tab
from ..exporters.phieu_tltn_2025 import inject_phieu_into_tex
from .mylt2026_tabs_extra import BBTXDMyLT2026Tab, BieuDienNghiemMyLT2026Tab, SoanThaoMyLT2026Tab
from .cau_hoi_mylt2026_tab import CauHoiMyLT2026Tab
from .pdf_preview import make_qimage_from_pdf_page
from .presentation_mode import PresentationDialog
from .workers import run_in_background


class MyLT2026MainWindow(QMainWindow):
    """Giao diện 10 tab chuẩn bố cục MyLT 2026:
    Trộn đề | Câu hỏi | Ma trận | Tiện ích | Vẽ hình | Đồ thị | BBT&XD | Biểu diễn nghiệm | Soạn thảo | Thông tin
    """

    def __init__(self, db_path: str | None = None):
        super().__init__()
        self.setWindowTitle("toan11 — MyLT 2026 v1.0")
        self.setMinimumSize(960, 620)
        self.resize(1240, 740)
        ico = resource_path("nganhangde/assets/app.ico")
        if ico.exists():
            self.setWindowIcon(QIcon(str(ico)))

        self.db = QuestionBankDB(db_path or str(user_data_dir() / "nganhang_mylt2026.db"))
        self.current_questions: list[Question] = []
        self.source_file_questions: list[Question] = []
        self.last_variants: list[ExamVariant] = []
        self.loaded_matrix: ExamMatrix | None = None
        self.custom_omr_template: str | None = None
        self.arena_server: LanArenaServer | None = None
        self._id_groups: list[dict] = []

        central = QWidget()
        self.setCentralWidget(central)
        main_lay = QVBoxLayout(central)
        main_lay.setContentsMargins(6, 6, 6, 6)
        main_lay.setSpacing(6)

        self.tabs = QTabWidget()
        main_lay.addWidget(self.tabs, stretch=1)

        # Thanh nút dưới cùng bên phải (Tạo đề | Thoát) giống MyLT 2026
        bottom_bar = QHBoxLayout()
        self.lbl_status_global = QLabel("Sẵn sàng — Kho FTS5 đang hoạt động.")
        btn_create = QPushButton("Tạo đề")
        btn_create.setMinimumWidth(95)
        btn_create.clicked.connect(self._create_and_export_exam)
        btn_exit = QPushButton("Thoát")
        btn_exit.setMinimumWidth(85)
        btn_exit.clicked.connect(self.close)
        bottom_bar.addWidget(self.lbl_status_global, stretch=1)
        bottom_bar.addWidget(btn_create)
        bottom_bar.addWidget(btn_exit)
        main_lay.addLayout(bottom_bar)

        # 10 Tab chính theo đúng thứ tự MyLT 2026
        self._build_tab_1_tron_de()
        self._build_tab_2_cau_hoi()
        self._build_tab_3_ma_tran()
        self._build_tab_4_tien_ich()
        self._build_tab_5_ve_hinh()
        self._build_tab_6_do_thi()
        self._build_tab_7_bbt_xd()
        self._build_tab_8_bieu_dien_nghiem()
        self._build_tab_9_soan_thao()
        self._build_tab_10_thong_tin()

        self._refresh_bank()
        self._refresh_tree()
        self._refresh_id_matrix_table()

    def closeEvent(self, event):
        if self.arena_server:
            self.arena_server.stop()
        self.db.close()
        super().closeEvent(event)

    def _get_ai_config(self) -> AIConfig:
        return AIConfig(
            provider=self.cb_prov.currentText(),
            api_key=self.inp_key.text().strip(),
            model=self.inp_model.text().strip(),
            thinking_budget=(self.sp_think.value() or None),
        )

    # ==========================================================================
    # TAB 1: TRỘN ĐỀ (5 sub-tabs giống hệt bố cục ảnh mẫu MyLT 2026)
    # ==========================================================================
    def _build_tab_1_tron_de(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setSpacing(6)

        # Khối chọn nguồn phía trên
        src_box = QGroupBox()
        src_v = QVBoxLayout(src_box)
        src_v.setContentsMargins(8, 6, 8, 6)
        r_row = QHBoxLayout()
        self.rb_from_bank = QRadioButton("Từ ngân hàng câu hỏi")
        self.rb_from_files = QRadioButton("Từ Files. Chọn một hoặc nhiều file nguồn chứa câu hỏi")
        self.rb_from_bank.setChecked(True)
        bg = QButtonGroup(self)
        bg.addButton(self.rb_from_bank)
        bg.addButton(self.rb_from_files)
        r_row.addWidget(self.rb_from_bank)
        r_row.addWidget(self.rb_from_files)
        r_row.addStretch()
        src_v.addLayout(r_row)

        b_row = QHBoxLayout()
        b_open_bank = QPushButton("Mở ngân hàng")
        b_imp_q = QPushButton("Nhập câu hỏi")
        b_sample = QPushButton("Nạp mẫu Toán 11")
        b_pick_files = QPushButton("Chọn file .tex nguồn...")
        b_open_bank.clicked.connect(self._open_bank_db)
        b_imp_q.clicked.connect(self._import_tex)
        b_sample.clicked.connect(self._load_sample)
        b_pick_files.clicked.connect(self._pick_source_tex_files)
        for b in (b_open_bank, b_imp_q, b_sample, b_pick_files):
            b_row.addWidget(b)
        b_row.addStretch()
        src_v.addLayout(b_row)
        lay.addWidget(src_box)

        # 5 sub-tab trong Trộn đề
        self.sub_tron = QTabWidget()
        lay.addWidget(self.sub_tron, stretch=1)

        self._build_subtab_theo_id()
        self._build_subtab_tu_chon()
        self._build_subtab_theo_file()
        self._build_subtab_tuong_tu()
        self._build_subtab_tuy_chon()

        self.tabs.addTab(tab, "Trộn đề")

    def _build_subtab_theo_id(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(6)

        # GroupBox: Chọn nhanh
        g_fast = QGroupBox("Chọn nhanh")
        grid = QGridLayout(g_fast)
        self.cb_fast_lop = QComboBox(); self.cb_fast_lop.addItems(["Tất cả", "6", "7", "8", "9", "10", "11", "12"])
        self.cb_fast_mon = QComboBox(); self.cb_fast_mon.addItems(["Tất cả", "D - Đại số / Giải tích", "H - Hình học"])
        self.cb_fast_chuong = QComboBox(); self.cb_fast_chuong.addItems(["Tất cả"] + [f"{c['prefix']} - {c['chapter']}" for c in GDPT2018_MATH_CATALOG])
        self.cb_fast_bai = QComboBox(); self.cb_fast_bai.addItems(["Tất cả", "1", "2", "3", "4", "5", "6"])
        self.cb_fast_dang = QComboBox(); self.cb_fast_dang.addItems(["Tất cả", "1", "2", "3", "4", "5"])
        self.cb_fast_muc = QComboBox(); self.cb_fast_muc.addItems(["Tất cả", "N - Nhận biết", "H - Thông hiểu", "V - Vận dụng", "C - Vận dụng cao"])
        self.cb_fast_loai = QComboBox(); self.cb_fast_loai.addItems(["Tất cả", "TN", "DS", "KQ", "TL"])
        self.sp_fast_count = QSpinBox(); self.sp_fast_count.setRange(1, 50); self.sp_fast_count.setValue(1)
        b_fast_loc = QPushButton("Lọc")
        b_fast_lay = QPushButton("Lấy")
        b_fast_loc.clicked.connect(self._refresh_id_matrix_table)
        b_fast_lay.clicked.connect(self._quick_pick_to_table)

        grid.addWidget(QLabel("Lớp"), 0, 0); grid.addWidget(self.cb_fast_lop, 0, 1)
        grid.addWidget(QLabel("Bài"), 0, 2); grid.addWidget(self.cb_fast_bai, 0, 3)
        grid.addWidget(QLabel("Loại"), 0, 4); grid.addWidget(self.cb_fast_loai, 0, 5)
        grid.addWidget(QLabel("Môn"), 1, 0); grid.addWidget(self.cb_fast_mon, 1, 1)
        grid.addWidget(QLabel("Dạng"), 1, 2); grid.addWidget(self.cb_fast_dang, 1, 3)
        grid.addWidget(QLabel("Số câu"), 1, 4); grid.addWidget(self.sp_fast_count, 1, 5)
        grid.addWidget(QLabel("Chương"), 2, 0); grid.addWidget(self.cb_fast_chuong, 2, 1)
        grid.addWidget(QLabel("Mức độ"), 2, 2); grid.addWidget(self.cb_fast_muc, 2, 3)
        hb_fl = QHBoxLayout(); hb_fl.addWidget(b_fast_loc); hb_fl.addWidget(b_fast_lay)
        grid.addLayout(hb_fl, 2, 4, 1, 2)
        grid.setColumnStretch(1, 2); grid.setColumnStretch(3, 2)
        lay.addWidget(g_fast)

        # GroupBox: Chọn theo ID (bảng 14 cột chuẩn MyLT 2026)
        g_id = QGroupBox("Chọn theo ID")
        vid = QVBoxLayout(g_id)
        fbar = QHBoxLayout()
        self.cb_id_lop = QComboBox(); self.cb_id_lop.addItems(["Tất cả", "0 (Lớp 10)", "1 (Lớp 11)", "2 (Lớp 12)", "6", "7", "8", "9"])
        self.cb_id_mon = QComboBox(); self.cb_id_mon.addItems(["Tất cả", "D", "H"])
        self.cb_id_loai = QComboBox(); self.cb_id_loai.addItems(["Tất cả", "TN", "DS", "KQ", "TL"])
        self.inp_id_filter = QLineEdit(); self.inp_id_filter.setPlaceholderText("Mẫu ID (VD: 1D2*)")
        b_id_loc = QPushButton("Lọc")
        b_id_loc.clicked.connect(self._refresh_id_matrix_table)
        for lbl, wid in [("Lớp", self.cb_id_lop), ("Môn", self.cb_id_mon), ("Loại", self.cb_id_loai), ("ID", self.inp_id_filter)]:
            fbar.addWidget(QLabel(lbl)); fbar.addWidget(wid)
        fbar.addWidget(b_id_loc)
        vid.addLayout(fbar)

        cols = [
            "STT", "ID", "Lớp", "Môn", "Chương", "Bài, dạng", "Loại",
            "Đã có (N/H/V/C)", "Nhận biết", "Thông hiểu", "Vận dụng", "Vận dụng cao", "Tổng có", "Tổng lấy",
        ]
        self.tbl_id_pick = QTableWidget(0, len(cols))
        self.tbl_id_pick.setHorizontalHeaderLabels(cols)
        self.tbl_id_pick.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tbl_id_pick.cellChanged.connect(self._recalc_id_pick_totals)
        vid.addWidget(self.tbl_id_pick, stretch=1)

        # Thanh nút tắt dưới bảng: [?][H][A][C][E][D][O][U] | Đã chọn: ... | Đầu Trước Sau Cuối
        b_foot = QHBoxLayout()
        for sym, tip, fn in [
            ("?", "Hướng dẫn chọn ID", lambda: QMessageBox.information(self, "Hướng dẫn", "Nhập số câu cần lấy vào 4 cột Nhận biết / Thông hiểu / Vận dụng / Vận dụng cao rồi bấm Tạo đề.")),
            ("H", "Chọn hết tất cả câu hiện có", self._pick_all_available),
            ("A", "Xóa trắng số câu đã chọn", self._clear_all_picked),
            ("C", "Mở tra cứu ID6 HTML", self._open_id6),
        ]:
            bt = QPushButton(sym); bt.setFixedWidth(28); bt.setToolTip(tip); bt.clicked.connect(fn)
            b_foot.addWidget(bt)
        self.lbl_picked_summary = QLabel("Đã chọn: 0 câu")
        self.lbl_picked_summary.setAlignment(Qt.AlignCenter)
        b_foot.addWidget(self.lbl_picked_summary, stretch=1)
        for lbl in ("Đầu", "Trước", "Sau", "Cuối"):
            bp = QPushButton(lbl); bp.setFixedWidth(55); b_foot.addWidget(bp)
        vid.addLayout(b_foot)
        lay.addWidget(g_id, stretch=1)
        self.sub_tron.addTab(w, "Tạo đề theo ID")

    def _build_subtab_tu_chon(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Tích chọn trực tiếp từng câu hỏi trong danh sách để đưa vào đề (hoặc dùng Tab Câu hỏi để lọc trước):"))
        self.tbl_manual = QTableWidget(0, 5)
        self.tbl_manual.setHorizontalHeaderLabels(["Chọn", "Mã ID6", "Loại", "Đã dùng", "Nội dung câu hỏi"])
        self.tbl_manual.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        lay.addWidget(self.tbl_manual, stretch=1)
        self.sub_tron.addTab(w, "Tạo đề tự chọn")

    def _build_subtab_theo_file(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        hb = QHBoxLayout()
        b_add = QPushButton("Chọn một hoặc nhiều file .tex để trộn trực tiếp")
        b_add.clicked.connect(self._pick_source_tex_files)
        hb.addWidget(b_add); hb.addStretch()
        lay.addLayout(hb)
        self.txt_file_list = QPlainTextEdit(); self.txt_file_list.setReadOnly(True)
        lay.addWidget(self.txt_file_list)
        self.sub_tron.addTab(w, "Tạo đề theo file")

    def _build_subtab_tuong_tu(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(QLabel("Tạo đề tương tự theo đúng ma trận ID của một tệp đề gốc .tex:"))
        hb = QHBoxLayout()
        b_ref = QPushButton("Chọn đề gốc (.tex) để rút đề tương tự từ kho")
        b_ref.clicked.connect(self._build_similar_from_tex)
        hb.addWidget(b_ref); hb.addStretch()
        lay.addLayout(hb)
        self.txt_sim_log = QPlainTextEdit(); self.txt_sim_log.setReadOnly(True)
        lay.addWidget(self.txt_sim_log)
        self.sub_tron.addTab(w, "Tạo đề tương tự")

    def _build_subtab_tuy_chon(self):
        w = QWidget()
        f = QFormLayout(w)
        self.inp_title = QLineEdit("ĐỀ KIỂM TRA ĐỊNH KÌ TOÁN")
        self.sp_n = QSpinBox(); self.sp_n.setRange(1, 50); self.sp_n.setValue(4)
        self.sp_seed = QSpinBox(); self.sp_seed.setRange(1, 999999); self.sp_seed.setValue(2026)
        self.chk_balance = QCheckBox("Cân bằng tần suất đáp án A/B/C/D (Phần I)"); self.chk_balance.setChecked(True)
        self.chk_sort_level = QCheckBox("Sắp xếp tăng dần theo mức độ (N → H → V → C)")
        self.chk_qr = QCheckBox("Nhúng Mã QR đáp án vào cuối bản lời giải")
        self.cb_omr = QComboBox()
        for k, prof in OMR_PROFILES.items():
            self.cb_omr.addItem(f"{prof.label} ({k})", k)
        b_omr_tpl = QPushButton("Chọn file mẫu OMR Excel riêng (Azota/TNMaker)...")
        b_omr_tpl.clicked.connect(self._pick_omr_template)
        f.addRow("Tên kỳ thi:", self.inp_title)
        f.addRow("Số mã đề (4 chữ số CV 1239):", self.sp_n)
        f.addRow("Seed tái lập:", self.sp_seed)
        f.addRow("Mẫu phiếu OMR 2025:", self.cb_omr)
        f.addRow("Mẫu OMR tùy chỉnh:", b_omr_tpl)
        f.addRow("", self.chk_balance)
        f.addRow("", self.chk_sort_level)
        f.addRow("", self.chk_qr)
        self.tuy_chon_panel = TuyChonDePanel()
        self.sub_tron.addTab(self.tuy_chon_panel, "Tuỳ chọn đề")
        self.sub_tron.addTab(w, "Cấu hình OMR / Seed")

    # ==========================================================================
    # TAB 2: CÂU HỎI (FTS5, Cây dữ liệu, Rà soát CV 1239, Tìm gần trùng, F11)
    # ==========================================================================
    def _build_tab_2_cau_hoi(self):
        tab = QWidget()
        lay = QHBoxLayout(tab)
        sp = QSplitter(Qt.Horizontal)
        left, right = QWidget(), QWidget()
        lv, rv = QVBoxLayout(left), QVBoxLayout(right)

        self.tree = WorkspaceDataTree()
        self.tree.action_triggered.connect(self._on_tree_act)
        b_add = QPushButton("+ Thêm thư mục đề")
        b_add.clicked.connect(lambda: (self.db.add_workspace_node("Thư mục đề mới"), self._refresh_tree()))
        lv.addWidget(b_add); lv.addWidget(self.tree)

        bar = QHBoxLayout()
        self.inp_kw = QLineEdit(); self.inp_kw.setPlaceholderText("Tìm FTS5 không dấu (VD: tich phan, cap so cong)...")
        self.inp_id = QLineEdit(); self.inp_id.setPlaceholderText("Lọc ID (VD: 1D2*)")
        self.cb_qt = QComboBox(); self.cb_qt.addItems(["", "TN", "DS", "KQ", "TL"])
        bar.addWidget(self.inp_kw, stretch=2); bar.addWidget(self.inp_id, stretch=1); bar.addWidget(self.cb_qt)
        for lbl, fn in [
            ("Tìm", self._refresh_bank), ("Nhập .tex", self._import_tex), ("Xóa câu", self._delete_selected),
            ("Rà soát CV 1239", self._audit_qs), ("Tìm gần trùng", self._find_similar),
            ("Trình chiếu F11", self._present), ("Tra cứu ID6", self._open_id6),
        ]:
            b = QPushButton(lbl); b.clicked.connect(fn); bar.addWidget(b)
        rv.addLayout(bar)

        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["DB ID", "Mã ID6", "Loại", "Đã dùng", "Trích nội dung"])
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl.cellClicked.connect(self._on_row)
        self.lbl_id = QLabel("Chọn 1 câu để xem giải nghĩa ID6.")
        self.txt_tex = QPlainTextEdit(); self.txt_tex.setReadOnly(True)
        rv.addWidget(self.tbl, stretch=2); rv.addWidget(self.lbl_id); rv.addWidget(self.txt_tex, stretch=1)
        sp.addWidget(left); sp.addWidget(right); sp.setSizes([230, 1050])
        lay.addWidget(sp)
        cau_hoi_tabs = QTabWidget()
        self.cau_hoi_mylt = CauHoiMyLT2026Tab(self.db)
        cau_hoi_tabs.addTab(self.cau_hoi_mylt, "Quản lý câu hỏi (MyLT 2026)")
        cau_hoi_tabs.addTab(tab, "Kho nâng cao (Cây thư mục · FTS5 · F11)")
        self.tabs.addTab(cau_hoi_tabs, "Câu hỏi")

    # ==========================================================================
    # TAB 3: MA TRẬN (CV 7991 Excel/Word, Tạo ma trận ngược)
    # ==========================================================================
    def _build_tab_3_ma_tran(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        hb = QHBoxLayout()
        for lbl, fn in [
            ("Nạp Ma trận Excel (.xlsx)", self._load_matrix_xlsx),
            ("Tạo Ma trận ngược từ Kho", self._export_reverse_matrix),
            ("Xuất Phụ lục 1 & 2 CV 7991 (.xlsx / .docx)", self._export_cv7991_docs),
        ]:
            b = QPushButton(lbl); b.clicked.connect(fn); hb.addWidget(b)
        hb.addStretch()
        lay.addLayout(hb)
        self.txt_matrix_log = QPlainTextEdit(); self.txt_matrix_log.setReadOnly(True)
        lay.addWidget(self.txt_matrix_log)
        self.tabs.addTab(tab, "Ma trận")

    # ==========================================================================
    # TAB 4: TIỆN ÍCH (Word 2 chiều, AI OCR PDF, Trạm AI, Moodle, GAS, LAN, Chuyên đề)
    # ==========================================================================
    def _build_tab_4_tien_ich(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        sub = QTabWidget()

        # Sub 1: Word & OCR PDF
        w_conv = QWidget(); vc = QVBoxLayout(w_conv)
        hc = QHBoxLayout()
        for lbl, fn in [("Nhập Word (.docx) → Kho", self._imp_word), ("Xuất câu đang lọc → Word (.docx)", self._exp_word), ("AI OCR PDF (cụm 10 trang) → ex_test", self._run_ocr)]:
            b = QPushButton(lbl); b.clicked.connect(fn); hc.addWidget(b)
        hc.addStretch(); vc.addLayout(hc)
        self.txt_ocr_out = QPlainTextEdit(); vc.addWidget(self.txt_ocr_out)
        sub.addTab(TienIch1Panel(self), "Tiện ích 1")
        sub.addTab(TienIch2Tab(), "Tiện ích 2")
        sub.addTab(w_conv, "Word ↔ LaTeX & AI OCR PDF")

        # Sub 2: Moodle, GAS Online, Đấu trường LAN & Xem PDF
        w_on = QWidget(); vo = QVBoxLayout(w_on)
        ho = QHBoxLayout()
        self.b_arena = QPushButton("Khởi chạy Đấu trường LAN (SSE)")
        self.b_arena.clicked.connect(self._toggle_arena)
        for lbl, fn in [("Xuất Moodle XML (MathJax + Cloze)", self._exp_moodle), ("Xuất Thi Online GAS (Code.gs)", self._exp_gas), ("Xem trước PDF (chống xé hình)", self._preview_pdf)]:
            b = QPushButton(lbl); b.clicked.connect(fn); ho.addWidget(b)
        ho.insertWidget(2, self.b_arena); ho.addStretch(); vo.addLayout(ho)
        self.lbl_arena = QLabel("Đấu trường LAN: Đang tắt.")
        self.lbl_pdf = QLabel("Khung xem trước trang PDF."); self.lbl_pdf.setAlignment(Qt.AlignCenter)
        vo.addWidget(self.lbl_arena); vo.addWidget(self.lbl_pdf, stretch=1)
        sub.addTab(w_on, "Moodle · Online GAS · Đấu trường LAN")

        # Sub 3: Biên soạn Chuyên đề có mục lục
        sub.addTab(TopicBookTab(self.db), "Biên soạn Chuyên đề (.tex / PDF)")

        # Sub 4: Trạm AI (Gán ID6, Sinh câu tương tự, Chấm tự luận)
        sub.addTab(AIStationTab(self.db, self._get_ai_config), "Trạm AI (Gán ID · Sinh câu · Chấm TL)")
        sub.addTab(MyLT2025SuiteTab(self.db), "Phiếu 2025 · Tikz2Pic · Blogger · Config")

        lay.addWidget(sub)
        self.tabs.addTab(tab, "Tiện ích")

    # ==========================================================================
    # TAB 5, 6, 7, 8: BỐN CÔNG CỤ TOÁN HỌC TIKZ TÁCH RIÊNG NHƯ MYLT 2026
    # ==========================================================================
    def _make_tikz_workspace(self, form_widget: QWidget, gen_fn):
        w = QWidget()
        lay = QHBoxLayout(w)
        left, right = QVBoxLayout(), QVBoxLayout()
        code_box = QPlainTextEdit()
        img_lbl = QLabel("Khung xem trước hình TikZ sau khi biên dịch.")
        img_lbl.setAlignment(Qt.AlignCenter); img_lbl.setMinimumWidth(420)
        b_gen = QPushButton("Sinh mã TikZ")
        b_prev = QPushButton("Biên dịch xem trước")
        b_gen.clicked.connect(lambda: code_box.setPlainText(gen_fn()))
        b_prev.clicked.connect(lambda: self._compile_tikz_preview(code_box, img_lbl, gen_fn))
        hb = QHBoxLayout(); hb.addWidget(b_gen); hb.addWidget(b_prev)
        left.addWidget(form_widget); left.addLayout(hb); left.addWidget(code_box, stretch=1)
        right.addWidget(img_lbl, stretch=1)
        lay.addLayout(left, stretch=3); lay.addLayout(right, stretch=2)
        return w

    def _compile_tikz_preview(self, code_box: QPlainTextEdit, img_lbl: QLabel, gen_fn):
        code = code_box.toPlainText().strip() or gen_fn()
        code_box.setPlainText(code)
        tmp_dir = Path(tempfile.mkdtemp(prefix="tikz_prev_"))
        tex_f = tmp_dir / "fig.tex"
        tex_f.write_text(r"\documentclass[border=4pt]{standalone}\usepackage{amsmath,amssymb,tikz,tkz-tab}\usetikzlibrary{calc,patterns}\begin{document}" + "\n" + code + "\n\\end{document}\n", encoding="utf-8")
        img_lbl.setText("Đang biên dịch hình TikZ...")

        def _done(res):
            if res.success and res.pdf_path:
                qimg, _ = make_qimage_from_pdf_page(res.pdf_path, 0, 2.0)
                img_lbl.setPixmap(QPixmap.fromImage(qimg).scaled(img_lbl.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                img_lbl.setText("Lỗi biên dịch TikZ:\n" + "\n".join(d.summary for d in res.diagnostics))

        run_in_background(compile_tex_to_pdf, str(tex_f), on_finished=_done, on_error=lambda e: img_lbl.setText(e))

    def _build_tab_5_ve_hinh(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.s_type = QComboBox(); self.s_type.addItems(["pyramid_sabcd_perp", "pyramid_sabc_perp", "prism_triangular"])
        self.s_h = QDoubleSpinBox(); self.s_h.setRange(1, 10); self.s_h.setValue(3.5)
        self.s_w = QDoubleSpinBox(); self.s_w.setRange(1, 10); self.s_w.setValue(4.2)
        f.addRow("Loại khối 3D:", self.s_type); f.addRow("Chiều cao:", self.s_h); f.addRow("Độ rộng đáy:", self.s_w)
        self.tabs.addTab(VeHinhMyLT2026Tab(), "Vẽ hình")

    def _build_tab_6_do_thi(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.g_expr = QLineEdit("(\\x+1)/(\\x-1)")
        self.g_xmin = QDoubleSpinBox(); self.g_xmin.setRange(-20, 20); self.g_xmin.setValue(-4)
        self.g_xmax = QDoubleSpinBox(); self.g_xmax.setRange(-20, 20); self.g_xmax.setValue(5)
        self.g_ax = QLineEdit("1"); self.g_ay = QLineEdit("1"); self.g_sh = QLineEdit("2, 4")
        f.addRow("Biểu thức (dùng \\x):", self.g_expr); f.addRow("x min:", self.g_xmin); f.addRow("x max:", self.g_xmax)
        f.addRow("Tiệm cận đứng x =:", self.g_ax); f.addRow("Tiệm cận ngang/xiên y =:", self.g_ay); f.addRow("Tô miền tích phân [a, b]:", self.g_sh)
        gen = lambda: generate_function_graph_tikz(
            self.g_expr.text(), xmin=self.g_xmin.value(), xmax=self.g_xmax.value(),
            asymptote_x=(float(self.g_ax.text()) if self.g_ax.text().strip() else None),
            asymptote_y_expr=(self.g_ay.text().strip() or None),
            shade_integral=(tuple(float(x.strip()) for x in self.g_sh.text().split(",", 1)) if "," in self.g_sh.text() else None),
        )
        self.tabs.addTab(DoThiMyLT2026Tab(), "Đồ thị")

    def _build_tab_7_bbt_xd(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.b_x = QLineEdit(r"$-\infty$, $0$, $2$, $+\infty$")
        self.b_yp = QLineEdit(r", +, 0, -, 0, +, ")
        self.b_y = QLineEdit(r"-/$-\infty$, +/$4$, -/$0$, +/$+\infty$")
        f.addRow("Dòng x:", self.b_x); f.addRow("Dòng y' (tkzTabLine):", self.b_yp); f.addRow("Dòng y (tkzTabVar):", self.b_y)
        gen = lambda: generate_variation_table_tikz([x.strip() for x in self.b_x.text().split(",")], [x.strip() for x in self.b_yp.text().split(",")], [x.strip() for x in self.b_y.text().split(",")])
        self.tabs.addTab(BBTXDMyLT2026Tab(), "BBT&XD")

    def _build_tab_8_bieu_dien_nghiem(self):
        fw = QWidget(); f = QFormLayout(fw)
        self.n_iv = QLineEdit("-2, 3")
        self.n_ineq = QLineEdit("1,1,2,<=; 1,0,0,>=")
        f.addRow("Khoảng trục số [a, b):", self.n_iv); f.addRow("Hệ BPT (a,b,c,op cách ';'):", self.n_ineq)

        def _gen():
            a, b = [float(x.strip()) for x in self.n_iv.text().split(",", 1)]
            ineqs = [(float(p[0]), float(p[1]), float(p[2]), p[3].strip()) for s in self.n_ineq.text().split(";") if s.strip() for p in [s.split(",")]]
            return generate_number_line_tikz([IntervalSpec(a, b, True, False)]) + "\n\n" + generate_linear_inequality_region_tikz(ineqs)

        self.tabs.addTab(BieuDienNghiemMyLT2026Tab(), "Biểu diễn nghiệm")

    # ==========================================================================
    # TAB 9: SOẠN THẢO (Soạn ex_test nhanh + biên dịch PDF + chẩn đoán .log)
    # ==========================================================================
    def _build_tab_9_soan_thao(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        hb = QHBoxLayout()
        for lbl, snip in [
            ("+ Câu TN", "\\begin{ex}\nNội dung câu hỏi\n\\choice[4]\n{\\True Đáp án A}\n{Đáp án B}\n{Đáp án C}\n{Đáp án D}\n\\loigiai{\nLời giải.\n}\n\\end{ex}\n"),
            ("+ Câu Đ/S", "\\begin{ex}\nNội dung câu hỏi\n\\choiceTF[1t]\n{\\True Mệnh đề a}\n{Mệnh đề b}\n{\\True Mệnh đề c}\n{Mệnh đề d}\n\\loigiai{\n\\begin{itemchoice}\n\\itemch Đúng.\n\\itemch Sai.\n\\itemch Đúng.\n\\itemch Sai.\n\\end{itemchoice}\n}\n\\end{ex}\n"),
            ("+ Câu TLN", "\\begin{ex}\nNội dung câu hỏi\n\\shortans[oly]{$1{,}5$}\n\\loigiai{\nLời giải.\n}\n\\end{ex}\n"),
        ]:
            b = QPushButton(lbl); b.clicked.connect(lambda _=False, s=snip: self.txt_editor.insertPlainText(s)); hb.addWidget(b)
        b_save_bank = QPushButton("Lưu vào Ngân hàng")
        b_save_bank.clicked.connect(self._save_editor_to_bank)
        b_comp = QPushButton("Biên dịch PDF & Chẩn đoán .log")
        b_comp.clicked.connect(self._compile_pdf)
        hb.addWidget(b_save_bank); hb.addWidget(b_comp); hb.addStretch()
        lay.addLayout(hb)
        self.txt_editor = QPlainTextEdit()
        lay.addWidget(self.txt_editor, stretch=1)
        self.tabs.addTab(SoanThaoMyLT2026Tab(tab), "Soạn thảo")

    # ==========================================================================
    # TAB 10: THÔNG TIN (Cài đặt AI đa nền tảng & Hệ thống)
    # ==========================================================================
    def _build_tab_10_thong_tin(self):
        tab = QWidget()
        f = QFormLayout(tab)
        self.cb_prov = QComboBox(); self.cb_prov.addItems(["gemini", "openai", "claude", "deepseek", "grok"])
        self.inp_key = QLineEdit(); self.inp_key.setEchoMode(QLineEdit.Password)
        self.inp_model = QLineEdit("gemini-2.5-flash")
        self.sp_think = QSpinBox(); self.sp_think.setRange(0, 24576); self.sp_think.setValue(0); self.sp_think.setSpecialValueText("Mặc định (tự động)")
        f.addRow("Phiên bản:", QLabel("toan11 v1.0 — Bố cục MyLT 2026 (GDPT 2018 · CV 7991 · CV 1239)"))
        f.addRow("Nhà cung cấp AI:", self.cb_prov)
        f.addRow("API Key:", self.inp_key)
        f.addRow("Model:", self.inp_model)
        f.addRow("Ngân sách suy luận (thinking_budget):", self.sp_think)
        f.addRow("Trình biên dịch TeX:", QLabel(detect_tex_compiler() or "Chưa phát hiện MiKTeX / TeX Live"))
        f.addRow("Cơ sở dữ liệu FTS5:", QLabel(self.db.db_path))
        self.tabs.addTab(tab, "Thông tin")

    # ==========================================================================
    # NGHIỆP VỤ BẢNG CHỌN ID & TẠO ĐỀ
    # ==========================================================================
    def _refresh_id_matrix_table(self):
        rows = self.db.search(id_glob=self.inp_id_filter.text().strip(), limit=5000)
        groups: dict[tuple[str, str], dict] = {}
        for r in rows:
            qid = r["qid"] or "CHUA_ID"
            qtype = r["qtype"]
            lop = r["lop"] or ""
            mon = r["mon"] or ""
            chuong = r["chuong"] or ""
            md = r["muc_do"] or "N"
            # Lọc nhanh
            if self.cb_id_lop.currentIndex() > 0:
                want_lop = self.cb_id_lop.currentText().split()[0]
                if lop != want_lop:
                    continue
            if self.cb_id_mon.currentIndex() > 0 and mon != self.cb_id_mon.currentText():
                continue
            if self.cb_id_loai.currentIndex() > 0 and qtype != self.cb_id_loai.currentText():
                continue
            key = (qid, qtype)
            if key not in groups:
                groups[key] = {
                    "qid": qid, "lop": lop, "mon": mon, "chuong": chuong,
                    "desc": describe_id6(qid) if qid != "CHUA_ID" else "Chưa gắn mã ID",
                    "qtype": qtype, "counts": defaultdict(int),
                }
            groups[key]["counts"][md] += 1

        self._id_groups = list(groups.values())
        self.tbl_id_pick.blockSignals(True)
        self.tbl_id_pick.setRowCount(len(self._id_groups))
        for ri, g in enumerate(self._id_groups):
            c = g["counts"]
            tot = sum(c.values())
            vals = [
                str(ri + 1), g["qid"], g["lop"], g["mon"], g["chuong"], g["desc"], g["qtype"],
                f"{c['N']}/{c['H']}/{c['V']}/{c['C']}", "0", "0", "0", "0", str(tot), "0",
            ]
            for ci, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if ci not in (8, 9, 10, 11):
                    it.setFlags(it.flags() & ~Qt.ItemIsEditable)
                it.setTextAlignment(Qt.AlignCenter if ci != 5 else Qt.AlignVCenter | Qt.AlignLeft)
                self.tbl_id_pick.setItem(ri, ci, it)
        self.tbl_id_pick.blockSignals(False)
        self._recalc_id_pick_totals()

    def _recalc_id_pick_totals(self):
        self.tbl_id_pick.blockSignals(True)
        grand = 0
        for ri in range(self.tbl_id_pick.rowCount()):
            row_sum = 0
            for ci in (8, 9, 10, 11):
                it = self.tbl_id_pick.item(ri, ci)
                try:
                    row_sum += max(0, int(it.text())) if it else 0
                except ValueError:
                    pass
            self.tbl_id_pick.setItem(ri, 13, QTableWidgetItem(str(row_sum)))
            grand += row_sum
        self.tbl_id_pick.blockSignals(False)
        self.lbl_picked_summary.setText(f"Đã chọn: {grand} câu")

    def _quick_pick_to_table(self):
        want = self.sp_fast_count.value()
        for ri in range(self.tbl_id_pick.rowCount()):
            g = self._id_groups[ri]
            for ci, md in [(8, "N"), (9, "H"), (10, "V"), (11, "C")]:
                if g["counts"][md] > 0:
                    self.tbl_id_pick.setItem(ri, ci, QTableWidgetItem(str(min(want, g["counts"][md]))))
        self._recalc_id_pick_totals()

    def _pick_all_available(self):
        for ri, g in enumerate(self._id_groups):
            for ci, md in [(8, "N"), (9, "H"), (10, "V"), (11, "C")]:
                self.tbl_id_pick.setItem(ri, ci, QTableWidgetItem(str(g["counts"][md])))
        self._recalc_id_pick_totals()

    def _clear_all_picked(self):
        for ri in range(self.tbl_id_pick.rowCount()):
            for ci in (8, 9, 10, 11):
                self.tbl_id_pick.setItem(ri, ci, QTableWidgetItem("0"))
        self._recalc_id_pick_totals()

    def _collect_rules_from_id_table(self) -> list[MatrixRule]:
        rules: list[MatrixRule] = []
        for ri, g in enumerate(self._id_groups):
            for ci, md in [(8, "N"), (9, "H"), (10, "V"), (11, "C")]:
                it = self.tbl_id_pick.item(ri, ci)
                try:
                    cnt = int(it.text()) if it else 0
                except ValueError:
                    cnt = 0
                if cnt > 0:
                    rules.append(MatrixRule(g["qtype"], cnt, g["qid"] if g["qid"] != "CHUA_ID" else "*", md, topic=g["desc"]))
        return rules

    def _create_and_export_exam(self):
        """Nút Tạo đề ở góc dưới phải — hoạt động thống nhất cho mọi chế độ."""
        try:
            opts = self.tuy_chon_panel.get_options() if hasattr(self, "tuy_chon_panel") else {}
            n_exams = opts.get("num_exams", self.sp_n.value())
            c_digits = opts.get("code_digits", 4)
            start_c = 101 if c_digits == 3 else 1001
            bal_abcd = opts.get("balance_abcd", self.chk_balance.isChecked())
            sort_lv = opts.get("sort_by_level", self.chk_sort_level.isChecked())
            exam_title = opts.get("title", self.inp_title.text())

            if self.rb_from_files.isChecked() and self.source_file_questions:
                self.last_variants = generate_exam_batch(
                    n_exams, self.sp_seed.value(), base_questions=self.source_file_questions,
                    code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                )
            else:
                rules = self._collect_rules_from_id_table()
                if rules:
                    mat = ExamMatrix(exam_title, rules=rules)
                    self.loaded_matrix = mat
                    self.last_variants = generate_exam_batch(
                        n_exams, self.sp_seed.value(), db=self.db, matrix=mat,
                        code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                    )
                elif self.loaded_matrix is not None:
                    self.last_variants = generate_exam_batch(
                        n_exams, self.sp_seed.value(), db=self.db, matrix=self.loaded_matrix,
                        code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                    )
                elif self.current_questions:
                    self.last_variants = generate_exam_batch(
                        n_exams, self.sp_seed.value(), base_questions=self.current_questions,
                        code_digits=c_digits, start_code=start_c, balance_abcd=bal_abcd, sort_by_level=sort_lv,
                    )
                else:
                    QMessageBox.warning(self, "Tạo đề", "Kho đang trống. Hãy bấm 'Nạp mẫu Toán 11' hoặc 'Nhập câu hỏi' trước.")
                    return

            d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất trọn bộ đề thi")
            if not d:
                return
            tpl = resource_path("nganhangde/templates/de_thi.tex")
            embed_qr = opts.get("embed_qr", False) or self.chk_qr.isChecked()
            tres = export_exam_tex_suite(self.last_variants, d, exam_title, str(tpl) if tpl.exists() else None, embed_qr_in_solution=embed_qr)

            # Tự động nhúng Phiếu TLTN 2025 nếu người dùng chọn
            phieu_mode = opts.get("phieu_mode", "")
            if "2025" in phieu_mode:
                pkey = "full" if "2 trang" in phieu_mode else "1mat"
                for fp_str in tres.created_files:
                    fp = Path(fp_str)
                    if fp.suffix.lower() == ".tex" and "loi_giai" not in fp.stem.lower():
                        try:
                            updated = inject_phieu_into_tex(fp.read_text(encoding="utf-8", errors="replace"), template_key=pkey, copy_to_dir=fp.parent)
                            fp.write_text(updated, encoding="utf-8")
                        except Exception:
                            pass

            # Tự động biên dịch PDF nếu tick "Biên dịch đề"
            compiled_pdfs = 0
            if opts.get("compile_pdf", False):
                for fp_str in tres.created_files:
                    fp = Path(fp_str)
                    if fp.suffix.lower() == ".tex":
                        bres = compile_tex_to_pdf(str(fp), compiler="pdflatex", passes=1)
                        if bres.success:
                            compiled_pdfs += 1
            export_answer_csv_bom(self.last_variants, os.path.join(d, "dap_an_utf8_bom.csv"))
            ow = export_omr_excel(self.last_variants, os.path.join(d, "dap_an_omr_2025.xlsx"), self.inp_title.text(), self.cb_omr.currentData(), template_xlsx=self.custom_omr_template)
            mat_out = self.loaded_matrix or ExamMatrix.from_exam_questions(self.last_variants[0].questions, self.inp_title.text())
            export_cv7991_excel(mat_out, os.path.join(d, "ma_tran_dac_ta_cv7991.xlsx"))
            try:
                export_cv7991_docx(mat_out, os.path.join(d, "ma_tran_dac_ta_cv7991.docx"))
            except RuntimeError:
                pass
            record_exam_batch(self.db, self.inp_title.text(), self.sp_seed.value(), self.last_variants, mat_out)
            self._refresh_bank()
            self.lbl_status_global.setText(f"Đã xuất {len(self.last_variants)} mã đề tại: {d}")
            QMessageBox.information(self, "Tạo đề thành công", f"Đã xuất {len(tres.created_files)} tệp (.tex, OMR, CSV BOM, Ma trận & Đặc tả CV 7991) và biên dịch {compiled_pdfs} tệp PDF vào:\n{d}" + ("\n\nCảnh báo:\n- " + "\n- ".join(tres.warnings + ow) if (tres.warnings or ow) else ""))
        except Exception as exc:
            QMessageBox.warning(self, "Lỗi tạo đề", str(exc))

    # ==========================================================================
    # CÁC HÀM HỖ TRỢ KHÁC
    # ==========================================================================
    def _open_bank_db(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở kho SQLite (.db)", "", "SQLite DB (*.db)")
        if p:
            self.db.close()
            self.db = QuestionBankDB(p)
            self._refresh_bank(); self._refresh_tree(); self._refresh_id_matrix_table()
            self.lbl_status_global.setText(f"Đang mở kho: {p}")

    def _pick_source_tex_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex nguồn", "", "LaTeX (*.tex)")
        if not paths:
            return
        self.rb_from_files.setChecked(True)
        self.source_file_questions = []
        for p in paths:
            self.source_file_questions.extend(parse_tex_questions(Path(p).read_text(encoding="utf-8", errors="ignore"), auto_normalize=True))
        self.txt_file_list.setPlainText("\n".join(paths) + f"\n\n==> Tổng cộng: {len(self.source_file_questions)} câu hỏi sẵn sàng trộn.")
        self.lbl_status_global.setText(f"Đã nạp {len(self.source_file_questions)} câu từ {len(paths)} file .tex.")

    def _build_similar_from_tex(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn đề gốc .tex", "", "LaTeX (*.tex)")
        if not p:
            return
        qs = parse_tex_questions(Path(p).read_text(encoding="utf-8", errors="ignore"))
        self.loaded_matrix = ExamMatrix.from_exam_questions(qs, f"Tương tự {Path(p).stem}")
        self.txt_sim_log.setPlainText(f"Đã phân tích {len(qs)} câu từ {Path(p).name}.\nCơ cấu rút đề tương tự: {self.loaded_matrix.total_by_type()}\nBấm nút 'Tạo đề' bên dưới để rút đề tương tự từ kho.")

    def _refresh_tree(self):
        nodes = self.db.list_workspace_nodes()
        if not nodes:
            rid = self.db.add_workspace_node("Năm học 2026–2027")
            self.db.add_workspace_node("Lớp 11 / Học kì I", parent_id=rid)
            nodes = self.db.list_workspace_nodes()
        self.tree.load_nodes(nodes)

    def _on_tree_act(self, key: str, nid: int):
        if key == "delete_node":
            self.db.delete_workspace_node(nid); self._refresh_tree()
        elif key == "open_view":
            bs = list_exam_batches(self.db, limit=10)
            msg = "\n".join(f"- {b['name']} ({len(b['codes'])} mã đề, {b['question_count']} câu)" for b in bs)
            QMessageBox.information(self, "Lịch sử đợt ra đề", msg or "Chưa có đợt ra đề nào.")

    def _refresh_bank(self):
        rows = self.db.search(self.inp_kw.text(), self.inp_id.text(), self.cb_qt.currentText(), limit=400)
        self.current_questions = []
        self.tbl.setRowCount(len(rows))
        self.tbl_manual.setRowCount(len(rows))
        for ri, row in enumerate(rows):
            ps = parse_tex_questions(row["raw"])
            if ps:
                self.current_questions.append(ps[0])
            stem_short = (row["stem"] or "")[:100].replace("\n", " ")
            for ci, v in enumerate([str(row["id"]), row["qid"], row["qtype"], str(row["used_count"]), stem_short]):
                self.tbl.setItem(ri, ci, QTableWidgetItem(v))
            chk = QTableWidgetItem(); chk.setCheckState(Qt.Checked)
            self.tbl_manual.setItem(ri, 0, chk)
            for ci, v in enumerate([row["qid"], row["qtype"], str(row["used_count"]), stem_short], 1):
                self.tbl_manual.setItem(ri, ci, QTableWidgetItem(v))

    def _on_row(self, ri: int, _ci: int):
        if 0 <= ri < len(self.current_questions):
            q = self.current_questions[ri]
            self.lbl_id.setText(describe_id6(q.primary_id) if q.primary_id else "Chưa gắn mã ID6")
            self.txt_tex.setPlainText(q.to_latex(True))

    def _import_tex(self):
        from .import_bank_dialog import ImportBankDialog
        dlg = ImportBankDialog(self.db, self)
        dlg.exec()
        if dlg.imported_count > 0:
            self._refresh_bank()
            self._refresh_id_matrix_table()
            if hasattr(self, "cau_hoi_mylt") and self.cau_hoi_mylt.rb_bank.isChecked():
                self.cau_hoi_mylt._load_questions()

    def _load_sample(self):
        sp = resource_path("sample_data/de_mau_toan11_2026.tex")
        if not sp.exists():
            QMessageBox.warning(self, "Dữ liệu mẫu", "Không tìm thấy sample_data/de_mau_toan11_2026.tex.")
            return
        st = self.db.bulk_import(parse_tex_questions(sp.read_text(encoding="utf-8"), auto_normalize=True), asset_base_dir=str(sp.parent))
        self._refresh_bank(); self._refresh_id_matrix_table()
        QMessageBox.information(self, "Nạp mẫu Toán 11", f"Đã nạp {st['added']} câu mẫu (trùng bỏ qua: {st['duplicates']}).")

    def _delete_selected(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.db.delete_question(int(self.tbl.item(r, 0).text()))
            self._refresh_bank(); self._refresh_id_matrix_table()

    def _audit_qs(self):
        out = [f"Câu {i} [{q.primary_id}] ({iss.level}): {iss.message}" for i, q in enumerate(self.current_questions, 1) for iss in audit_question(q)]
        QMessageBox.information(self, "Rà soát CV 1239", "\n".join(out[:80]) if out else "Tất cả câu hỏi đang lọc đều hợp lệ!")

    def _find_similar(self):
        r = self.tbl.currentRow()
        if not (0 <= r < len(self.current_questions)):
            return
        q = self.current_questions[r]
        cands = [{"qid": x.primary_id, "stem": x.stem} for i, x in enumerate(self.current_questions) if i != r]
        hits = find_similar_questions(q.stem, cands, threshold=0.3)
        msg = "\n".join(f"- Tương đồng {score:.0%} [{it['qid']}]: {it['stem'][:80]}" for score, it in hits)
        QMessageBox.information(self, "Tìm câu gần trùng", msg or "Không có câu nào tương đồng ≥ 30%.")

    def _present(self):
        if self.current_questions:
            PresentationDialog(self.current_questions, max(0, self.tbl.currentRow()), self).exec()

    def _open_id6(self):
        out = str(user_data_dir() / "tra_cuu_id6_gdpt2018.html")
        export_id6_lookup_html(out)
        webbrowser.open(Path(out).as_uri())

    def _load_matrix_xlsx(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn Ma trận Excel", "", "Excel (*.xlsx)")
        if p:
            self.loaded_matrix = ExamMatrix.load_from_excel(p, name=Path(p).stem)
            ws = self.loaded_matrix.validate_cv7991()
            self.txt_matrix_log.setPlainText(f"Đã nạp '{self.loaded_matrix.name}': {self.loaded_matrix.total_by_type()}\n" + ("\n".join(ws) if ws else "Đạt chuẩn CV 7991."))

    def _export_reverse_matrix(self):
        if not self.current_questions:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu Ma trận ngược", "ma_tran_nguoc.xlsx", "Excel (*.xlsx)")
        if p:
            ExamMatrix.from_exam_questions(self.current_questions, self.inp_title.text()).save_to_excel(p)
            self.txt_matrix_log.appendPlainText(f"Đã lưu ma trận ngược tại: {p}")

    def _export_cv7991_docs(self):
        mat = self.loaded_matrix or (ExamMatrix.from_exam_questions(self.current_questions, self.inp_title.text()) if self.current_questions else None)
        if not mat:
            return
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu Phụ lục 1 & 2 CV 7991")
        if d:
            export_cv7991_excel(mat, os.path.join(d, "ma_tran_dac_ta_cv7991.xlsx"))
            try:
                export_cv7991_docx(mat, os.path.join(d, "ma_tran_dac_ta_cv7991.docx"))
            except RuntimeError:
                pass
            self.txt_matrix_log.appendPlainText(f"Đã xuất Phụ lục 1 & 2 CV 7991 tại: {d}")

    def _pick_omr_template(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file mẫu OMR Excel", "", "Excel (*.xlsx)")
        if p:
            self.custom_omr_template = p
            self.lbl_status_global.setText(f"Mẫu OMR riêng: {os.path.basename(p)}")

    def _save_editor_to_bank(self):
        qs = parse_tex_questions(self.txt_editor.toPlainText(), auto_normalize=True)
        if qs:
            st = self.db.bulk_import(qs)
            self._refresh_bank(); self._refresh_id_matrix_table()
            QMessageBox.information(self, "Soạn thảo", f"Đã lưu {st['added']} câu vào kho (trùng: {st['duplicates']}).")

    def _compile_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp .tex biên dịch", "", "LaTeX (*.tex)")
        if p:
            self.lbl_status_global.setText(f"Đang biên dịch nền: {os.path.basename(p)}...")
            run_in_background(
                compile_tex_to_pdf, p,
                on_finished=lambda r: QMessageBox.information(self, "Biên dịch PDF", f"THÀNH CÔNG: {r.pdf_path}" if r.success else "LỖI:\n" + "\n".join(f"- Dòng {d.line_no}: {d.summary} -> {d.suggestion_vi}" for d in r.diagnostics)),
                on_error=lambda e: QMessageBox.warning(self, "Lỗi biên dịch", e),
            )

    def _imp_word(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp Word", "", "Word (*.docx)")
        if p:
            qs, tr = convert_docx_to_questions(p)
            st = self.db.bulk_import(qs)
            self._refresh_bank(); self._refresh_id_matrix_table()
            QMessageBox.information(self, "Nhập Word", f"Thêm: {st['added']} | OMML={tr.omml_count}, MathType OLE={tr.mathtype_ole_count}, Ảnh={tr.media_image_count}")

    def _exp_word(self):
        if not self.current_questions:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu Word", "de_xuat.docx", "Word (*.docx)")
        if p:
            rep = export_questions_to_docx(self.current_questions, p, self.inp_title.text())
            QMessageBox.information(self, "Xuất Word", f"Xong! Công thức OMML: {rep.direct_omml}/{rep.total_equations}")

    def _run_ocr(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn PDF đề thi", "", "PDF (*.pdf)")
        if p:
            self.txt_ocr_out.setPlainText("Đang OCR cụm 10 trang trên luồng nền...")
            run_in_background(ocr_pdf_to_extest, p, self._get_ai_config(), on_finished=lambda r: self.txt_ocr_out.setPlainText(r.full_tex), on_error=lambda e: self.txt_ocr_out.setPlainText(e))

    def _exp_moodle(self):
        if not self.current_questions:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Lưu Moodle XML", "moodle_quiz.xml", "XML (*.xml)")
        if p:
            export_moodle_xml(self.current_questions, p)
            QMessageBox.information(self, "Moodle XML", f"Đã xuất tại: {p}")

    def _exp_gas(self):
        if not self.last_variants and self.current_questions:
            self.last_variants = generate_exam_batch(1, self.sp_seed.value(), base_questions=self.current_questions)
        if not self.last_variants:
            return
        d = QFileDialog.getExistingDirectory(self, "Chọn thư mục xuất gói GAS Online")
        if d:
            b = export_online_exam_bundle(self.last_variants[0], d, server_only_key=True)
            QMessageBox.information(self, "Thi Online GAS", f"Đã xuất Code.gs + ExamClient.html tại:\n{d}\nThư mục Drive: {b['folder_id']}")

    def _toggle_arena(self):
        if self.arena_server:
            self.arena_server.stop(); self.arena_server = None
            self.b_arena.setText("Khởi chạy Đấu trường LAN (SSE)")
            self.lbl_arena.setText("Đấu trường LAN: Đang tắt.")
            return
        if not self.last_variants and self.current_questions:
            self.last_variants = generate_exam_batch(1, self.sp_seed.value(), base_questions=self.current_questions)
        if not self.last_variants:
            return
        self.arena_server = LanArenaServer(self.last_variants[0], "0.0.0.0", 8765)
        _, port = self.arena_server.start()
        ip = detect_lan_ip()
        self.b_arena.setText("Dừng Đấu trường LAN")
        self.lbl_arena.setText(f"ĐANG CHẠY — Học sinh: http://{ip}:{port}/ | Xếp hạng SSE: http://{ip}:{port}/host")
        webbrowser.open(f"http://127.0.0.1:{port}/host")

    def _preview_pdf(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn PDF xem trước", "", "PDF (*.pdf)")
        if p:
            qimg, tot = make_qimage_from_pdf_page(p, 0, 1.4)
            self.lbl_pdf.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl_pdf.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.lbl_arena.setText(f"Xem trước trang 1/{tot}: {os.path.basename(p)}")


def main(argv: list[str] | None = None) -> int:
    app = QApplication(argv or sys.argv)
    app.setStyle("Fusion")
    win = MyLT2026MainWindow()
    win.show()
    return app.exec()
