"""Cửa sổ Câu hỏi chuẩn bố cục & chức năng MyLT 2026 v1.0.3.44, tích hợp biên dịch PDF."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import tempfile
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ..paths import resource_path
from ..core.parser import parse_tex_questions, read_tex_with_inputs
from ..converters.mylt_bank_importer import import_mylt_into_db, convert_mylt_to_tex
from ..core.map_id_loader import load_map_id_file, MapIDTree
from ..core.config_manager import ConfigManager
from ..exporters.pdfbuild import compile_tex_to_pdf, open_pdf_file


ID_RE = re.compile(r"%\[([0-9A-Za-z\-]+)\]")


@dataclass
class QuestionItemRow:
    db_id: int | None
    raw_tex: str
    preview: str
    id1: str
    id2: str
    qtype: str
    source_file: str = ""


class _EditQuestionDialog(QDialog):
    def __init__(self, title: str, tex: str, readonly: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(760, 520)
        lay = QVBoxLayout(self)
        self.ed = QPlainTextEdit(tex)
        self.ed.setReadOnly(readonly)
        lay.addWidget(self.ed, 1)
        btns = QDialogButtonBox(QDialogButtonBox.Ok if readonly else (QDialogButtonBox.Save | QDialogButtonBox.Cancel))
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    def value(self) -> str:
        return self.ed.toPlainText()


class CauHoiMyLT2026Tab(QWidget):
    PAGE_SIZE = 50

    def __init__(self, db=None, parent=None):
        super().__init__(parent)
        self.db = db
        self.cfg = ConfigManager()
        self.source_files: list[Path] = []
        self.all_items: list[QuestionItemRow] = []
        self.filtered_items: list[QuestionItemRow] = []
        self.current_page: int = 1
        self.map_tree: MapIDTree | None = None
        self._load_map_tree("Map ID_3Sach.tex")
        self._build_ui()

    def _load_map_tree(self, filename: str):
        p = resource_path(f"nganhangde/templates/map_id/{filename}")
        if p.exists():
            try:
                self.map_tree = load_map_id_file(p)
                return
            except Exception:
                pass
        self.map_tree = None

    def _describe_id(self, code: str) -> str:
        if not code:
            return ""
        if self.map_tree is not None:
            try:
                return self.map_tree.describe(code)
            except Exception:
                pass
        return code

    # ------------------------------------------------------------------
    # GIAO DIỆN CHUẨN MYLT 2026 v1.0.3.44
    # ------------------------------------------------------------------
    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        # Hàng 1: Chọn nguồn (Ngân hàng câu hỏi | Từ Files)
        r_src = QHBoxLayout()
        self.rb_bank = QRadioButton("Từ ngân hàng câu hỏi")
        self.rb_files = QRadioButton("Từ Files. Chọn một hoặc nhiều file nguồn chứa câu hỏi")
        self.rb_files.setChecked(True)
        r_src.addWidget(self.rb_bank)
        r_src.addWidget(self.rb_files)
        r_src.addStretch()
        root.addLayout(r_src)

        # Hàng 2: Files + Chọn / Thêm / Load
        r_files = QHBoxLayout()
        self.cbo_files = QComboBox()
        self.cbo_files.setEditable(True)
        self.cbo_files.lineEdit().setPlaceholderText("Chọn một hoặc nhiều tệp .tex nguồn chứa câu hỏi...")
        b_chon = QPushButton("Chọn"); b_chon.clicked.connect(self._pick_files_replace)
        b_them = QPushButton("Thêm"); b_them.clicked.connect(self._pick_files_append)
        b_load = QPushButton("Load"); b_load.clicked.connect(self._load_questions)
        r_files.addWidget(QLabel("Files"))
        r_files.addWidget(self.cbo_files, 1)
        r_files.addWidget(b_chon)
        r_files.addWidget(b_them)
        r_files.addWidget(b_load)
        root.addLayout(r_files)

        # Hàng 2b: Nạp tệp main.tex (khung preamble để biên dịch PDF)
        r_main = QHBoxLayout()
        self.ed_main_tex = QLineEdit(self.cfg.get("MainTeX", "main_tex_path", ""))
        self.ed_main_tex.setPlaceholderText("Tệp main.tex / Header.tex dùng làm khung biên dịch PDF (để trống sẽ dùng mặc định)...")
        b_pick_main = QPushButton("Nạp Main .tex")
        b_pick_main.clicked.connect(self._pick_main_tex)
        b_clear_flt = QPushButton("Xoá lọc")
        b_clear_flt.clicked.connect(self._clear_filters)
        r_main.addWidget(QLabel("Main .tex"))
        r_main.addWidget(self.ed_main_tex, 1)
        r_main.addWidget(b_pick_main)
        r_main.addWidget(b_clear_flt)
        root.addLayout(r_main)

        # Hàng 3: Thanh lọc đa tầng nối trực tiếp tên từ Map ID (Lớp -> Môn -> Chương -> Bài -> Dạng)
        r_flt = QHBoxLayout()
        b_loc = QPushButton("Lọc"); b_loc.clicked.connect(self._apply_filter)
        self.cbo_lop = QComboBox(); self.cbo_lop.setMinimumWidth(65)
        self.cbo_mon = QComboBox(); self.cbo_mon.setMinimumWidth(70)
        self.cbo_chuong = QComboBox(); self.cbo_chuong.setMinimumWidth(85)
        self.cbo_bai = QComboBox(); self.cbo_bai.setMinimumWidth(85)
        self.cbo_dang = QComboBox(); self.cbo_dang.setMinimumWidth(85)
        self.cbo_mucdo = QComboBox(); self.cbo_mucdo.setMinimumWidth(65)
        for _cb in (self.cbo_lop, self.cbo_mon, self.cbo_chuong, self.cbo_bai, self.cbo_dang, self.cbo_mucdo):
            _cb.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
        for cb, pw in [(self.cbo_chuong, 280), (self.cbo_bai, 280), (self.cbo_dang, 300), (self.cbo_mucdo, 160)]:
            cb.view().setMinimumWidth(pw)

        self.cbo_loai = QComboBox()
        for lb, val in [("ALL", ""), ("TN", "TN"), ("TL", "TL"), ("ĐS", "DS"), ("SA", "KQ"), ("GĐ", "GN")]:
            self.cbo_loai.addItem(lb, val)

        self.cbo_kieu_id = QComboBox()
        self.cbo_kieu_id.addItem("3 Sách", "Map ID_3Sach.tex")
        self.cbo_kieu_id.addItem("4 Mức độ", "Map ID_4MucDo.tex")
        self.cbo_kieu_id.addItem("Chuẩn", "Map ID.tex")
        self.cbo_kieu_id.addItem("Gốc", "Map ID_Goc.tex")
        self.cbo_kieu_id.currentIndexChanged.connect(self._on_map_changed)

        self.cbo_id_txt = QComboBox()
        self.cbo_id_txt.setMinimumWidth(80)
        for lb, val in [("Tất cả", "ALL"), ("Không", "NONE"), ("Có ID", "HAS"), ("Sai ID", "INVALID")]:
            self.cbo_id_txt.addItem(lb, val)

        self.cbo_lop.currentIndexChanged.connect(self._on_lop_changed)
        self.cbo_mon.currentIndexChanged.connect(self._on_mon_changed)
        self.cbo_chuong.currentIndexChanged.connect(self._on_chuong_changed)
        self.cbo_bai.currentIndexChanged.connect(self._on_bai_changed)
        self.cbo_dang.currentIndexChanged.connect(lambda: self._apply_filter())
        self.cbo_mucdo.currentIndexChanged.connect(lambda: self._apply_filter())
        self.cbo_loai.currentIndexChanged.connect(lambda: self._apply_filter())
        self.cbo_id_txt.currentIndexChanged.connect(lambda: self._apply_filter())
        self._populate_map_dropdowns()

        r_flt.addWidget(b_loc)
        for lbl, w in [
            ("Lớp", self.cbo_lop), ("Môn", self.cbo_mon), ("Chương", self.cbo_chuong),
            ("Bài", self.cbo_bai), ("Dạng", self.cbo_dang), ("Mức độ", self.cbo_mucdo),
            ("Loại", self.cbo_loai), ("Kiểu ID", self.cbo_kieu_id), ("ID", self.cbo_id_txt),
        ]:
            r_flt.addWidget(QLabel(lbl))
            r_flt.addWidget(w)
        root.addLayout(r_flt)

        # Bảng câu hỏi 6 cột: STT | Nội dung | ID1 | ID2 | Loại | Diễn giải ID
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["STT", "Nội dung", "ID1", "ID2", "Loại", "Diễn giải ID"])
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        hdr = self.tbl.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Interactive)
        self.tbl.setColumnWidth(5, 240)
        self.tbl.cellDoubleClicked.connect(lambda _r, _c: self._on_view())
        root.addWidget(self.tbl, 1)

        # Thanh công cụ dưới cùng đúng thứ tự MyLT 2026
        bot = QHBoxLayout()
        actions = [
            ("HDSD", self._on_hdsd),
            ("Gán ID", self._on_assign_id),
            ("AI ID", self._on_ai_id),
            ("Tìm", self._on_find_dialog),
            ("Nhập", self._on_import_to_bank),
            ("Nhập .mylt", self._on_import_mylt),
            ("Mở", self._on_open_source),
            ("Xem", self._on_view),
            ("Sửa", self._on_edit),
            ("Xoá", self._on_delete),
            ("Copy", self._on_copy),
        ]
        for label, fn in actions:
            b = QPushButton(label)
            b.clicked.connect(fn)
            bot.addWidget(b)

        self.chk_pdf = QCheckBox("PDF")
        self.chk_pdf.setToolTip("Tick để nút 'Xem' tự động biên dịch và mở PDF câu đang chọn")
        self.btn_compile_pdf = QPushButton("Biên dịch PDF")
        self.btn_compile_pdf.clicked.connect(self._on_compile_pdf)
        bot.addWidget(self.chk_pdf)
        bot.addWidget(self.btn_compile_pdf)

        bot.addStretch(1)
        self.lbl_total = QLabel("Tổng số câu: 0")
        bot.addWidget(self.lbl_total)
        bot.addStretch(1)

        b_first = QPushButton("Đầu"); b_first.clicked.connect(lambda: self._go_page(1))
        b_prev = QPushButton("Trước"); b_prev.clicked.connect(lambda: self._go_page(self.current_page - 1))
        self.cbo_page = QComboBox(); self.cbo_page.setMinimumWidth(70)
        self.cbo_page.currentIndexChanged.connect(self._on_page_combo)
        b_next = QPushButton("Sau"); b_next.clicked.connect(lambda: self._go_page(self.current_page + 1))
        b_last = QPushButton("Cuối"); b_last.clicked.connect(lambda: self._go_page(self._total_pages()))
        for w in (b_first, b_prev, self.cbo_page, b_next, b_last):
            bot.addWidget(w)
        root.addLayout(bot)

    # ------------------------------------------------------------------
    # NẠP & LỌC DỮ LIỆU
    # ------------------------------------------------------------------
    def _pick_files_replace(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn một hoặc nhiều file .tex", "", "LaTeX (*.tex)")
        if not paths:
            return
        self.source_files = [Path(p) for p in paths]
        self._sync_files_combo()
        self.rb_files.setChecked(True)
        self._load_questions()

    def _pick_files_append(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Thêm file .tex", "", "LaTeX (*.tex)")
        if not paths:
            return
        existing = {p.resolve() for p in self.source_files}
        for p in paths:
            pp = Path(p)
            if pp.resolve() not in existing:
                self.source_files.append(pp)
        self._sync_files_combo()
        self.rb_files.setChecked(True)
        self._load_questions()

    def _sync_files_combo(self):
        self.cbo_files.clear()
        for p in self.source_files:
            self.cbo_files.addItem(str(p))

    def _detect_qtype(self, tex: str) -> str:
        if r"\choiceTF" in tex:
            return "DS"
        if r"\shortans" in tex:
            return "KQ"
        if r"\choice" in tex:
            return "TN"
        return "TL"

    def _load_questions(self):
        self.all_items.clear()
        if self.rb_bank.isChecked():
            if self.db is None:
                QMessageBox.warning(self, "Ngân hàng", "Chưa kết nối cơ sở dữ liệu ngân hàng câu hỏi.")
                return
            rows = self.db.search(limit=5000)
            for r in rows:
                raw = r["raw_tex"] if "raw_tex" in r.keys() else (r["stem"] if "stem" in r.keys() else "")
                ids = ID_RE.findall(raw)
                id1 = r["id6"] if "id6" in r.keys() and r["id6"] else (ids[0] if ids else "")
                id2 = ids[1] if len(ids) > 1 else ""
                qtype = r["qtype"] if "qtype" in r.keys() and r["qtype"] else self._detect_qtype(raw)
                stem = r["stem"] if "stem" in r.keys() and r["stem"] else raw
                preview = " ".join(stem.split())[:140]
                self.all_items.append(QuestionItemRow(r["id"], raw, preview, id1, id2, qtype, "Ngân hàng DB"))
        else:
            if not self.source_files:
                txt_path = self.cbo_files.currentText().strip()
                if txt_path and Path(txt_path).exists():
                    self.source_files = [Path(txt_path)]
                else:
                    QMessageBox.information(self, "Chọn file", "Hãy bấm 'Chọn' hoặc 'Thêm' để chọn tệp .tex nguồn.")
                    return
            for fp in self.source_files:
                if not fp.exists():
                    continue
                content = read_tex_with_inputs(fp)
                qs = parse_tex_questions(content)
                for q in qs:
                    raw = q.to_latex(include_solution=True)
                    ids = ID_RE.findall(raw)
                    pid = q.primary_id() if callable(getattr(q, "primary_id", None)) else getattr(q, "primary_id", "")
                    id1 = pid or (ids[0] if ids else "")
                    id2 = ids[1] if len(ids) > 1 else ""
                    qtype = getattr(q, "qtype", "") or self._detect_qtype(raw)
                    preview = " ".join(getattr(q, "stem", raw).split())[:140]
                    self.all_items.append(QuestionItemRow(None, raw, preview, id1, id2, qtype, str(fp)))

        self._apply_filter()
        if self.all_items and not self.filtered_items:
            QMessageBox.information(
                self,
                "Đã nạp câu hỏi",
                f"Đã nạp {len(self.all_items)} câu hỏi từ nguồn, nhưng bộ lọc hiện tại đang ẩn hết.\n"
                "Bấm 'Xoá lọc' để hiển thị toàn bộ câu hỏi.",
            )

    def _populate_map_dropdowns(self):
        """Đổ danh sách Lớp và Mức độ từ MapIDTree hiện tại."""
        for cb in (self.cbo_lop, self.cbo_mon, self.cbo_chuong, self.cbo_bai, self.cbo_dang, self.cbo_mucdo):
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("", "")
        if self.map_tree is not None:
            for k, v in self.map_tree.grades.items():
                self.cbo_lop.addItem(f"[{k}] {v}", k)
            for k, v in self.map_tree.levels.items():
                self.cbo_mucdo.addItem(f"[{k}] {v}", k)
        else:
            for k, v in [("0", "Lớp 10"), ("1", "Lớp 11"), ("2", "Lớp 12")]:
                self.cbo_lop.addItem(f"[{k}] {v}", k)
            for k in ("N", "H", "V", "C", "Y", "B", "K", "G", "T"):
                self.cbo_mucdo.addItem(k, k)
        for cb in (self.cbo_lop, self.cbo_mon, self.cbo_chuong, self.cbo_bai, self.cbo_dang, self.cbo_mucdo):
            cb.blockSignals(False)

    def _on_lop_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        for cb in (self.cbo_mon, self.cbo_chuong, self.cbo_bai, self.cbo_dang):
            cb.blockSignals(True); cb.clear(); cb.addItem("", "")
        if self.map_tree is not None and lop:
            for (g, s), name in self.map_tree.subjects.items():
                if g == lop:
                    self.cbo_mon.addItem(f"[{s}] {name}", s)
        for cb in (self.cbo_mon, self.cbo_chuong, self.cbo_bai, self.cbo_dang):
            cb.blockSignals(False)
        self._apply_filter()

    def _on_mon_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        mon = str(self.cbo_mon.currentData() or "")
        for cb in (self.cbo_chuong, self.cbo_bai, self.cbo_dang):
            cb.blockSignals(True); cb.clear(); cb.addItem("", "")
        if self.map_tree is not None and lop and mon:
            for (g, s, c), name in self.map_tree.chapters.items():
                if g == lop and s == mon:
                    self.cbo_chuong.addItem(f"[{c}] {name}", c)
        for cb in (self.cbo_chuong, self.cbo_bai, self.cbo_dang):
            cb.blockSignals(False)
        self._apply_filter()

    def _on_chuong_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        mon = str(self.cbo_mon.currentData() or "")
        ch = str(self.cbo_chuong.currentData() or "")
        for cb in (self.cbo_bai, self.cbo_dang):
            cb.blockSignals(True); cb.clear(); cb.addItem("", "")
        if self.map_tree is not None and lop and mon and ch:
            for (g, s, c, l), name in self.map_tree.lessons.items():
                if g == lop and s == mon and c == ch:
                    self.cbo_bai.addItem(f"[{l}] {name}", l)
        for cb in (self.cbo_bai, self.cbo_dang):
            cb.blockSignals(False)
        self._apply_filter()

    def _on_bai_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        mon = str(self.cbo_mon.currentData() or "")
        ch = str(self.cbo_chuong.currentData() or "")
        bai = str(self.cbo_bai.currentData() or "")
        self.cbo_dang.blockSignals(True); self.cbo_dang.clear(); self.cbo_dang.addItem("", "")
        if self.map_tree is not None and lop and mon and ch and bai:
            for (g, s, c, l, f), name in self.map_tree.forms.items():
                if g == lop and s == mon and c == ch and l == bai:
                    self.cbo_dang.addItem(f"[{f}] {name}", f)
        self.cbo_dang.blockSignals(False)
        self._apply_filter()

    def _on_map_changed(self):
        fname = self.cbo_kieu_id.currentData()
        if fname:
            self._load_map_tree(fname)
            self._populate_map_dropdowns()
            self._apply_filter()

    def _apply_filter(self, keyword: str = ""):
        lop = str(self.cbo_lop.currentData() or "").strip()
        mon = str(self.cbo_mon.currentData() or "").strip().upper()
        chuong = str(self.cbo_chuong.currentData() or "").strip()
        bai = str(self.cbo_bai.currentData() or "").strip()
        dang = str(self.cbo_dang.currentData() or "").strip()
        mucdo = str(self.cbo_mucdo.currentData() or "").strip().upper()
        loai = str(self.cbo_loai.currentData() or "").strip().upper()
        id_mode = str(self.cbo_id_txt.currentData() or "ALL")
        kw = keyword.strip().lower()

        res: list[QuestionItemRow] = []
        for it in self.all_items:
            cid = it.id1.upper()
            if id_mode == "NONE" and cid:
                continue
            if id_mode == "HAS" and not cid:
                continue
            if id_mode == "INVALID":
                if not cid:
                    continue
                if re.fullmatch(r"[0-9][A-Z][0-9][A-Z][0-9](?:-[0-9])?", cid):
                    continue
            if lop and (len(cid) < 1 or cid[0] != lop):
                continue
            if mon and (len(cid) < 2 or cid[1] != mon):
                continue
            if chuong and (len(cid) < 3 or cid[2] != chuong):
                continue
            if mucdo and (len(cid) < 4 or cid[3] != mucdo):
                continue
            if bai and (len(cid) < 5 or cid[4] != bai):
                continue
            if dang and (f"-{dang}" not in cid):
                continue
            if loai and it.qtype.upper() != loai:
                continue
            if kw and (kw not in it.raw_tex.lower() and kw not in cid.lower()):
                continue
            res.append(it)

        self.filtered_items = res
        self.current_page = 1
        self._update_pagination()
        self._render_table()

    def _total_pages(self) -> int:
        return max(1, (len(self.filtered_items) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)

    def _update_pagination(self):
        total_p = self._total_pages()
        self.cbo_page.blockSignals(True)
        self.cbo_page.clear()
        for p in range(1, total_p + 1):
            self.cbo_page.addItem(f"{p}/{total_p}", p)
        self.cbo_page.setCurrentIndex(min(self.current_page - 1, total_p - 1))
        self.cbo_page.blockSignals(False)
        self.lbl_total.setText(f"Tổng số câu: {len(self.filtered_items)} / {len(self.all_items)}")

    def _go_page(self, page: int):
        total_p = self._total_pages()
        self.current_page = max(1, min(page, total_p))
        self._update_pagination()
        self._render_table()

    def _on_page_combo(self, idx: int):
        if idx >= 0:
            self.current_page = idx + 1
            self._render_table()

    def _render_table(self):
        start = (self.current_page - 1) * self.PAGE_SIZE
        chunk = self.filtered_items[start : start + self.PAGE_SIZE]
        self.tbl.setRowCount(len(chunk))
        for i, it in enumerate(chunk):
            self.tbl.setItem(i, 0, QTableWidgetItem(str(start + i + 1)))
            self.tbl.setItem(i, 1, QTableWidgetItem(it.preview))
            self.tbl.setItem(i, 2, QTableWidgetItem(it.id1))
            self.tbl.setItem(i, 3, QTableWidgetItem(it.id2))
            self.tbl.setItem(i, 4, QTableWidgetItem(it.qtype))
            self.tbl.setItem(i, 5, QTableWidgetItem(self._describe_id(it.id1)))

    def _selected_items(self) -> list[QuestionItemRow]:
        rows = sorted({idx.row() for idx in self.tbl.selectedIndexes()})
        start = (self.current_page - 1) * self.PAGE_SIZE
        return [self.filtered_items[start + r] for r in rows if 0 <= start + r < len(self.filtered_items)]

    # ------------------------------------------------------------------
    # CÁC NÚT CHỨC NĂNG DƯỚI CÙNG
    # ------------------------------------------------------------------
    def _on_hdsd(self):
        QMessageBox.information(
            self,
            "Hướng dẫn cửa sổ Câu hỏi",
            "- Chọn 'Từ ngân hàng câu hỏi' hoặc 'Từ Files' rồi bấm 'Load'.\n"
            "- Dùng thanh lọc (Lớp, Môn, Chương, Bài, Dạng, Mức độ, Loại, Kiểu ID, ID) rồi bấm 'Lọc'.\n"
            "- Tick 'PDF' rồi bấm 'Xem' hoặc bấm trực tiếp 'Biên dịch PDF' để xuất và mở tệp PDF các câu đang chọn.\n"
            "- Dùng 'Gán ID' (thủ công) hoặc 'AI ID' (Gemini) để chuẩn hóa mã ID6.",
        )

    def _on_assign_id(self):
        sel = self._selected_items()
        if not sel:
            QMessageBox.warning(self, "Chưa chọn câu", "Hãy chọn ít nhất 1 câu trong bảng.")
            return
        new_id, ok = QInputDialog.getText(self, "Gán ID", "Nhập mã ID6 mới (VD: 2D1N1-1):")
        if not ok or not new_id.strip():
            return
        code = new_id.strip().strip("%[]")
        for it in sel:
            it.id1 = code
            if ID_RE.search(it.raw_tex):
                it.raw_tex = ID_RE.sub(f"%[{code}]", it.raw_tex, count=1)
            else:
                it.raw_tex = it.raw_tex.replace(r"\begin{ex}", f"\\begin{{ex}}%[{code}]", 1)
        self._render_table()

    def _on_ai_id(self):
        sel = self._selected_items()
        if not sel:
            QMessageBox.warning(self, "Chưa chọn câu", "Hãy chọn ít nhất 1 câu để AI gán ID6.")
            return
        api_key = self.cfg.get("API", "gemini_api_key").strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu Gemini API Key", "Vào Tab 'Tiện ích' -> 'Phiếu 2025 · Tikz2Pic · Blogger · Config' để nhập Gemini API Key.")
            return
        try:
            from google import genai
        except ImportError:
            QMessageBox.critical(self, "Thiếu thư viện", "Chưa cài google-genai (pip install google-genai).")
            return
        client = genai.Client(api_key=api_key)
        model = self.cfg.get("API", "gemini_model", "gemini-2.5-flash")
        updated = 0
        for it in sel:
            prompt = (
                "Chỉ trả về đúng 1 mã ID6 chuẩn chương trình GDPT 2018 (VD: 2D1N1-1) cho câu hỏi Toán sau, không giải thích:\n"
                + it.raw_tex
            )
            try:
                resp = client.models.generate_content(model=model, contents=prompt)
                m = re.search(r"[0-9][A-Za-z][0-9][A-Za-z][0-9](?:-[0-9])?", (resp.text or "").strip())
                if m:
                    code = m.group(0)
                    it.id1 = code
                    if ID_RE.search(it.raw_tex):
                        it.raw_tex = ID_RE.sub(f"%[{code}]", it.raw_tex, count=1)
                    else:
                        it.raw_tex = it.raw_tex.replace(r"\begin{ex}", f"\\begin{{ex}}%[{code}]", 1)
                    updated += 1
            except Exception as exc:
                QMessageBox.critical(self, "Lỗi Gemini AI", str(exc))
                break
        self._render_table()
        QMessageBox.information(self, "AI ID", f"Đã gán tự động ID6 cho {updated}/{len(sel)} câu.")

    def _on_find_dialog(self):
        kw, ok = QInputDialog.getText(self, "Tìm câu hỏi", "Nhập từ khoá hoặc mã ID cần tìm:")
        if ok:
            self._apply_filter(keyword=kw)

    def _on_import_to_bank(self):
        if self.db is None:
            QMessageBox.warning(self, "Ngân hàng", "Chưa kết nối cơ sở dữ liệu.")
            return
        from .import_bank_dialog import ImportBankDialog
        dlg = ImportBankDialog(self.db, self)
        dlg.exec()
        if dlg.imported_count > 0 and self.rb_bank.isChecked():
            self._load_questions()

    def _on_open_source(self):
        sel = self._selected_items()
        if sel and sel[0].source_file and Path(sel[0].source_file).exists():
            open_pdf_file(sel[0].source_file)
        elif self.source_files:
            open_pdf_file(self.source_files[0])
        else:
            QMessageBox.information(self, "Mở tệp", "Chưa có tệp nguồn nào được chọn.")

    def _on_view(self):
        sel = self._selected_items()
        if not sel:
            QMessageBox.warning(self, "Chưa chọn câu", "Hãy chọn 1 câu trong bảng để xem.")
            return
        if self.chk_pdf.isChecked():
            self._compile_items_to_pdf(sel)
            return
        dlg = _EditQuestionDialog(f"Xem câu hỏi ({sel[0].id1 or 'Chưa có ID'})", sel[0].raw_tex, readonly=True, parent=self)
        dlg.exec()

    def _on_edit(self):
        sel = self._selected_items()
        if not sel:
            QMessageBox.warning(self, "Chưa chọn câu", "Hãy chọn 1 câu trong bảng để sửa.")
            return
        it = sel[0]
        dlg = _EditQuestionDialog(f"Sửa câu hỏi ({it.id1 or 'Chưa có ID'})", it.raw_tex, readonly=False, parent=self)
        if dlg.exec() == QDialog.Accepted:
            new_tex = dlg.value()
            it.raw_tex = new_tex
            it.preview = " ".join(new_tex.split())[:140]
            ids = ID_RE.findall(new_tex)
            if ids:
                it.id1 = ids[0]
            if it.db_id is not None and self.db is not None:
                try:
                    self.db.update_question_stem(it.db_id, new_tex)
                except Exception:
                    pass
            self._render_table()

    def _on_delete(self):
        sel = self._selected_items()
        if not sel:
            return
        if QMessageBox.question(self, "Xoá câu hỏi", f"Bạn có chắc muốn xoá {len(sel)} câu đã chọn?") != QMessageBox.Yes:
            return
        for it in sel:
            if it.db_id is not None and self.db is not None and self.rb_bank.isChecked():
                try:
                    self.db.delete_question(it.db_id)
                except Exception:
                    pass
            if it in self.all_items:
                self.all_items.remove(it)
            if it in self.filtered_items:
                self.filtered_items.remove(it)
        self._update_pagination()
        self._render_table()

    def _on_copy(self):
        sel = self._selected_items()
        if not sel:
            QMessageBox.warning(self, "Chưa chọn câu", "Hãy chọn ít nhất 1 câu để sao chép.")
            return
        QApplication.clipboard().setText("\n\n".join(it.raw_tex for it in sel))
        QMessageBox.information(self, "Copy", f"Đã sao chép {len(sel)} câu vào clipboard.")

    def _on_compile_pdf(self):
        items = self._selected_items() or self.filtered_items
        if not items:
            QMessageBox.warning(self, "Trống", "Chưa có câu hỏi nào để biên dịch PDF.")
            return
        self._compile_items_to_pdf(items)

    def _compile_items_to_pdf(self, items: list[QuestionItemRow]):
        out_dir = Path(tempfile.gettempdir()) / "toan11_cauhoi_pdf"
        out_dir.mkdir(parents=True, exist_ok=True)
        import uuid
        tex_file = out_dir / f"xem_cau_hoi_{uuid.uuid4().hex[:8]}.tex"

        body = "\n\n".join(it.raw_tex for it in items)
        main_p = Path(self.ed_main_tex.text().strip()) if self.ed_main_tex.text().strip() else None
        if main_p and main_p.exists():
            mtxt = main_p.read_text(encoding="utf-8", errors="replace")
            idx_doc = mtxt.find(r"\begin{document}")
            if idx_doc != -1:
                preamble = mtxt[: idx_doc + len(r"\begin{document}")]
                doc = f"{preamble}\n\\providecommand{{\\MYLT}}[1][]{{}}\n{body}\n\\end{{document}}\n"
                tex_file = main_p.parent / f"_toan11_preview_{uuid.uuid4().hex[:8]}.tex"
            else:
                doc = f"{mtxt}\n{body}\n\\end{{document}}\n"
        else:
            doc = (
                "\\documentclass[12pt,a4paper]{article}\n"
                "\\usepackage[utf8]{vietnam}\n"
                "\\usepackage[shortlabels]{enumitem}\n"
                "\\usepackage{amsmath,amssymb,amsfonts,graphicx,xcolor,array,multicol,tikz,tkz-tab,pgfplots}\n"
                "\\usepackage[loigiai]{nhd_extest}\n\\providecommand{\\MYLT}[1][]{}\n"
                "\\pgfplotsset{compat=1.16}\n"
                "\\begin{document}\n"
                f"{body}\n"
                "\\end{document}\n"
            )
        tex_file.write_text(doc, encoding="utf-8")
        res = compile_tex_to_pdf(str(tex_file), compiler="pdflatex", passes=1)
        if res.success and res.pdf_path:
            open_pdf_file(res.pdf_path)
        else:
            diag = "\n".join(f"Dòng {d.line_no}: {d.summary} ({d.suggestion_vi})" for d in res.diagnostics[:5])
            QMessageBox.critical(self, "Lỗi biên dịch PDF", diag or res.stderr or "Không thể biên dịch PDF. Kiểm tra cài đặt TeX Live / MiKTeX.")


    def _pick_main_tex(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp main.tex / Header.tex", "", "LaTeX (*.tex)")
        if not p:
            return
        self.ed_main_tex.setText(p)
        self.cfg.set("MainTeX", "main_tex_path", p)
        self.cfg.save()
        QMessageBox.information(self, "Đã nạp Main .tex", f"Đã lưu tệp khung biên dịch:\n{p}")

    def _clear_filters(self):
        self.cbo_lop.setCurrentIndex(0)
        self.cbo_mucdo.setCurrentIndex(0)
        self.cbo_loai.setCurrentIndex(0)
        self.cbo_id_txt.setCurrentIndex(0)
        self._apply_filter()


    def _on_import_mylt(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp ngân hàng MyLT (.mylt / .mdb)", "", "MyLT Bank (*.mylt *.mdb)")
        if not p:
            return
        try:
            if self.db is not None:
                stat = import_mylt_into_db(p, self.db)
                QMessageBox.information(
                    self,
                    "Nhập Bank.mylt thành công",
                    f"Tổng dòng trong bảng QUEST: {stat.get('total_rows', 0)}\n"
                    f"Đã nhập mới vào kho nganhang.db: {stat.get('added', 0)} câu.",
                )
                self.rb_bank.setChecked(True)
                self._load_questions()
            else:
                out_tex = Path(p).with_suffix(".tex")
                n = convert_mylt_to_tex(p, out_tex)
                QMessageBox.information(self, "Chuyển Bank.mylt", f"Đã xuất {n} câu ra tệp:\n{out_tex}")
        except Exception as exc:
            QMessageBox.critical(self, "Lỗi đọc Bank.mylt", str(exc))
