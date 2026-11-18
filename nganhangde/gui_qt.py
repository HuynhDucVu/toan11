"""Giao diện chính bằng PySide6 (Qt) – dùng để đóng gói thành file .exe.

Chạy:  python -m nganhangde gui     (hoặc chạy NganHangDe.exe)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

from PySide6.QtCore import QSettings, Qt, QUrl
from PySide6.QtGui import (QAction, QColor, QDesktopServices, QFont, QIcon, QKeySequence,
                           QSyntaxHighlighter, QTextCharFormat)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox,
                               QDialog, QDialogButtonBox, QFrame, QScrollArea, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QInputDialog, QHeaderView, QLabel, QLineEdit, QListWidget,
                               QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextBrowser, QToolBar, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from . import __version__, tools
from .db import Bank
from .exporter import ExportOptions, export_questions, export_versions
from .generator import (THPT_2026, MixOptions, NotEnoughQuestions, Rule, answer_distribution, check_structure,
                        make_codes, make_versions, matrix_from_questions, overlap_report)
from .idmap import IdTree, dash_duplicates, parse_map_text, save_map, to_dash_text
from .idsuggest import MapSuggester, Suggester, combine
from . import review as rv
from .idcode import LOP, MON, parse_id
from .parser import parse_file, parse_tex, validate

APP_NAME = "Ngân hàng đề thi"
TEN_LOAI = {"TN": "Trắc nghiệm", "DS": "Đúng/Sai", "KQ": "Trả lời ngắn", "TL": "Tự luận"}
TEN_MUC = {"N": "Nhận biết", "H": "Thông hiểu", "V": "Vận dụng", "C": "Vận dụng cao"}

MAU_CAU = {
    "TN": ("\\begin{ex}%[Nguồn]%[0D1N1-1]\n\tNội dung câu hỏi\n\t\\choice\n\t{\\True Phương án A}\n"
           "\t{Phương án B}\n\t{Phương án C}\n\t{Phương án D}\n\t\\loigiai{\n\t\tLời giải\n\t}\n\\end{ex}"),
    "DS": ("\\begin{ex}%[Nguồn]%[0D1H1-1]\n\tNội dung câu hỏi\n\t\\choiceTF[t]\n\t{\\True Ý a}\n\t{Ý b}\n"
           "\t{\\True Ý c}\n\t{Ý d}\n\t\\loigiai{\n\t\t\\begin{itemchoice}\n\t\t\t\\itemch Đúng. ...\n"
           "\t\t\t\\itemch Sai. ...\n\t\t\t\\itemch Đúng. ...\n\t\t\t\\itemch Sai. ...\n"
           "\t\t\\end{itemchoice}\n\t}\n\\end{ex}"),
    "KQ": ("\\begin{ex}%[Nguồn]%[0D1V1-1]\n\tNội dung câu hỏi\n\t\\shortans[oly]{$12$}\n"
           "\t\\loigiai{\n\t\tLời giải\n\t}\n\\end{ex}"),
    "TL": "\\begin{bt}%[Nguồn]%[0D1V1-1]\n\tNội dung câu hỏi\n\t\\loigiai{\n\t\tLời giải\n\t}\n\\end{bt}",
}

STYLE = """
QMainWindow, QDialog { background: #f5f7fa; }
QToolBar { background: #1f4e79; spacing: 4px; padding: 4px; border: none; }
QToolBar QToolButton { color: white; padding: 6px 10px; border-radius: 4px; font-weight: 600; }
QToolBar QToolButton:hover { background: #2e6da4; }
QGroupBox { font-weight: 600; border: 1px solid #c8d1dc; border-radius: 6px; margin-top: 10px; padding-top: 6px; background: white; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; color: #1f4e79; }
QTableWidget { background: white; alternate-background-color: #eef3f8; gridline-color: #dde3ea; selection-background-color: #2e6da4; }
QHeaderView::section { background: #dce6f1; padding: 4px; border: none; border-right: 1px solid #c8d1dc; font-weight: 600; }
QTreeWidget { background: white; }
QPushButton { padding: 5px 12px; border-radius: 4px; background: #e4ebf3; border: 1px solid #b9c6d4; }
QPushButton:hover { background: #d3e0ee; }
QPushButton#primary { background: #1f4e79; color: white; font-weight: 600; border: none; }
QPushButton#primary:hover { background: #2e6da4; }
QStatusBar { background: #dce6f1; }
QTabWidget#mainTabs::pane { border-top: 3px solid #1f4e79; background: #f5f7fa; }
QTabWidget#mainTabs > QTabBar::tab { background: #dce6f1; color: #1f4e79; padding: 8px 18px; margin-right: 2px;
    border-top-left-radius: 6px; border-top-right-radius: 6px; font-weight: 600; }
QTabWidget#mainTabs > QTabBar::tab:selected { background: #1f4e79; color: white; }
QTabWidget#mainTabs > QTabBar::tab:hover:!selected { background: #c5d6ea; }
"""


def resource_dir() -> str:
    """Thư mục chứa dữ liệu mặc định (cạnh file .exe khi đã đóng gói)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()


class LatexHighlighter(QSyntaxHighlighter):
    """Tô màu mã LaTeX: lệnh, công thức $...$, comment, ID."""

    def __init__(self, doc):
        super().__init__(doc)

        def fmt(color, bold=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            return f
        self.rules = [
            (re.compile(r"\$[^$]*\$"), fmt("#0b7a0b")),
            (re.compile(r"\\[A-Za-z@]+"), fmt("#1f4e79", True)),
            (re.compile(r"\\True"), fmt("#c00000", True)),
            (re.compile(r"\\begin\{[^}]*\}|\\end\{[^}]*\}"), fmt("#8e44ad", True)),
            (re.compile(r"(?<!\\)%.*$"), fmt("#888888")),
            (re.compile(r"%\[[0-9][A-Z][0-9A-Z][A-Z][0-9A-Z](-[0-9A-Z]+)?\]"), fmt("#d35400", True)),
        ]

    def highlightBlock(self, text):
        for rx, f in self.rules:
            for m in rx.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), f)


def scroll_of(layout) -> QScrollArea:
    """Bọc một layout trong vùng cuộn (cột dài vẫn dùng được trên màn hình nhỏ)."""
    w = QWidget()
    w.setLayout(layout)
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    sa.setWidget(w)
    return sa


def latex_editor(read_only=False) -> QPlainTextEdit:
    ed = QPlainTextEdit()
    ed.setFont(QFont("Consolas", 11))
    ed.setReadOnly(read_only)
    ed.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
    ed._hl = LatexHighlighter(ed.document())
    return ed


# =====================================================================
class MainWindow(QMainWindow):
    def __init__(self, db_path: str | None = None):
        super().__init__()
        self.settings = QSettings("NganHangDe", "NganHangDe")
        db_path = db_path or self.settings.value("db_path") or os.path.join(resource_dir(), "nganhang.db")
        self.bank: Bank | None = None
        self.resize(1300, 800)
        self._build_ui()
        self.open_bank(db_path)

    # ---------------------------------------------------------- dựng giao diện
    def _build_ui(self):
        # --- menu
        mb = self.menuBar()
        m = mb.addMenu("&Tệp")
        self._act(m, "Mở kho câu hỏi…", self.choose_bank, QKeySequence.StandardKey.Open)
        self._act(m, "Tạo kho mới…", self.new_bank, QKeySequence.StandardKey.New)
        m.addSeparator()
        self._act(m, "Nhập file .tex…", self.import_files, "Ctrl+I")
        self._act(m, "Nhập file Word (.docx)…", self.import_word)
        self._act(m, "Xuất câu đang hiển thị/đã chọn…", self.export_selected, "Ctrl+E")
        self._act(m, "Xuất câu ra Word / Moodle / bài làm online…", self.export_other)
        m.addSeparator()
        self._act(m, "Sao lưu kho…", self.backup_bank, "Ctrl+B")
        self._act(m, "Gộp kho khác vào kho này…", self.merge_bank)
        self._act(m, "Tách câu đã chọn ra kho mới…", self.split_bank)
        m.addSeparator()
        self._act(m, "Thoát", self.close, QKeySequence.StandardKey.Quit)
        m = mb.addMenu("&Câu hỏi")
        self._act(m, "Thêm câu mới", self.add_question, "Ctrl+N")
        self._act(m, "Sửa câu", self.edit_question, "F2")
        self._act(m, "Xoá câu", self.delete_questions, QKeySequence.StandardKey.Delete)
        m.addSeparator()
        self._act(m, "Gán ID cho câu đã chọn / câu thiếu ID…", self.assign_ids, "F3")
        self._act(m, "Tìm và thay thế…", self.find_replace, "Ctrl+H")
        self._act(m, "Khôi phục câu đã xoá…", self.restore_deleted)
        m = mb.addMenu("Đề &thi")
        self._act(m, "Tạo đề theo ma trận…", self.open_generator, "Ctrl+G")
        self._act(m, "Rà soát đáp án và lời giải…", self.open_review, "Ctrl+R")
        m = mb.addMenu("Công &cụ")
        self._act(m, "Soát lỗi file .tex…", self.check_file)
        self._act(m, "Giải nghĩa ID (Map ID)…", self.edit_idmap, "Ctrl+M")
        self._act(m, "Tìm câu gần trùng trong kho…", self.near_dups)
        self._act(m, "Thống kê ngân hàng", self.show_stats)
        m = mb.addMenu("Trợ &giúp")
        self._act(m, "Kiểm tra bản cập nhật…", self.check_update)
        self._act(m, "Giới thiệu", self.about)

        # --- thanh công cụ
        tb = QToolBar("Công cụ")
        tb.setMovable(False)
        self.addToolBar(tb)
        for text, fn in (("📥 Nhập .tex", self.import_files), ("➕ Thêm câu", self.add_question),
                         ("✏️ Sửa", self.edit_question), ("🗑 Xoá", self.delete_questions),
                         ("🏷 Gán ID", self.assign_ids),
                         ("📤 Xuất câu", self.export_selected), ("🎲 Tạo đề", self.open_generator),
                         ("✅ Rà soát", self.open_review), ("📊 Thống kê", self.show_stats)):
            tb.addAction(text, fn)

        # --- cột trái: cây chương + bộ lọc
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        g = QGroupBox("Cây chương")
        gl = QVBoxLayout(g)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Mục", "Số câu"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setStretchLastSection(False)
        self.tree.itemClicked.connect(self.on_tree_click)
        gl.addWidget(self.tree)
        ll.addWidget(g, 3)

        g = QGroupBox("Bộ lọc")
        fl = QFormLayout(g)
        self.f_type = QComboBox()
        self.f_type.addItem("Tất cả", "")
        for k, v in TEN_LOAI.items():
            self.f_type.addItem(v, k)
        self.f_muc = QComboBox()
        self.f_muc.addItem("Tất cả", "")
        for k, v in TEN_MUC.items():
            self.f_muc.addItem(v, k)
        self.f_id = QLineEdit()
        self.f_id.setPlaceholderText("vd: 0D2*  hoặc  0H9?3-*")
        self.f_tag = QLineEdit()
        self.f_tag.setPlaceholderText("nguồn / tác giả trong %[...]")
        self.f_text = QLineEdit()
        self.f_text.setPlaceholderText("từ khoá trong đề/lời giải/nguồn")
        fl.addRow("Loại câu", self.f_type)
        fl.addRow("Mức độ", self.f_muc)
        fl.addRow("Mẫu ID", self.f_id)
        fl.addRow("Từ khoá", self.f_text)
        fl.addRow("Nguồn", self.f_tag)
        self.f_tag.returnPressed.connect(self.refresh)
        for w in (self.f_type, self.f_muc):
            w.currentIndexChanged.connect(self.refresh)
        for w in (self.f_id, self.f_text):
            w.returnPressed.connect(self.refresh)
        row = QHBoxLayout()
        b = QPushButton("Lọc")
        b.setObjectName("primary")
        b.clicked.connect(self.refresh)
        b2 = QPushButton("Bỏ lọc")
        b2.clicked.connect(self.clear_filter)
        row.addWidget(b)
        row.addWidget(b2)
        fl.addRow(row)
        ll.addWidget(g, 2)

        # --- giữa: bảng câu hỏi
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["#", "Loại", "ID", "Mức độ", "Đáp án", "Đã dùng", "Nội dung"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        hh = self.table.horizontalHeader()
        for c, w in enumerate((50, 100, 90, 100, 70, 60)):
            self.table.setColumnWidth(c, w)
        hh.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.on_select)
        self.table.doubleClicked.connect(lambda *_: self.edit_question())

        # --- phải: xem trước
        self.tabs = QTabWidget()
        self.info = QTextBrowser()
        self.code = latex_editor(read_only=True)
        self.tabs.addTab(self.info, "Thông tin")
        self.tabs.addTab(self.code, "Mã LaTeX")
        self.sim = QTableWidget(0, 4)
        self.sim.setHorizontalHeaderLabels(["#", "ID", "Đáp án", "Nội dung"])
        self.sim.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.sim.verticalHeader().setVisible(False)
        self.sim.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sim.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sim.doubleClicked.connect(self.edit_similar)
        self.tabs.addTab(self.sim, "Câu tương tự")
        hw = QWidget()
        hl_ = QVBoxLayout(hw)
        hl_.setContentsMargins(0, 0, 0, 0)
        self.hist = QTableWidget(0, 3)
        self.hist.setHorizontalHeaderLabels(["Thời điểm", "Thao tác", "Nội dung trước khi đổi"])
        self.hist.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.hist.verticalHeader().setVisible(False)
        self.hist.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hist.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        hl_.addWidget(self.hist)
        b = QPushButton("Khôi phục bản đã chọn")
        b.clicked.connect(self.restore_version)
        hl_.addWidget(b)
        self.tabs.addTab(hw, "Lịch sử sửa")

        center = QSplitter(Qt.Orientation.Vertical)
        center.addWidget(self.table)
        center.addWidget(self.tabs)
        center.setSizes([480, 320])

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(center)
        split.setSizes([280, 1020])

        # --- cửa sổ chính chia tab
        self.main_tabs = QTabWidget()
        self.main_tabs.setObjectName("mainTabs")
        self.main_tabs.addTab(split, "📚  Ngân hàng câu hỏi")
        self.gen_panel = GeneratorPanel(self)
        self.main_tabs.addTab(self.gen_panel, "📝  Tạo đề")
        self.review_panel = ReviewPanel(self)
        self.main_tabs.addTab(self.review_panel, "✅  Rà soát")
        self.tools_panel = ToolsPanel(self)
        self.main_tabs.addTab(self.tools_panel, "🛠  Công cụ")
        self.stats_panel = StatsPanel(self)
        self.main_tabs.addTab(self.stats_panel, "📊  Thống kê")
        self.main_tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.main_tabs)
        self.statusBar().showMessage("Sẵn sàng")

    def on_tab_changed(self, idx):
        w = self.main_tabs.widget(idx)
        if w is self.gen_panel:
            self.gen_panel.update_avail()
        elif w is self.stats_panel:
            self.stats_panel.reload()

    def _act(self, menu, text, fn, shortcut=None):
        a = QAction(text, self)
        a.triggered.connect(fn)
        if shortcut:
            a.setShortcut(shortcut)
        menu.addAction(a)
        return a

    # ---------------------------------------------------------- kho dữ liệu
    def open_bank(self, path: str):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            bank = Bank(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi", f"Không mở được kho:\n{path}\n\n{e}")
            return
        if self.bank:
            self.bank.close()
        self.bank = bank
        self.settings.setValue("db_path", os.path.abspath(path))
        self.setWindowTitle(f"{APP_NAME} – {os.path.abspath(path)}")
        self.build_tree()
        self.refresh()
        self.gen_panel.update_avail()
        self.stats_panel.reload()

    def choose_bank(self):
        p, _ = QFileDialog.getOpenFileName(self, "Mở kho câu hỏi", "", "Kho câu hỏi (*.db);;Tất cả (*.*)")
        if p:
            self.open_bank(p)

    def new_bank(self):
        p, _ = QFileDialog.getSaveFileName(self, "Tạo kho mới", "nganhang.db", "Kho câu hỏi (*.db)")
        if p:
            self.open_bank(p)

    def build_tree(self):
        self.tree.clear()
        root = QTreeWidgetItem(["Toàn bộ ngân hàng", str(self.bank.count())])
        root.setData(0, Qt.ItemDataRole.UserRole, {})
        self.tree.addTopLevelItem(root)
        nodes = {}
        names = self.bank.idmap()
        for r in self.bank.stats():
            lop, mon, ch, n = r["lop"], r["mon"], r["chuong"], r["n"]
            path = [("lop", lop, f"Lớp {LOP.get(lop, lop)}" if lop else "Chưa có ID"),
                    ("mon", mon, names.get(lop + mon) or MON.get(mon, mon or "?")),
                    ("chuong", ch, names.get(lop + mon + ch) or f"Chương {ch}")]
            parent, filt = root, {}
            for key, val, label in path:
                if not lop and key != "lop":
                    break
                filt = {**filt, key: val}
                k = tuple(sorted(filt.items()))
                if k not in nodes:
                    it = QTreeWidgetItem([label, "0"])
                    it.setToolTip(0, label)
                    it.setData(0, Qt.ItemDataRole.UserRole, filt)
                    parent.addChild(it)
                    nodes[k] = it
                node = nodes[k]
                node.setText(1, str(int(node.text(1)) + n))
                parent = node
        root.setExpanded(True)
        for i in range(root.childCount()):
            root.child(i).setExpanded(True)
        self.tree_filter = {}

    def on_tree_click(self, item, _col):
        self.tree_filter = item.data(0, Qt.ItemDataRole.UserRole) or {}
        self.refresh()

    def clear_filter(self):
        self.f_type.setCurrentIndex(0)
        self.f_muc.setCurrentIndex(0)
        self.f_id.clear()
        self.f_text.clear()
        self.tree_filter = {}
        self.tree.setCurrentItem(self.tree.topLevelItem(0))
        self.refresh()

    def refresh(self):
        if not self.bank:
            return
        tf = getattr(self, "tree_filter", {})
        qs = self.bank.search(qtype=self.f_type.currentData() or None, muc_do=self.f_muc.currentData() or None,
                              id_like=self.f_id.text().strip() or None, text=self.f_text.text().strip() or None, tag=self.f_tag.text().strip() or None,
                              lop=tf.get("lop"), mon=tf.get("mon"), chuong=tf.get("chuong"))
        used = dict(self.bank.con.execute("SELECT id, used_count FROM questions").fetchall())
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(qs))
        for r, q in enumerate(qs):
            idc = parse_id(q.id_code) if q.id_code else None
            vals = [q.db_id, TEN_LOAI[q.qtype], q.id_code, TEN_MUC.get(idc.muc_do, "") if idc else "",
                    q.answer_text, used.get(q.db_id, 0), " ".join(q.stem.split())]
            for c, v in enumerate(vals):
                it = QTableWidgetItem()
                it.setData(Qt.ItemDataRole.DisplayRole, v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, q.db_id)
                if c == 1 and validate(q):
                    it.setForeground(QColor("#c00000"))
                    it.setToolTip("; ".join(validate(q)))
                self.table.setItem(r, c, it)
        self.table.setSortingEnabled(True)
        self.statusBar().showMessage(f"Hiển thị {len(qs)} / {self.bank.count()} câu  •  Kho: {self.bank.path}")
        self.info.clear()
        self.code.clear()

    def selected_ids(self) -> list[int]:
        rows = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in rows]

    def visible_ids(self) -> list[int]:
        return [self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in range(self.table.rowCount())]

    def on_select(self):
        ids = self.selected_ids()
        if not ids:
            return
        q = self.bank.get(ids[0])
        if not q:
            return
        idc = parse_id(q.id_code) if q.id_code else None
        warns = validate(q)
        html = [f"<h3>Câu #{q.db_id} – {TEN_LOAI[q.qtype]}</h3>",
                f"<p><b>ID:</b> {q.id_code or '<i>chưa có</i>'}<br>",
                f"<b>Phân loại:</b> {idc.describe() if idc else '—'}<br>",
                "".join(f"&nbsp;&nbsp;↳ {n}<br>" for n in self.bank.id_names(q.id_code)),
                f"<b>Đáp án:</b> <span style='color:#c00000;font-weight:bold'>{q.answer_text or '—'}</span><br>",
                f"<b>Nguồn/nhãn:</b> {', '.join(q.tags) or '—'}</p>"]
        if q.choices:
            labels = "ABCD" if q.qtype == "TN" else "abcd"
            html.append("<ul>" + "".join(
                f"<li>{'<b>' if ok else ''}{labels[i] if i < 4 else i}. {c}{'</b>' if ok else ''}</li>"
                for i, (c, ok) in enumerate(zip(q.choices, q.correct))) + "</ul>")
        if warns:
            html.append("<p style='color:#c00000'><b>Cảnh báo:</b><br>" + "<br>".join(warns) + "</p>")
        else:
            html.append("<p style='color:#0b7a0b'>✔ Câu hỏi hợp lệ</p>")
        self.info.setHtml("".join(html))
        self.code.setPlainText(q.to_latex())
        sims = self.bank.similar(q)
        self.sim.setRowCount(len(sims))
        for r, x in enumerate(sims):
            for c, v in enumerate((x.db_id, x.id_code, x.answer_text, " ".join(x.stem.split()))):
                it = QTableWidgetItem(str(v))
                it.setData(Qt.ItemDataRole.UserRole, x.db_id)
                self.sim.setItem(r, c, it)
        self.tabs.setTabText(2, f"Câu tương tự ({len(sims)})")
        hs = self.bank.history(q.db_id)
        self.hist.setRowCount(len(hs))
        for r, h in enumerate(hs):
            for c, v in enumerate((h["at"].replace("T", " "), h["action"], " ".join(h["old_raw"].split())[:200])):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, h["hid"])
                self.hist.setItem(r, c, it)
        self.tabs.setTabText(3, f"Lịch sử sửa ({len(hs)})")

    def restore_version(self):
        rows = sorted({i.row() for i in self.hist.selectedIndexes()})
        if not rows:
            QMessageBox.information(self, "Lịch sử", "Chọn một dòng trong bảng lịch sử.")
            return
        hid = self.hist.item(rows[0], 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Khôi phục", "Đưa câu về bản đã chọn? (bản hiện tại vẫn được lưu "
                                "trong lịch sử)") == QMessageBox.StandardButton.Yes:
            self.bank.restore(hid)
            self.build_tree()
            self.refresh()

    def restore_deleted(self):
        rows = self.bank.con.execute(
            "SELECT h.hid, h.at, h.question_id, h.old_raw FROM history h WHERE h.action='xoá' AND "
            "NOT EXISTS (SELECT 1 FROM questions q WHERE q.id=h.question_id) ORDER BY h.hid DESC LIMIT 500").fetchall()
        if not rows:
            QMessageBox.information(self, "Khôi phục", "Không có câu nào đã xoá cần khôi phục.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Khôi phục câu đã xoá")
        dlg.resize(900, 500)
        lay = QVBoxLayout(dlg)
        t = QTableWidget(len(rows), 3)
        t.setHorizontalHeaderLabels(["Xoá lúc", "Câu", "Nội dung"])
        t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, h in enumerate(rows):
            for c, v in enumerate((h["at"].replace("T", " "), f"#{h['question_id']}", " ".join(h["old_raw"].split())[:200])):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, h["hid"])
                t.setItem(r, c, it)
        lay.addWidget(t)
        b = QPushButton("Khôi phục các câu đã chọn")
        b.setObjectName("primary")
        lay.addWidget(b)

        def go():
            sel = sorted({i.row() for i in t.selectedIndexes()})
            for r in sel:
                self.bank.restore(t.item(r, 0).data(Qt.ItemDataRole.UserRole))
            self.build_tree()
            self.refresh()
            QMessageBox.information(dlg, "Khôi phục", f"Đã khôi phục {len(sel)} câu.")
            dlg.accept()
        b.clicked.connect(go)
        dlg.exec()

    def find_replace(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Tìm và thay thế trong kho")
        f = QFormLayout(dlg)
        e_find, e_rep = QLineEdit(), QLineEdit()
        c_re = QCheckBox("Dùng biểu thức chính quy (regex)")
        scope = QComboBox()
        scope.addItem("Câu đang chọn", "sel")
        scope.addItem("Câu đang hiển thị (theo bộ lọc)", "vis")
        scope.addItem("Toàn bộ kho", "all")
        if not self.selected_ids():
            scope.setCurrentIndex(1)
        cs = {k: QCheckBox(v) for k, v in (("stem", "Đề bài"), ("choices", "Phương án / đáp án"),
                                           ("solution", "Lời giải"))}
        for c in cs.values():
            c.setChecked(True)
        f.addRow("Tìm", e_find)
        f.addRow("Thay bằng", e_rep)
        f.addRow("", c_re)
        f.addRow("Phạm vi", scope)
        row = QHBoxLayout()
        for c in cs.values():
            row.addWidget(c)
        f.addRow("Trong", row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("Thay tất cả")
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        f.addRow(bb)
        if not dlg.exec() or not e_find.text():
            return
        ids = {"sel": self.selected_ids(), "vis": self.visible_ids(), "all": None}[scope.currentData()]
        try:
            n = self.bank.replace_text(e_find.text(), e_rep.text(), ids, c_re.isChecked(),
                                       tuple(k for k, c in cs.items() if c.isChecked()))
        except re.error as e:
            QMessageBox.warning(self, "Regex sai", str(e))
            return
        self.refresh()
        QMessageBox.information(self, "Thay thế", f"Đã sửa {n} câu. Có thể hoàn tác từng câu ở tab «Lịch sử sửa».")

    def near_dups(self):
        thr, ok = QInputDialog.getInt(self, "Câu gần trùng", "Độ giống tối thiểu (%)", 80, 30, 100)
        if not ok:
            return
        qs = self.bank.search()
        pairs = tools.near_duplicates(qs, thr / 100)
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Câu gần trùng (≥ {thr}%) – {len(pairs)} cặp")
        dlg.resize(1100, 600)
        lay = QVBoxLayout(dlg)
        t = QTableWidget(len(pairs), 5)
        t.setHorizontalHeaderLabels(["Giống", "Câu 1", "Câu 2", "Nội dung câu 1", "Nội dung câu 2"])
        t.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        for r, (i, j, sc) in enumerate(pairs):
            a, b_ = qs[i], qs[j]
            for c, v in enumerate((f"{sc:.0%}", f"#{a.db_id} [{a.id_code}]", f"#{b_.db_id} [{b_.id_code}]",
                                   " ".join(a.stem.split())[:150], " ".join(b_.stem.split())[:150])):
                it = QTableWidgetItem(v)
                it.setData(Qt.ItemDataRole.UserRole, b_.db_id)
                t.setItem(r, c, it)
        lay.addWidget(t)
        b = QPushButton("Xoá «Câu 2» của các cặp đã chọn")
        lay.addWidget(b)

        def go():
            ids = sorted({t.item(r, 0).data(Qt.ItemDataRole.UserRole) for r in {i.row() for i in t.selectedIndexes()}})
            if ids and QMessageBox.question(dlg, "Xoá", f"Xoá {len(ids)} câu? (khôi phục được ở "
                                            "Câu hỏi → Khôi phục câu đã xoá)") == QMessageBox.StandardButton.Yes:
                self.bank.delete(ids)
                self.build_tree()
                self.refresh()
                dlg.accept()
        b.clicked.connect(go)
        dlg.exec()

    def check_update(self):
        import urllib.request
        url = "https://api.github.com/repos/HuynhDucVu/toan11/releases/latest"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "NganHangDe"}),
                                        timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Cập nhật", f"Không kiểm tra được (cần mạng Internet):\n{e}")
            return
        latest = data.get("tag_name", "").lstrip("v")

        def ver(x):
            return tuple(int(p) for p in re.findall(r"\d+", x)[:3])
        if latest and ver(latest) > ver(__version__):
            if QMessageBox.question(self, "Có bản mới", f"Đang dùng bản {__version__}. Đã có bản {latest}.\n"
                                    "Mở trang tải về?") == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(data.get("html_url", "")))
        else:
            QMessageBox.information(self, "Cập nhật", f"Bạn đang dùng bản mới nhất ({__version__}).")

    def edit_similar(self, idx):
        db_id = self.sim.item(idx.row(), 0).data(Qt.ItemDataRole.UserRole)
        if EditDialog(self, db_id).exec():
            self.refresh()

    # ---------------------------------------------------------- kho: sao lưu / gộp / tách / Map ID
    def backup_bank(self):
        from datetime import datetime
        base = os.path.splitext(os.path.basename(self.bank.path))[0]
        name = f"{base}_saoluu_{datetime.now():%Y%m%d_%H%M}.db"
        p, _ = QFileDialog.getSaveFileName(self, "Sao lưu kho", os.path.join(os.path.dirname(
            os.path.abspath(self.bank.path)), name), "Kho câu hỏi (*.db)")
        if p:
            self.bank.backup(p)
            QMessageBox.information(self, "Sao lưu", f"Đã sao lưu {self.bank.count()} câu ra\n{p}\n\n"
                                    "Khôi phục: menu Tệp → Mở kho câu hỏi và chọn file sao lưu.")

    def merge_bank(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn kho cần gộp vào", "", "Kho câu hỏi (*.db)")
        if p and os.path.abspath(p) != os.path.abspath(self.bank.path):
            added, dup = self.bank.merge_from(p)
            self.build_tree()
            self.refresh()
            QMessageBox.information(self, "Gộp kho", f"Thêm {added} câu, bỏ qua {dup} câu trùng.")

    def split_bank(self):
        ids = self.selected_ids() or self.visible_ids()
        if not ids:
            return
        p, _ = QFileDialog.getSaveFileName(self, f"Tách {len(ids)} câu ra kho mới", "kho_moi.db",
                                           "Kho câu hỏi (*.db)")
        if p:
            n = self.bank.export_subset(ids, p)
            QMessageBox.information(self, "Tách kho", f"Đã chép {n} câu sang\n{p}")

    def assign_ids(self):
        ids = self.selected_ids()
        if ids:
            qs = [self.bank.get(i) for i in ids]
        else:
            qs = [q for q in self.bank.search() if not q.id_code]
            if not qs:
                QMessageBox.information(self, "Gán ID", "Hãy chọn các câu cần gán/đổi ID trong bảng "
                                        "(kho hiện không có câu nào thiếu ID).")
                return
        if AssignIdDialog(self, qs, [f"Kho #{q.db_id}" for q in qs]).exec():
            self.refresh()

    def edit_idmap(self):
        if IdMapDialog(self).exec():
            self.build_tree()
            self.refresh()

    # ---------------------------------------------------------- thao tác câu hỏi
    def import_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex", self.settings.value("last_dir", ""),
                                                "LaTeX (*.tex);;Tất cả (*.*)")
        if not paths:
            return
        self.settings.setValue("last_dir", os.path.dirname(paths[0]))
        lines, warn_total = [], 0
        for p in paths:
            try:
                qs = parse_file(p)
            except Exception as e:  # noqa: BLE001
                lines.append(f"✘ {os.path.basename(p)}: lỗi đọc file – {e}")
                continue
            added = sum(1 for q in qs if self.bank.add(q, p))
            warn_total += sum(1 for q in qs if validate(q))
            lines.append(f"✔ {os.path.basename(p)}: {len(qs)} câu, thêm {added}, trùng {len(qs) - added}")
        if warn_total:
            lines.append(f"\n{warn_total} câu có cảnh báo (tô đỏ ở cột Loại, xem chi tiết khi chọn câu).")
        self.build_tree()
        self.refresh()
        QMessageBox.information(self, "Nhập dữ liệu", "\n".join(lines))

    def add_question(self):
        if EditDialog(self, None).exec():
            self.build_tree()
            self.refresh()

    def edit_question(self):
        ids = self.selected_ids()
        if not ids:
            QMessageBox.information(self, "Sửa câu", "Hãy chọn một câu trong bảng.")
            return
        if EditDialog(self, ids[0]).exec():
            self.build_tree()
            self.refresh()

    def delete_questions(self):
        ids = self.selected_ids()
        if not ids:
            return
        if QMessageBox.question(self, "Xoá", f"Xoá {len(ids)} câu đã chọn khỏi kho?") == QMessageBox.StandardButton.Yes:
            self.bank.delete(ids)
            self.build_tree()
            self.refresh()

    def import_word(self):
        from .wordconv import PandocMissing, import_docx
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn file Word", self.settings.value("last_dir", ""),
                                                "Word (*.docx)")
        if not paths:
            return
        tag, ok = QInputDialog.getText(self, "Nhập từ Word", "Nhãn nguồn gắn cho các câu (có thể để trống):")
        if not ok:
            return
        lines = []
        for p in paths:
            try:
                tex = import_docx(p, tag.strip())
            except PandocMissing as e:
                QMessageBox.warning(self, "Thiếu pandoc", str(e))
                return
            except Exception as e:  # noqa: BLE001
                lines.append(f"✘ {os.path.basename(p)}: {e}")
                continue
            out = os.path.splitext(p)[0] + "_tuWord.tex"
            with open(out, "w", encoding="utf-8") as f:
                f.write(tex)
            qs = parse_tex(tex)
            added = sum(1 for q in qs if self.bank.add(q, p))
            bad = sum(1 for q in qs if rv.worst(rv.review_question(q)) == rv.LOI)
            lines.append(f"✔ {os.path.basename(p)}: nhận dạng {len(qs)} câu, thêm {added} câu vào kho, "
                         f"{bad} câu cần xem lại (chưa rõ đáp án…). Bản LaTeX: {os.path.basename(out)}")
        self.build_tree()
        self.refresh()
        QMessageBox.information(self, "Nhập từ Word", "\n".join(lines) + "\n\nNên mở tab «Rà soát» để kiểm tra lại.")

    def export_other(self):
        ids = self.selected_ids() or self.visible_ids()
        if not ids:
            return
        kinds = ["Word (.docx) – có đánh dấu đáp án và lời giải", "Moodle XML", "Bài làm online (HTML)"]
        k, ok = QInputDialog.getItem(self, "Xuất câu", f"Xuất {len(ids)} câu sang:", kinds, 0, False)
        if not ok:
            return
        qs = [self.bank.get(i) for i in ids]
        ext = {0: "Word (*.docx)", 1: "Moodle XML (*.xml)", 2: "HTML (*.html)"}[kinds.index(k)]
        p, _ = QFileDialog.getSaveFileName(self, "Lưu thành", "cau_hoi." + ext.split("*.")[1].rstrip(")"), ext)
        if not p:
            return
        try:
            if kinds.index(k) == 0:
                from .wordconv import export_questions_docx
                export_questions_docx(qs, p)
            elif kinds.index(k) == 1:
                from .online import export_moodle
                export_moodle(qs, p)
            else:
                from .generator import ExamVersion, sections_from_questions
                from .online import version_html
                v = ExamVersion("ÔN TẬP", sections_from_questions(qs))
                with open(p, "w", encoding="utf-8") as f:
                    f.write(version_html(v, ten_de="LUYỆN TẬP", thoi_gian=max(15, len(qs) * 3)))
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Xuất câu", str(e))
            return
        QMessageBox.information(self, "Xuất câu", f"Đã xuất {len(qs)} câu ra\n{p}")

    def export_selected(self):
        ids = self.selected_ids() or self.visible_ids()
        if not ids:
            return
        p, _ = QFileDialog.getSaveFileName(self, f"Xuất {len(ids)} câu", "cau_hoi.tex", "LaTeX (*.tex)")
        if not p:
            return
        sol = QMessageBox.question(self, "Lời giải", "Xuất kèm lời giải?") == QMessageBox.StandardButton.Yes
        export_questions([self.bank.get(i) for i in ids], p, sol)
        QMessageBox.information(self, "Xuất", f"Đã xuất {len(ids)} câu ra\n{p}")

    def check_file(self):
        self.main_tabs.setCurrentWidget(self.tools_panel)
        self.tools_panel.check_file()

    def show_stats(self):
        self.main_tabs.setCurrentWidget(self.stats_panel)

    def open_review(self):
        self.main_tabs.setCurrentWidget(self.review_panel)

    def open_generator(self):
        self.main_tabs.setCurrentWidget(self.gen_panel)

    def about(self):
        QMessageBox.about(self, "Giới thiệu",
                          f"<h3>{APP_NAME} {__version__}</h3>"
                          "<p>Quản lý ngân hàng câu hỏi Toán định dạng LaTeX <code>ex_test</code>: "
                          "nhập file .tex, phân loại theo ID [0D2N1-2], lọc, chống trùng, "
                          "trộn đề theo ma trận, xuất mã đề – lời giải – đáp án.</p>")

    def closeEvent(self, e):
        if self.bank:
            self.bank.close()
        super().closeEvent(e)


# =====================================================================
class EditDialog(QDialog):
    """Thêm/sửa 1 câu bằng mã LaTeX, có mẫu sẵn cho 4 loại câu."""

    def __init__(self, win: MainWindow, db_id: int | None):
        super().__init__(win)
        self.win, self.db_id = win, db_id
        self.setWindowTitle(f"Sửa câu #{db_id}" if db_id else "Thêm câu mới")
        self.resize(900, 620)
        lay = QVBoxLayout(self)
        if not db_id:
            row = QHBoxLayout()
            row.addWidget(QLabel("Chèn mẫu:"))
            for k, v in TEN_LOAI.items():
                b = QPushButton(v)
                b.clicked.connect(lambda _=False, k=k: self.editor.setPlainText(MAU_CAU[k]))
                row.addWidget(b)
            row.addStretch()
            lay.addLayout(row)
        self.editor = latex_editor()
        self.editor.setPlainText(win.bank.get(db_id).to_latex() if db_id else MAU_CAU["TN"])
        lay.addWidget(self.editor)
        self.msg = QLabel()
        lay.addWidget(self.msg)
        self.editor.textChanged.connect(self.check)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Save).setText("Lưu")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("Huỷ")
        bb.accepted.connect(self.save)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.check()

    def _parse(self):
        qs = parse_tex(self.editor.toPlainText())
        return qs[0] if len(qs) == 1 else None, len(qs)

    def check(self):
        q, n = self._parse()
        if not q:
            self.msg.setText(f"<span style='color:#c00000'>Cần đúng 1 khối \\begin{{ex}}…\\end{{ex}} (đang có {n})</span>")
            return
        ws = validate(q)
        self.msg.setText(f"<b>{TEN_LOAI[q.qtype]}</b> • ID {q.id_code or '?'} • Đáp án: <b>{q.answer_text or '—'}</b> • "
                         + (f"<span style='color:#c00000'>{'; '.join(ws)}</span>" if ws
                            else "<span style='color:#0b7a0b'>hợp lệ</span>"))

    def save(self):
        q, n = self._parse()
        if not q:
            QMessageBox.warning(self, "Lỗi", f"Cần đúng 1 khối câu hỏi (đang có {n}).")
            return
        ws = validate(q)
        if ws and QMessageBox.question(self, "Cảnh báo", "\n".join(ws) + "\n\nVẫn lưu?") != QMessageBox.StandardButton.Yes:
            return
        if self.db_id:
            self.win.bank.update(self.db_id, q)
        elif self.win.bank.add(q, "nhap-tay") is None:
            QMessageBox.warning(self, "Trùng", "Câu này đã có trong kho.")
            return
        self.accept()


# =====================================================================
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
        body.addWidget(scroll_of(lay), 2)

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
        self.e_tpl[0].setPlaceholderText("để trống = dùng mẫu có sẵn")
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
        self.c_pdf = QCheckBox("Biên dịch PDF bằng xelatex (nếu máy có cài)")
        self.c_pdf.setEnabled(bool(shutil.which("xelatex")))
        for c in (self.c_diff,):
            fl.addRow("", c)
        fl.addRow("  Trùng tối đa giữa 2 mã", self.sp_overlap)
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
        row = QHBoxLayout()
        for text, fn in (("Thêm dòng", self.add_row), ("Xoá dòng", self.del_row),
                         ("Mở ma trận…", self.load_matrix), ("Lưu ma trận…", self.save_matrix),
                         ("Ma trận từ đề có sẵn…", self.matrix_from_exam),
                         ("In ma trận đặc tả…", self.print_matrix),
                         ("Kiểm tra số câu", self.update_avail)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        self.l_total = QLabel()
        row.addWidget(self.l_total)
        gl.addLayout(row)
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
        p, _ = QFileDialog.getOpenFileName(self, "Mở ma trận", "", "Ma trận (*.json)")
        if not p:
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
        try:
            if self.c_preview.isChecked() and not self.c_diff.isChecked():
                import random as _r
                from .generator import pick_questions
                sections = pick_questions(self.win.bank, rules, _r.Random(seed), self.c_unused.isChecked())
                dlg = SwapDialog(self, sections, rules)
                if not dlg.exec():
                    return
                sections = dlg.sections
            ov = self.sp_overlap.value()
            vs = make_versions(self.win.bank, rules, len(codes), codes=codes,
                               seed=seed, same_questions=not self.c_diff.isChecked(),
                               prefer_unused=self.c_unused.isChecked(), options=self.opts.mix_options(),
                               max_overlap=(ov / 100 if self.c_diff.isChecked() and ov < 100 else None),
                               sections=sections)
        except NotEnoughQuestions as e:
            QMessageBox.warning(self, "Không đủ câu", str(e))
            return
        out = self.e_out[0].text()
        try:
            files = export_versions(vs, out, template_path=self.e_tpl[0].text() or None,
                                    ten_de=self.e_ten.text(), truong=self.e_truong.text(),
                                    thoi_gian=self.e_tg.value(), options=self.export_options())
        except OSError as e:
            QMessageBox.critical(self, "Lỗi ghi file", str(e))
            return
        self.win.bank.mark_used({q.db_id for v in vs for q in v.all_questions()})
        self.win.refresh()
        for k, v in (("ten", self.e_ten.text()), ("truong", self.e_truong.text()), ("tg", self.e_tg.value()),
                     ("n", self.e_n.value()), ("ma", self.e_ma.text()), ("out", out),
                     ("tpl", self.e_tpl[0].text()), ("matrix", json.dumps(rd, ensure_ascii=False))):
            self.st.setValue(f"gen/{k}", v)
        self.opts.save()
        self.st.setValue("gen/check2026", self.c_check2026.isChecked())
        self.st.setValue("gen/overlap", self.sp_overlap.value())
        for k, e in self.hdr.items():
            self.st.setValue(f"gen/hdr_{k}", e.text())
        extra = ""
        if self.c_pdf.isChecked():
            fails = compile_pdfs([f for f in files if f.endswith(".tex")], out)
            extra = "<p>Biên dịch PDF: " + ("thành công" if not fails else "lỗi ở " + ", ".join(fails)) + "</p>"
        ResultDialog(self, vs, out, extra).exec()

    def export_options(self):
        o = self.opts.export_options()
        o.header = {k: e.text() for k, e in self.hdr.items()}
        return o

    def print_matrix(self):
        rd = self.rules_dicts()
        if not rd:
            return
        p, _ = QFileDialog.getSaveFileName(self, "In ma trận đặc tả", "ma_tran_dac_ta.xlsx",
                                           "Excel (*.xlsx);;LaTeX (*.tex)")
        if p:
            from .exporter import matrix_spec
            matrix_spec(self.win.bank, [Rule.from_dict(r) for r in rd], p)
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


# =====================================================================
class MixOptionsBox(QWidget):
    """Nhóm ô tick tuỳ chọn trộn đề (dùng chung cho tab Tạo đề và Trộn đề từ file)."""
    ITEMS = (("shuffle_q", "Trộn thứ tự câu trong từng phần", True),
             ("shuffle_tn", "Trộn phương án A, B, C, D", True),
             ("shuffle_ds", "Trộn thứ tự ý a, b, c, d câu Đúng/Sai", True),
             ("balance", "Cân bằng số đáp án A/B/C/D trong mỗi đề", True),
             ("first_original", "Mã đề đầu tiên giữ nguyên thứ tự (đề gốc)", False),
             ("sort_by_level", "Trong mỗi phần xếp câu từ dễ đến khó (Nhận biết → Vận dụng cao)", False))

    def __init__(self, settings, prefix):
        super().__init__()
        self.st, self.prefix = settings, prefix
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.boxes = {}
        for key, text, default in self.ITEMS:
            c = QCheckBox(text)
            v = self.st.value(f"{prefix}/mix_{key}", default)
            c.setChecked(v if isinstance(v, bool) else str(v).lower() == "true")
            lay.addWidget(c)
            self.boxes[key] = c

    def options(self) -> MixOptions:
        return MixOptions(**{k: c.isChecked() for k, c in self.boxes.items()})

    def save(self):
        for k, c in self.boxes.items():
            self.st.setValue(f"{self.prefix}/mix_{k}", c.isChecked())


class SwapDialog(QDialog):
    """Xem bộ câu đã chọn theo ma trận; «đổi câu» = thay bằng câu khác cùng dòng ma trận."""

    def __init__(self, panel, sections, rules):
        super().__init__(panel)
        self.panel, self.rules = panel, rules
        self.bank = panel.win.bank
        self.sections = {k: list(v) for k, v in sections.items()}
        self.setWindowTitle("Xem trước bộ câu – đổi câu trước khi trộn")
        self.resize(1150, 680)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chọn câu muốn thay rồi bấm <b>Đổi ngẫu nhiên</b> hoặc <b>Chọn câu thay…</b>. "
                             "Câu thay luôn cùng dòng ma trận (cùng loại, cùng mẫu ID, cùng mức độ)."))
        split = QSplitter(Qt.Orientation.Vertical)
        self.t = QTableWidget(0, 5)
        self.t.setHorizontalHeaderLabels(["Phần", "Câu", "ID", "Đáp án", "Nội dung"])
        self.t.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.t.itemSelectionChanged.connect(self.show_code)
        split.addWidget(self.t)
        self.code = latex_editor(read_only=True)
        split.addWidget(self.code)
        split.setSizes([420, 200])
        lay.addWidget(split, 1)
        row = QHBoxLayout()
        for text, fn in (("🎲 Đổi ngẫu nhiên", self.swap_random), ("Chọn câu thay…", self.swap_pick)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        ok = QPushButton("Dùng bộ câu này để trộn")
        ok.setObjectName("primary")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Huỷ")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.fill()

    def rows(self):
        return [(s, i, q) for s in ("TN", "DS", "KQ", "TL") for i, q in enumerate(self.sections.get(s, []))]

    def fill(self):
        rows = self.rows()
        self.t.setRowCount(len(rows))
        part = {"TN": "I", "DS": "II", "KQ": "III", "TL": "IV"}
        for r, (s, i, q) in enumerate(rows):
            for c, v in enumerate((part[s], str(i + 1), q.id_code, q.answer_text, " ".join(q.stem.split())[:200])):
                self.t.setItem(r, c, QTableWidgetItem(v))

    def current(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        return (self.rows()[rows[0]], rows[0]) if rows else (None, None)

    def show_code(self):
        (item, _r) = self.current()
        if item:
            self.code.setPlainText(item[2].to_latex())

    def used(self):
        return {q.db_id for qs in self.sections.values() for q in qs}

    def _replace(self, new):
        (s, i, old), r = self.current()
        new.rule_index = getattr(old, "rule_index", 0)
        self.sections[s][i] = new
        self.fill()
        self.t.selectRow(r)
        self.show_code()

    def swap_random(self):
        from .generator import replacement_pool
        import random as _r
        (item, _row) = self.current()
        if not item:
            return
        pool = replacement_pool(self.bank, self.rules, item[2], self.used())
        if not pool:
            QMessageBox.information(self, "Đổi câu", "Kho không còn câu nào khác cùng dòng ma trận.")
            return
        self._replace(_r.choice(pool))

    def swap_pick(self):
        from .generator import replacement_pool
        (item, _row) = self.current()
        if not item:
            return
        pool = replacement_pool(self.bank, self.rules, item[2], self.used())
        if not pool:
            QMessageBox.information(self, "Đổi câu", "Kho không còn câu nào khác cùng dòng ma trận.")
            return
        labels = [f"#{q.db_id} [{q.id_code}] " + " ".join(q.stem.split())[:110] for q in pool]
        choice, ok = QInputDialog.getItem(self, "Chọn câu thay", f"{len(pool)} câu cùng dòng ma trận:", labels, 0, False)
        if ok:
            self._replace(pool[labels.index(choice)])


class ExamOptionsBox(QTabWidget):
    """Mục «Tuỳ chọn trộn đề»: mã đề · trộn · trình bày · phiếu chấm (đáp án Excel cho TNMaker)."""

    def __init__(self, settings, prefix, show_codes=True):
        super().__init__()
        self.st, self.prefix = settings, prefix

        def val(key, default):
            v = self.st.value(f"{prefix}/opt_{key}", default)
            if isinstance(default, bool):
                return v if isinstance(v, bool) else str(v).lower() == "true"
            return type(default)(v)

        def combo(items, key, default):
            cb = QComboBox()
            for text, data in items:
                cb.addItem(text, data)
            cb.setCurrentIndex(max(0, cb.findData(val(key, default))))
            return cb

        # Mã đề
        self.w_codes = QWidget()
        f = QFormLayout(self.w_codes)
        self.cb_codemode = combo([("Liên tiếp (101, 102, …)", "seq"), ("Ngẫu nhiên, không trùng", "rand")],
                                 "codemode", "seq")
        self.sp_start = QSpinBox()
        self.sp_start.setRange(0, 9999)
        self.sp_start.setValue(val("start", 101))
        self.cb_digits = combo([("3 chữ số (101)", 3), ("4 chữ số (0101)", 4)], "digits", 3)
        f.addRow("Cách đánh mã", self.cb_codemode)
        f.addRow("Bắt đầu từ", self.sp_start)
        f.addRow("Độ dài mã", self.cb_digits)
        self.l_preview = QLabel()
        f.addRow("Ví dụ", self.l_preview)
        for w_ in (self.cb_codemode, self.cb_digits):
            w_.currentIndexChanged.connect(self._preview)
        self.sp_start.valueChanged.connect(self._preview)
        if show_codes:
            self.addTab(self.w_codes, "Mã đề")

        # Trộn
        self.mix = MixOptionsBox(settings, prefix)
        self.addTab(self.mix, "Trộn")

        # Trình bày
        w = QWidget()
        v = QVBoxLayout(w)
        self.c_renum = QCheckBox("Đánh số lại từ Câu 1 ở mỗi phần (như đề thi tốt nghiệp)")
        self.c_official = QCheckBox("Tiêu đề và lời dẫn từng phần theo mẫu đề thi tốt nghiệp")
        self.c_scoring = QCheckBox("In thang điểm (Phần I 0,25 · Phần II 0,1/0,25/0,5/1 · Phần III 0,5) trong file lời giải")
        self.c_showid = QCheckBox("In ID nhỏ sau mỗi câu trong file lời giải (bản giáo viên)")
        self.c_zip = QCheckBox("Nén toàn bộ kết quả thành 1 file .zip")
        for c, k in ((self.c_renum, "renumber"), (self.c_official, "official"), (self.c_scoring, "scoring"),
                     (self.c_showid, "showid"), (self.c_zip, "zip")):
            c.setChecked(val(k, False))
            v.addWidget(c)
        v.addStretch()
        self.addTab(w, "Trình bày")

        # Phiếu chấm TNMaker
        w = QWidget()
        f = QFormLayout(w)
        self.c_xlsx = QCheckBox("Xuất file đáp án Excel dap_an_TNMaker.xlsx")
        self.c_xlsx.setChecked(val("xlsx", True))
        self.cb_layout = combo([("Mỗi dòng 1 câu, mỗi cột 1 mã đề", "doc"), ("Mỗi dòng 1 mã đề, mỗi cột 1 câu", "ngang")],
                               "layout", "doc")
        self.cb_ds = combo([("Gộp 1 ô / câu (ĐSĐS)", "gop"), ("Tách 4 ô a, b, c, d", "tach")], "ds", "gop")
        self.cb_sym = combo([("Đ / S", "ĐS"), ("T / F", "TF"), ("1 / 0", "10")], "sym", "ĐS")
        self.cb_dec = combo([("Dấu phẩy (0,5)", ","), ("Dấu chấm (0.5)", ".")], "dec", ",")
        f.addRow(self.c_xlsx)
        f.addRow("Bố cục", self.cb_layout)
        f.addRow("Phần II Đúng/Sai", self.cb_ds)
        f.addRow("Kí hiệu Đúng/Sai", self.cb_sym)
        f.addRow("Phần III – thập phân", self.cb_dec)
        note = QLabel("Trong TNMaker: tạo bài thi theo mẫu phiếu tốt nghiệp (3 phần) → nhập đáp án từ file Excel → "
                      "chọn <code>dap_an_TNMaker.xlsx</code>. Nếu mẫu đáp án của TNMaker khác, đổi bố cục/kí hiệu ở trên. "
                      "File còn có sheet <i>Mã đề – câu gốc</i> để đối chiếu.")
        note.setWordWrap(True)
        f.addRow(note)
        self.addTab(w, "Phiếu chấm TNMaker")

        w = QWidget()
        v = QVBoxLayout(w)
        self.c_online = QCheckBox("Bài làm online: mỗi mã đề 1 file HTML (mở trên máy tính/điện thoại, nộp là có điểm)")
        self.c_online_sol = QCheckBox("   Hiện lời giải sau khi học sinh nộp bài")
        self.c_moodle = QCheckBox("File Moodle XML (nhập vào ngân hàng câu hỏi Moodle/LMS)")
        self.c_word = QCheckBox("File Word .docx mỗi mã đề (công thức Word gốc – cần cài pandoc)")
        from .wordconv import PandocMissing, pandoc_path
        try:
            pandoc_path()
        except PandocMissing:
            self.c_word.setEnabled(False)
            self.c_word.setToolTip("Chưa cài pandoc: tải tại pandoc.org/installing.html")
        for c, k, d in ((self.c_online, "online", False), (self.c_online_sol, "online_sol", True),
                        (self.c_moodle, "moodle", False), (self.c_word, "word", False)):
            c.setChecked(val(k, d))
            v.addWidget(c)
        note = QLabel("<i>Bài online dùng MathJax để hiện công thức (cần mạng khi mở). Đáp án nằm trong file "
                      "(đã mã hoá nhẹ) – phù hợp ôn tập, không dùng cho kì thi chính thức.</i>")
        note.setWordWrap(True)
        v.addWidget(note)
        v.addStretch()
        self.addTab(w, "Online / Word")
        self._preview()

    def _preview(self):
        self.l_preview.setText(", ".join(self.codes(3, preview=True)) + ", …")

    def codes(self, n, preview=False):
        rnd = self.cb_codemode.currentData() == "rand"
        if rnd and preview:
            return ["(ngẫu nhiên)"]
        return make_codes(n, self.sp_start.value(), self.cb_digits.currentData(), rnd)

    def mix_options(self) -> MixOptions:
        return self.mix.options()

    def export_options(self) -> ExportOptions:
        return ExportOptions(renumber=self.c_renum.isChecked(), official_titles=self.c_official.isChecked(),
                             scoring=self.c_scoring.isChecked(), answers_xlsx=self.c_xlsx.isChecked(),
                             tnmaker_layout=self.cb_layout.currentData(), ds_style=self.cb_ds.currentData(),
                             ds_symbols=self.cb_sym.currentData(), kq_decimal=self.cb_dec.currentData(),
                             show_id=self.c_showid.isChecked(), make_zip=self.c_zip.isChecked(),
                             online_html=self.c_online.isChecked(), online_solution=self.c_online_sol.isChecked(),
                             moodle=self.c_moodle.isChecked(), word=self.c_word.isChecked() and self.c_word.isEnabled())

    def apply_thpt2026(self):
        self.cb_codemode.setCurrentIndex(self.cb_codemode.findData("seq"))
        self.sp_start.setValue(101)
        self.cb_digits.setCurrentIndex(self.cb_digits.findData(4))
        for k, on in (("shuffle_q", True), ("shuffle_tn", True), ("shuffle_ds", False), ("balance", True),
                      ("first_original", False)):
            self.mix.boxes[k].setChecked(on)
        for c in (self.c_renum, self.c_official, self.c_scoring, self.c_xlsx):
            c.setChecked(True)

    def save(self):
        self.mix.save()
        for k, w_ in (("codemode", self.cb_codemode), ("digits", self.cb_digits), ("layout", self.cb_layout),
                      ("ds", self.cb_ds), ("sym", self.cb_sym), ("dec", self.cb_dec)):
            self.st.setValue(f"{self.prefix}/opt_{k}", w_.currentData())
        self.st.setValue(f"{self.prefix}/opt_start", self.sp_start.value())
        for k, c in (("renumber", self.c_renum), ("official", self.c_official), ("scoring", self.c_scoring),
                     ("xlsx", self.c_xlsx), ("showid", self.c_showid), ("zip", self.c_zip),
                     ("online", self.c_online), ("online_sol", self.c_online_sol), ("moodle", self.c_moodle),
                     ("word", self.c_word)):
            self.st.setValue(f"{self.prefix}/opt_{k}", c.isChecked())


def versions_report_html(vs, out_dir) -> str:
    """Báo cáo sau khi trộn: phân bố đáp án A/B/C/D từng mã đề và tỉ lệ trùng giữa các mã."""
    rows = "".join("<tr><td><b>{}</b></td>{}<td>{}</td></tr>".format(
        v.code, "".join(f"<td align=center>{n}</td>" for n in answer_distribution(v).values()),
        sum(len(v.sections.get(s) or []) for s in v.sections)) for v in vs)
    html = (f"<p>Đã tạo <b>{len(vs)}</b> mã đề trong thư mục:<br><code>{out_dir}</code></p>"
            "<p><b>Phân bố đáp án phần trắc nghiệm</b></p>"
            "<table border=1 cellspacing=0 cellpadding=4><tr><th>Mã đề</th><th>A</th><th>B</th><th>C</th><th>D</th>"
            "<th>Tổng số câu</th></tr>" + rows + "</table>")
    ov = overlap_report(vs)
    if ov:
        mx = max(r for _, _, r in ov)
        html += (f"<p><b>Tỉ lệ câu trùng giữa các mã đề:</b> cao nhất {mx:.0%}"
                 + (" (cùng bộ câu, chỉ hoán vị)" if mx == 1 else "") + "</p>")
    html += ("<p>File: <code>de_*.tex</code> (đề), <code>loigiai_*.tex</code> (lời giải + bảng đáp án), "
             "<code>dap_an.csv</code>, <code>dap_an_bang.csv</code> (mỗi mã đề một dòng).</p>")
    return html


class ResultDialog(QDialog):
    def __init__(self, parent, vs, out_dir, extra=""):
        super().__init__(parent)
        self.setWindowTitle("Kết quả tạo đề")
        self.resize(620, 480)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setHtml(versions_report_html(vs, out_dir) + extra)
        lay.addWidget(tb)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Mở thư mục kết quả")
        b.setObjectName("primary")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out_dir))))
        c = QPushButton("Đóng")
        c.clicked.connect(self.accept)
        row.addWidget(b)
        row.addWidget(c)
        lay.addLayout(row)


class IdMapDialog(QDialog):
    """Sửa bảng giải nghĩa ID theo định dạng Map ID phân cấp bằng gạch ngang (dùng chung với file Map_ID.tex)."""

    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Giải nghĩa ID (Map ID)")
        self.resize(820, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Định dạng phân cấp: <code>-[0] Lớp 10</code>, <code>----[D] Môn</code>, "
                             "<code>-------[1] Chương</code>, <code>----------[1] Bài</code>, "
                             "<code>-------------[1] Dạng</code> (1/4/7/10/13 gạch). Dòng bắt đầu bằng % là chú thích.<br>"
                             "Có thể nạp thẳng file <b>Map_ID.tex</b> đang dùng với các phần mềm khác."))
        self.ed = QPlainTextEdit()
        self.ed.setFont(QFont("Consolas", 11))
        self.ed.setPlainText(to_dash_text(win.bank.idmap()))
        lay.addWidget(self.ed)
        self.info = QLabel()
        lay.addWidget(self.info)
        self.ed.textChanged.connect(self.update_info)
        row = QHBoxLayout()
        for text, fn in (("Nạp file Map ID (.tex/.txt)…", self.load), ("Xuất file Map ID…", self.export)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        ok = QPushButton("Lưu")
        ok.setObjectName("primary")
        ok.clicked.connect(self.save)
        cancel = QPushButton("Huỷ")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.update_info()

    def update_info(self):
        m = parse_map_text(self.ed.toPlainText())
        n = {lv: 0 for lv in range(1, 6)}
        for k in m:
            if not k.startswith("#"):
                n[len(k.split("-")[0]) + ("-" in k)] += 1
        dups = dash_duplicates(self.ed.toPlainText())
        txt = (f"{n[1]} lớp · {n[2]} môn · {n[3]} chương · {n[4]} bài · {n[5]} dạng")
        if dups:
            txt += (f" — <span style='color:#c00000'>{len(dups)} mã bị khai báo trùng (giữ mục đầu): "
                    + "; ".join(f"{k} «{a}» / «{b}»" for k, a, b in dups[:5]) + "</span>")
        self.info.setText(txt)

    def load(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file Map ID", "",
                                           "Map ID (*.tex *.txt);;Tất cả (*.*)")
        if not p:
            return
        with open(p, encoding="utf-8-sig") as f:
            text = f.read()
        new = parse_map_text(text)
        if not new:
            QMessageBox.warning(self, "Map ID", "Không đọc được mục nào trong file này.")
            return
        cur = parse_map_text(self.ed.toPlainText())
        if cur and QMessageBox.question(self, "Map ID", f"File có {len(new)} mục. Thay toàn bộ bảng hiện tại?\n"
                                        "(Chọn No để gộp thêm vào bảng hiện tại)") != QMessageBox.StandardButton.Yes:
            cur.update(new)
            new = cur
        self.ed.setPlainText(to_dash_text(new))
        dups = dash_duplicates(text)
        if dups:
            QMessageBox.warning(self, "Map ID có mã trùng", "Các mã sau được khai báo 2 lần, phần mềm giữ mục đầu:\n\n"
                                + "\n".join(f"{k}: «{a}» / «{b}»" for k, a, b in dups))

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Xuất file Map ID", "Map_ID.tex", "Map ID (*.tex);;Văn bản (*.txt)")
        if p:
            save_map(parse_map_text(self.ed.toPlainText()), p)

    def save(self):
        self.win.bank.set_idmap(parse_map_text(self.ed.toPlainText()), replace=True)
        self.accept()


# =====================================================================
class IdPicker(QWidget):
    """Bộ chọn ID theo Map ID: Lớp → Môn → Chương → Bài → Dạng + Mức độ. Mỗi ô có lựa chọn «giữ nguyên»."""
    KEEP = None
    LABELS = ("Lớp", "Môn", "Chương", "Bài", "Dạng")

    def __init__(self, mapping: dict[str, str]):
        super().__init__()
        self.tree = IdTree(mapping)
        lay = QFormLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.cbs = []
        for i, lb in enumerate(self.LABELS):
            cb = QComboBox()
            cb.setMinimumWidth(320)
            cb.currentIndexChanged.connect(lambda _=0, i=i: self._changed(i))
            lay.addRow(lb, cb)
            self.cbs.append(cb)
        self.cb_md = QComboBox()
        self.cb_md.addItem("(giữ nguyên)", self.KEEP)
        for k, v in TEN_MUC.items():
            self.cb_md.addItem(f"[{k}] {v}", k)
        lay.addRow("Mức độ", self.cb_md)
        self.preview = QLabel()
        lay.addRow("ID", self.preview)
        self.cb_md.currentIndexChanged.connect(self._show)
        self._fill(0)

    def _fill(self, i):
        for j in range(i, 5):
            cb = self.cbs[j]
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("(giữ nguyên)", self.KEEP)
            parts = self.parts()[:j]
            if len(parts) == j and all(p is not self.KEEP for p in parts):
                for code, name in self.tree.children(parts):
                    cb.addItem(f"[{code}] {name}", code)
            cb.blockSignals(False)
        self._show()

    def _changed(self, i):
        if i < 4:
            self._fill(i + 1)
        self._show()

    def parts(self):
        return [cb.currentData() for cb in self.cbs]

    def level(self):
        return self.cb_md.currentData()

    def _show(self):
        p = ["?" if x is self.KEEP else x for x in self.parts()]
        md = self.level() or "?"
        self.preview.setText(f"<b>{p[0]}{p[1]}{p[2]}{md}{p[3]}-{p[4]}</b> &nbsp; (? = giữ nguyên theo ID cũ)")

    def apply_to(self, old_id: str) -> str | None:
        """Ghép phần đã chọn với ID cũ; trả về None nếu còn phần chưa xác định."""
        idc = parse_id(old_id) if old_id else None
        old = [idc.lop, idc.mon, idc.chuong, idc.bai, idc.dang] if idc else [None] * 5
        p = [o if x is self.KEEP else x for x, o in zip(self.parts(), old)]
        md = self.level() or (idc.muc_do if idc else None)
        if any(x is None for x in p[:4]) or md is None:
            return None
        return f"{p[0]}{p[1]}{p[2]}{md}{p[3]}" + (f"-{p[4]}" if p[4] else "")


class AssignIdDialog(QDialog):
    """Gán ID cho nhiều câu: gợi ý tự động (kho + Map ID), chọn theo Map ID, chỉ đổi mức độ; lưu vào kho hoặc file mới."""
    COLS = ["", "Câu", "ID hiện tại", "ID mới", "Độ giống", "Nội dung"]

    def __init__(self, win: MainWindow, questions, labels, source_file: str | None = None):
        super().__init__(win)
        self.win, self.qs, self.labels, self.src = win, questions, labels, source_file
        self.setWindowTitle("Gán ID" + (f" – {os.path.basename(source_file)}" if source_file else " – kho câu hỏi"))
        self.resize(1250, 760)
        self.mapping = win.bank.idmap()
        self.sugs = [[] for _ in questions]
        lay = QVBoxLayout(self)
        if not [k for k in self.mapping if not k.startswith("#")]:
            lay.addWidget(QLabel("<span style='color:#c00000'>Kho chưa có Map ID – vào <b>Công cụ → Giải nghĩa ID</b> "
                                 "để nạp file Map_ID.tex thì mới chọn ID theo tên chương/bài/dạng và gợi ý theo tên được.</span>"))
        top = QHBoxLayout()
        lay.addLayout(top, 1)

        left = QVBoxLayout()
        top.addLayout(left, 3)
        self.t = QTableWidget(len(questions), len(self.COLS))
        self.t.setHorizontalHeaderLabels(self.COLS)
        self.t.verticalHeader().setVisible(False)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for c, w_ in enumerate((30, 110, 90, 100, 70)):
            self.t.setColumnWidth(c, w_)
        self.t.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        for r, (q, lb) in enumerate(zip(questions, labels)):
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.t.setItem(r, 0, chk)
            for c, v in ((1, lb), (2, q.id_code or "—"), (3, ""), (4, ""), (5, " ".join(q.stem.split())[:200])):
                it = QTableWidgetItem(v)
                if c != 3:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.t.setItem(r, c, it)
        self.t.itemSelectionChanged.connect(self.on_select)
        left.addWidget(self.t)
        row = QHBoxLayout()
        for text, fn in (("Chọn hết", lambda: self.set_all(True)), ("Bỏ chọn", lambda: self.set_all(False)),
                         ("Chọn câu thiếu ID", self.check_missing)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        left.addLayout(row)

        right = QVBoxLayout()
        top.addLayout(right, 2)
        g = QGroupBox("1. Gợi ý tự động")
        gl = QFormLayout(g)
        self.cb_scope = QComboBox()
        self.cb_scope.addItem("Mọi lớp", "")
        tree = IdTree(self.mapping)
        for code, name in tree.children([]):
            self.cb_scope.addItem(name, code)
        self.cb_def_md = QComboBox()
        for k, v in TEN_MUC.items():
            self.cb_def_md.addItem(f"{v} (nếu câu chưa có mức độ)", k)
        b = QPushButton("Tìm gợi ý cho các câu")
        b.clicked.connect(self.compute)
        gl.addRow("Phạm vi", self.cb_scope)
        gl.addRow("Mức độ", self.cb_def_md)
        gl.addRow("", b)
        self.sp_thr = QSpinBox()
        self.sp_thr.setRange(5, 100)
        self.sp_thr.setValue(35)
        self.sp_thr.setSuffix(" %")
        b2 = QPushButton("Nhận gợi ý tốt nhất cho câu đã chọn có độ giống ≥")
        b2.clicked.connect(self.accept_best)
        h = QHBoxLayout()
        h.addWidget(b2)
        h.addWidget(self.sp_thr)
        gl.addRow(h)
        self.sug_list = QTableWidget(0, 3)
        self.sug_list.setHorizontalHeaderLabels(["ID gợi ý", "Giống", "Theo"])
        self.sug_list.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.sug_list.verticalHeader().setVisible(False)
        self.sug_list.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.sug_list.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.sug_list.setMaximumHeight(130)
        self.sug_list.doubleClicked.connect(self.use_suggestion)
        gl.addRow(QLabel("Gợi ý cho câu đang chọn (nhấp đúp để dùng):"))
        gl.addRow(self.sug_list)
        right.addWidget(g)

        g = QGroupBox("2. Chọn ID theo Map ID rồi áp cho câu đã chọn")
        gl = QVBoxLayout(g)
        self.picker = IdPicker(self.mapping)
        gl.addWidget(self.picker)
        b = QPushButton("Áp ID cho các câu đã chọn")
        b.clicked.connect(self.apply_picker)
        gl.addWidget(b)
        gl.addWidget(QLabel("<i>Để «giữ nguyên» ở mọi ô và chỉ chọn Mức độ ⇒ chỉ đổi mức độ.</i>"))
        right.addWidget(g)

        self.detail = QLabel()
        self.detail.setWordWrap(True)
        right.addWidget(self.detail)
        right.addStretch()

        row = QHBoxLayout()
        self.l_count = QLabel()
        row.addWidget(self.l_count)
        row.addStretch()
        ok = QPushButton("Lưu vào kho" if not source_file else "Lưu thành file mới…")
        ok.setObjectName("primary")
        ok.clicked.connect(self.save)
        cancel = QPushButton("Đóng")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.t.itemChanged.connect(self.update_count)
        self.check_missing()
        self.update_count()

    # --- tiện ích
    def set_all(self, v):
        for r in range(self.t.rowCount()):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if v else Qt.CheckState.Unchecked)

    def check_missing(self):
        for r, q in enumerate(self.qs):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Unchecked if q.id_code else Qt.CheckState.Checked)

    def checked_rows(self):
        return [r for r in range(self.t.rowCount()) if self.t.item(r, 0).checkState() == Qt.CheckState.Checked]

    def set_new(self, r, code, score=None):
        self.t.item(r, 3).setText(code)
        self.t.item(r, 3).setForeground(QColor("#0b7a0b") if parse_id(code) else QColor("#c00000"))
        if score is not None:
            self.t.item(r, 4).setText(f"{score:.0%}")

    def update_count(self, *_):
        n = sum(1 for r in range(self.t.rowCount()) if self.t.item(r, 3) and self.t.item(r, 3).text().strip())
        self.l_count.setText(f"{n} câu có ID mới · {len(self.checked_rows())} câu đang chọn")

    # --- gợi ý
    def compute(self):
        prefix = self.cb_scope.currentData() or ""
        bank_items = [q for q in self.win.bank.search() if q.id_code.startswith(prefix)]
        bs = Suggester(bank_items) if bank_items else None
        ms = MapSuggester(self.mapping, prefix)
        rows = self.checked_rows() or list(range(len(self.qs)))
        for r in rows:
            q = self.qs[r]
            idc = parse_id(q.id_code) if q.id_code else None
            md = idc.muc_do if idc else self.cb_def_md.currentData()
            b = bs.suggest(q, 3, exclude_db_id=q.db_id) if bs and len(bs) else []
            m = ms.suggest(q, md, 3) if len(ms) else []
            self.sugs[r] = combine(b, m, 4)
            if self.sugs[r]:
                self.t.item(r, 4).setText(f"{self.sugs[r][0].score:.0%}")
                self.t.item(r, 4).setToolTip(self.sugs[r][0].id_code)
        self.on_select()

    def on_select(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        self.sug_list.setRowCount(0)
        if not rows:
            return
        r = rows[0]
        q = self.qs[r]
        names = self.win.bank.id_names(q.id_code) if q.id_code else []
        self.detail.setText("<b>Câu đang chọn:</b> " + " ".join(q.stem.split())[:300]
                            + ("<br><b>ID hiện tại:</b> " + " › ".join(names) if names else ""))
        sg = self.sugs[r]
        self.sug_list.setRowCount(len(sg))
        for i, x in enumerate(sg):
            src = (f"câu #{x.db_id} trong kho: {x.sample}" if x.db_id is not None else f"Map ID: {x.sample}")
            for c, v in enumerate((x.id_code, f"{x.score:.0%}", src)):
                it = QTableWidgetItem(v)
                it.setToolTip(src)
                self.sug_list.setItem(i, c, it)

    def use_suggestion(self, idx):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if rows:
            x = self.sugs[rows[0]][idx.row()]
            self.set_new(rows[0], x.id_code, x.score)
            self.update_count()

    def accept_best(self):
        thr = self.sp_thr.value() / 100
        n = 0
        for r in self.checked_rows():
            if self.sugs[r] and self.sugs[r][0].score >= thr:
                self.set_new(r, self.sugs[r][0].id_code, self.sugs[r][0].score)
                n += 1
        self.update_count()
        QMessageBox.information(self, "Gợi ý", f"Đã điền ID gợi ý cho {n} câu (độ giống ≥ {thr:.0%}). "
                                "Kiểm tra lại cột «ID mới» trước khi lưu – có thể sửa trực tiếp trong ô.")

    def apply_picker(self):
        rows = self.checked_rows()
        bad = 0
        for r in rows:
            cur = self.t.item(r, 3).text().strip() or self.qs[r].id_code
            new = self.picker.apply_to(cur)
            if new:
                self.set_new(r, new)
            else:
                bad += 1
        self.update_count()
        if bad:
            QMessageBox.warning(self, "Gán ID", f"{bad} câu chưa có ID cũ nên phải chọn đủ Lớp, Môn, Chương, Bài "
                                "và Mức độ (không để «giữ nguyên»).")

    # --- lưu
    def save(self):
        changes, invalid = [], []
        for r, q in enumerate(self.qs):
            new = self.t.item(r, 3).text().strip().upper()
            if not new or new == q.id_code:
                continue
            if not parse_id(new):
                invalid.append(f"{self.labels[r]}: «{new}»")
                continue
            changes.append((q, new))
        if invalid:
            QMessageBox.warning(self, "ID sai dạng", "Các ID sau không đúng dạng 0D2N1-2:\n" + "\n".join(invalid[:15]))
            return
        if not changes:
            QMessageBox.information(self, "Gán ID", "Chưa có câu nào được đặt ID mới (cột «ID mới»).")
            return
        if self.src is None:
            for q, new in changes:
                q.set_id(new)
                self.win.bank.update(q.db_id, q)
            self.win.build_tree()
            self.win.refresh()
            QMessageBox.information(self, "Gán ID", f"Đã gán ID cho {len(changes)} câu trong kho.")
        else:
            base, ext = os.path.splitext(self.src)
            out, _ = QFileDialog.getSaveFileName(self, "Lưu file đã gán ID", base + "_ganID" + ext, "LaTeX (*.tex)")
            if not out:
                return
            with open(self.src, encoding="utf-8") as f:
                text = f.read()
            pairs = []
            for q, new in changes:
                old_raw = q.raw
                q.set_id(new)
                pairs.append((old_raw, q.raw))
            text, n = rv.replace_questions_text(text, pairs)
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Gán ID", f"Đã gán ID cho {n} câu, lưu thành\n{out}\n(file gốc giữ nguyên)")
        self.accept()


# =====================================================================
class ReviewPanel(QWidget):
    """Tab «Rà soát»: kiểm tra đáp án – lời giải – LaTeX của cả kho hoặc một file, rồi sửa/xoá câu sai."""
    COLS = ["", "Mức", "Câu", "Loại", "ID", "Đáp án", "Vấn đề", "Tự sửa được"]

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        self.items = []          # [{src, idx, q, issues}]
        lay = QVBoxLayout(self)

        g = QGroupBox("Phạm vi rà soát")
        hl = QHBoxLayout(g)
        self.cb_src = QComboBox()
        self.cb_src.addItem("Kho câu hỏi đang mở", "bank")
        self.cb_src.addItem("Một file .tex", "file")
        self.e_file = QLineEdit()
        self.e_file.setPlaceholderText("chọn file .tex cần rà soát")
        bf = QPushButton("…")
        bf.setFixedWidth(40)
        bf.clicked.connect(self.pick_file)
        self.cb_show = QComboBox()
        self.cb_show.addItem("Hiện câu có Lỗi hoặc Cảnh báo", "all")
        self.cb_show.addItem("Chỉ hiện câu có Lỗi", "loi")
        b = QPushButton("RÀ SOÁT")
        b.setObjectName("primary")
        b.clicked.connect(self.run)
        for w_, st in ((QLabel("Nguồn:"), 0), (self.cb_src, 0), (self.e_file, 1), (bf, 0), (self.cb_show, 0), (b, 0)):
            hl.addWidget(w_, st)
        self.cb_src.currentIndexChanged.connect(lambda: self.e_file.setEnabled(self.cb_src.currentData() == "file"))
        self.e_file.setEnabled(False)
        lay.addWidget(g)

        self.summary = QLabel("Chọn nguồn rồi bấm <b>RÀ SOÁT</b>. Phần mềm kiểm tra: số phương án và \\True, "
                              "phương án trùng, lời giải «Chọn X» lệch đáp án, lời giải Đúng/Sai ngược đánh dấu, "
                              "đáp án trả lời ngắn (là số, ≤ 4 kí tự, có trong lời giải), lỗi LaTeX "
                              "(ngoặc, $, \\begin/\\end, \\left/\\right), thiếu ID, thiếu lời giải.")
        self.summary.setWordWrap(True)
        lay.addWidget(self.summary)

        split = QSplitter(Qt.Orientation.Vertical)
        self.t = QTableWidget(0, len(self.COLS))
        self.t.setHorizontalHeaderLabels(self.COLS)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for c, w_ in enumerate((30, 80, 150, 100, 90, 70)):
            self.t.setColumnWidth(c, w_)
        self.t.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.t.setColumnWidth(7, 280)
        self.t.itemSelectionChanged.connect(self.on_select)
        self.t.doubleClicked.connect(lambda *_: self.edit())
        split.addWidget(self.t)
        self.code = latex_editor(read_only=True)
        split.addWidget(self.code)
        split.setSizes([420, 260])
        lay.addWidget(split, 1)

        g = QGroupBox("Sửa tự động")
        fx = QHBoxLayout(g)
        fx.addWidget(QLabel("Khi đáp án lệch lời giải:"))
        self.cb_policy = QComboBox()
        self.cb_policy.addItem("Tin lời giải → sửa đánh dấu \\True", rv.THEO_LOI_GIAI)
        self.cb_policy.addItem("Tin đáp án → sửa chữ trong lời giải", rv.THEO_DAP_AN)
        self.cb_policy.currentIndexChanged.connect(self.fill)
        fx.addWidget(self.cb_policy)
        self.c_concl = QCheckBox("Thêm câu kết luận còn thiếu («Chọn đáp án X», «Vậy đáp án là …»)")
        self.c_concl.setChecked(True)
        self.c_concl.toggled.connect(self.fill)
        fx.addWidget(self.c_concl)
        fx.addStretch()
        b = QPushButton("Sửa các câu đã đánh dấu")
        b.clicked.connect(self.fix_checked)
        fx.addWidget(b)
        b = QPushButton("⚡ SỬA TỰ ĐỘNG + BỎ CÂU SAI")
        b.setObjectName("primary")
        b.setToolTip("Sửa mọi câu sửa được, sau đó xoá những câu vẫn còn Lỗi")
        b.clicked.connect(self.fix_all_and_remove)
        fx.addWidget(b)
        lay.addWidget(g)

        row = QHBoxLayout()
        for text, fn in (("Đánh dấu mọi câu Lỗi", self.check_errors), ("Đánh dấu câu sửa được", self.check_fixable),
                         ("Bỏ đánh dấu", self.uncheck_all),
                         ("Sửa tay (kho)", self.edit), ("Xuất báo cáo CSV…", self.export_csv)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        self.b_del = QPushButton("Xoá các câu đã đánh dấu")
        self.b_del.setObjectName("primary")
        self.b_del.clicked.connect(self.delete_checked)
        row.addWidget(self.b_del)
        lay.addLayout(row)

    def pick_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file .tex", self.win.settings.value("last_dir", ""),
                                           "LaTeX (*.tex)")
        if p:
            self.e_file.setText(p)
            self.cb_src.setCurrentIndex(1)

    def run(self):
        mode = self.cb_src.currentData()
        if mode == "file":
            p = self.e_file.text().strip()
            if not p or not os.path.exists(p):
                self.pick_file()
                p = self.e_file.text().strip()
                if not p:
                    return
            qs = parse_file(p)
            src = [(f"{os.path.basename(p)} – câu {i}", q) for i, q in enumerate(qs, 1)]
        else:
            qs = self.win.bank.search()
            src = [(f"Kho #{q.db_id}", q) for q in qs]
        only_err = self.cb_show.currentData() == "loi"
        self.items = []
        n_err = n_warn = 0
        for label, q in src:
            iss = rv.review_question(q)
            lv = rv.worst(iss)
            n_err += lv == rv.LOI
            n_warn += lv == rv.CANH_BAO
            if lv and (lv == rv.LOI or not only_err):
                self.items.append({"label": label, "q": q, "issues": iss, "level": lv})
        self.items.sort(key=lambda it: it["level"] != rv.LOI)
        self.fill()
        self.summary.setText(f"Đã rà soát <b>{len(src)}</b> câu: <span style='color:#c00000'><b>{n_err}</b> câu có lỗi</span>, "
                             f"<span style='color:#b36b00'><b>{n_warn}</b> câu có cảnh báo</span>, "
                             f"<span style='color:#0b7a0b'><b>{len(src) - n_err - n_warn}</b> câu đạt</span>."
                             + ("" if mode == "bank" else " Xoá câu sẽ lưu thành <b>file mới</b>, file gốc giữ nguyên."))

    def fill(self):
        self.t.setRowCount(len(self.items))
        for r, it in enumerate(self.items):
            q = it["q"]
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            chk.setCheckState(Qt.CheckState.Unchecked)
            self.t.setItem(r, 0, chk)
            color = QColor("#c00000") if it["level"] == rv.LOI else QColor("#b36b00")
            fixed, done = self.plan_fix(q)
            it["fix"] = (fixed, done)
            vals = [it["level"], it["label"], TEN_LOAI[q.qtype], q.id_code, q.answer_text,
                    " • ".join(i.msg for i in it["issues"]), ("🔧 " + "; ".join(done)) if done else "—"]
            for c, v in enumerate(vals, 1):
                cell = QTableWidgetItem(str(v))
                if c in (1, 6):
                    cell.setForeground(color)
                if c == 7 and done:
                    cell.setForeground(QColor("#0b7a0b"))
                cell.setToolTip("\n".join(f"[{i.level}] {i.msg}" for i in it["issues"]))
                self.t.setItem(r, c, cell)
        self.code.clear()

    def on_select(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if rows and rows[0] < len(self.items):
            it = self.items[rows[0]]
            head = "\n".join(f"% [{i.level}] {i.msg}" for i in it["issues"])
            self.code.setPlainText(head + "\n" + (it["q"].raw or it["q"].to_latex()))

    # ---------------------------------------------------------- tự sửa
    def plan_fix(self, q):
        """Câu sau khi tự sửa + danh sách việc sẽ làm (chưa ghi gì)."""
        fixed, done = rv.fix_question(q, self.cb_policy.currentData())
        if self.c_concl.isChecked():
            fixed2, added = rv.add_conclusion(fixed)
            if added:
                fixed = fixed2
                done = done + ["Thêm câu kết luận"]
        return fixed, done

    def check_fixable(self):
        for r, it in enumerate(self.items):
            ok = bool(it.get("fix", (None, []))[1])
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if ok else Qt.CheckState.Unchecked)

    def commit(self, changes, removes, title) -> bool:
        """Ghi các thay đổi: changes = [(item, câu_mới)], removes = [item]. Kho: ghi thẳng; file: lưu file mới."""
        if not changes and not removes:
            QMessageBox.information(self, title, "Không có câu nào cần sửa hoặc xoá.")
            return False
        if self.cb_src.currentData() == "bank":
            msg = f"Sửa {len(changes)} câu và xoá {len(removes)} câu trong kho?"
            if QMessageBox.question(self, title, msg + "\nNên sao lưu kho trước (Tệp → Sao lưu kho).") \
                    != QMessageBox.StandardButton.Yes:
                return False
            for it, nq in changes:
                self.win.bank.update(it["q"].db_id, nq)
            if removes:
                self.win.bank.delete([it["q"].db_id for it in removes])
            self.win.build_tree()
            self.win.refresh()
            QMessageBox.information(self, title, f"Đã sửa {len(changes)} câu, xoá {len(removes)} câu khỏi kho.")
        else:
            src = self.e_file.text().strip()
            base, ext = os.path.splitext(src)
            out, _ = QFileDialog.getSaveFileName(self, "Lưu file đã rà soát", base + "_dasoat" + ext, "LaTeX (*.tex)")
            if not out:
                return False
            with open(src, encoding="utf-8") as f:
                text = f.read()
            text, n_fix = rv.replace_questions_text(text, [(it["q"].raw, nq.to_latex()) for it, nq in changes])
            text, n_del = rv.remove_questions_text(text, [it["q"].raw for it in removes])
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, title, f"Đã sửa {n_fix} câu, bỏ {n_del} câu.\nLưu thành: {out}\n"
                                    "(file gốc giữ nguyên)")
            self.e_file.setText(out)
        self.run()
        return True

    def fix_checked(self):
        items = self.checked()
        if not items:
            QMessageBox.information(self, "Sửa câu", "Chưa đánh dấu câu nào (cột đầu tiên). "
                                    "Bấm «Đánh dấu câu sửa được» để chọn nhanh.")
            return
        changes = [(it, it["fix"][0]) for it in items if it.get("fix", (None, []))[1]]
        self.commit(changes, [], "Sửa tự động")

    def fix_all_and_remove(self):
        """Một bước: sửa mọi câu sửa được, rồi bỏ các câu vẫn còn Lỗi sau khi sửa."""
        if not self.items:
            self.run()
        changes, removes = [], []
        for it in self.items:
            nq, done = it.get("fix", (it["q"], []))
            if done:
                changes.append((it, nq))
            if rv.worst(rv.review_question(nq if done else it["q"])) == rv.LOI:
                removes.append(it)
        changes = [(it, nq) for it, nq in changes if it not in removes]
        self.commit(changes, removes, "Sửa tự động + bỏ câu sai")

    def checked(self):
        return [self.items[r] for r in range(self.t.rowCount())
                if self.t.item(r, 0).checkState() == Qt.CheckState.Checked]

    def check_errors(self):
        for r, it in enumerate(self.items):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Checked if it["level"] == rv.LOI else Qt.CheckState.Unchecked)

    def uncheck_all(self):
        for r in range(self.t.rowCount()):
            self.t.item(r, 0).setCheckState(Qt.CheckState.Unchecked)

    def edit(self):
        rows = sorted({i.row() for i in self.t.selectedIndexes()})
        if not rows:
            return
        q = self.items[rows[0]]["q"]
        if q.db_id is None:
            QMessageBox.information(self, "Sửa câu", "Câu này nằm trong file .tex – hãy sửa trực tiếp trong file, "
                                    "hoặc nạp file vào kho rồi rà soát kho.")
            return
        if EditDialog(self.win, q.db_id).exec():
            self.win.refresh()
            self.run()

    def delete_checked(self):
        items = self.checked()
        if not items:
            QMessageBox.information(self, "Xoá câu", "Chưa đánh dấu câu nào (cột đầu tiên).")
            return
        if self.cb_src.currentData() == "bank":
            if QMessageBox.question(self, "Xoá câu", f"Xoá {len(items)} câu khỏi kho?\n"
                                    "Nên sao lưu kho trước (Tệp → Sao lưu kho).") != QMessageBox.StandardButton.Yes:
                return
            self.win.bank.delete([it["q"].db_id for it in items])
            self.win.build_tree()
            self.win.refresh()
            QMessageBox.information(self, "Xoá câu", f"Đã xoá {len(items)} câu khỏi kho.")
        else:
            src = self.e_file.text().strip()
            base, ext = os.path.splitext(src)
            out, _ = QFileDialog.getSaveFileName(self, "Lưu file đã bỏ câu sai", base + "_dasoat" + ext, "LaTeX (*.tex)")
            if not out:
                return
            with open(src, encoding="utf-8") as f:
                text, n = rv.remove_questions_text(f.read(), [it["q"].raw for it in items])
            with open(out, "w", encoding="utf-8") as f:
                f.write(text)
            QMessageBox.information(self, "Xoá câu", f"Đã bỏ {n} câu, lưu thành\n{out}\n(file gốc giữ nguyên)")
            self.e_file.setText(out)
        self.run()

    def export_csv(self):
        if not self.items:
            return
        p, _ = QFileDialog.getSaveFileName(self, "Xuất báo cáo rà soát", "bao_cao_ra_soat.csv", "CSV (*.csv)")
        if not p:
            return
        import csv
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w_ = csv.writer(f)
            w_.writerow(["Câu", "Loại", "ID", "Đáp án", "Mức", "Vấn đề"])
            for it in self.items:
                for i in it["issues"]:
                    w_.writerow([it["label"], it["q"].qtype, it["q"].id_code, it["q"].answer_text, i.level, i.msg])
        QMessageBox.information(self, "Báo cáo", f"Đã lưu {p}")


# =====================================================================
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
        from .wordconv import PandocMissing, import_docx
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
        from .wordconv import PandocMissing, export_questions_docx
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
        from .generator import ExamVersion, sections_from_questions
        from .online import version_html
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


# =====================================================================
class StatsPanel(QWidget):
    """Tab «Thống kê»: tổng quan kho theo lớp/chương/loại/mức độ."""

    def __init__(self, win: MainWindow):
        super().__init__()
        self.win = win
        lay = QVBoxLayout(self)
        self.cards = QHBoxLayout()
        lay.addLayout(self.cards)
        self.card_labels = {}
        for key, title in (("all", "Tổng số câu"), ("TN", "Trắc nghiệm"), ("DS", "Đúng/Sai"),
                           ("KQ", "Trả lời ngắn"), ("TL", "Tự luận")):
            box = QGroupBox(title)
            bl = QVBoxLayout(box)
            lb = QLabel("0")
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb.setStyleSheet("font-size: 26px; font-weight: 700; color: #1f4e79;")
            bl.addWidget(lb)
            self.card_labels[key] = lb
            self.cards.addWidget(box)
        self.t = QTableWidget(0, 7)
        self.t.setHorizontalHeaderLabels(["Lớp", "Môn", "Chương", "Nhận biết", "Thông hiểu", "Vận dụng",
                                          "Vận dụng cao"])
        self.t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        self.t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.t.setAlternatingRowColors(True)
        lay.addWidget(QLabel("<b>Số câu theo chương và mức độ</b>"))
        lay.addWidget(self.t, 1)

    def reload(self):
        bank = self.win.bank
        if not bank:
            return
        self.card_labels["all"].setText(str(bank.count()))
        for k in TEN_LOAI:
            n = bank.con.execute("SELECT COUNT(*) FROM questions WHERE qtype=?", (k,)).fetchone()[0]
            self.card_labels[k].setText(str(n))
        grid = {}
        for r in bank.stats():
            key = (r["lop"], r["mon"], r["chuong"])
            grid.setdefault(key, {})
            grid[key][r["muc_do"]] = grid[key].get(r["muc_do"], 0) + r["n"]
        self.t.setRowCount(len(grid))
        for i, ((lop, mon, ch), d) in enumerate(sorted(grid.items())):
            vals = [LOP.get(lop, lop or "?"), MON.get(mon, mon or "?"), ch or "?"] + \
                   [d.get(m, 0) for m in "NHVC"]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.t.setItem(i, c, it)


def compile_pdfs(tex_files, cwd) -> list[str]:
    fails = []
    for f in tex_files:
        r = subprocess.run(["xelatex", "-interaction=nonstopmode", os.path.basename(f)], cwd=cwd,
                           capture_output=True)
        if r.returncode != 0:
            fails.append(os.path.basename(f))
    return fails


def run(db_path: str | None = None):
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    app.setFont(QFont("Segoe UI", 10))
    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "app.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    w = MainWindow(db_path)
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
