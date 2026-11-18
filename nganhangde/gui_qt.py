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
                               QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
                               QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
                               QSpinBox, QSplitter, QTableWidget, QTableWidgetItem,
                               QTabWidget, QTextBrowser, QToolBar, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout, QWidget)

from . import __version__
from .db import Bank
from .exporter import export_questions, export_versions
from .generator import NotEnoughQuestions, Rule, make_versions
from .idcode import LOP, MON, MUC_DO, parse_id
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
        self._act(m, "Xuất câu đang hiển thị/đã chọn…", self.export_selected, "Ctrl+E")
        m.addSeparator()
        self._act(m, "Thoát", self.close, QKeySequence.StandardKey.Quit)
        m = mb.addMenu("&Câu hỏi")
        self._act(m, "Thêm câu mới", self.add_question, "Ctrl+N")
        self._act(m, "Sửa câu", self.edit_question, "F2")
        self._act(m, "Xoá câu", self.delete_questions, QKeySequence.StandardKey.Delete)
        m = mb.addMenu("Đề &thi")
        self._act(m, "Tạo đề theo ma trận…", self.open_generator, "Ctrl+G")
        m = mb.addMenu("Công &cụ")
        self._act(m, "Soát lỗi file .tex…", self.check_file)
        self._act(m, "Thống kê ngân hàng", self.show_stats)
        m = mb.addMenu("Trợ &giúp")
        self._act(m, "Giới thiệu", self.about)

        # --- thanh công cụ
        tb = QToolBar("Công cụ")
        tb.setMovable(False)
        self.addToolBar(tb)
        for text, fn in (("📥 Nhập .tex", self.import_files), ("➕ Thêm câu", self.add_question),
                         ("✏️ Sửa", self.edit_question), ("🗑 Xoá", self.delete_questions),
                         ("📤 Xuất câu", self.export_selected), ("🎲 Tạo đề", self.open_generator),
                         ("🔎 Soát lỗi file", self.check_file), ("📊 Thống kê", self.show_stats)):
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
        self.f_text = QLineEdit()
        self.f_text.setPlaceholderText("từ khoá trong đề/lời giải/nguồn")
        fl.addRow("Loại câu", self.f_type)
        fl.addRow("Mức độ", self.f_muc)
        fl.addRow("Mẫu ID", self.f_id)
        fl.addRow("Từ khoá", self.f_text)
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

        center = QSplitter(Qt.Orientation.Vertical)
        center.addWidget(self.table)
        center.addWidget(self.tabs)
        center.setSizes([480, 320])

        split = QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(center)
        split.setSizes([280, 1020])
        self.setCentralWidget(split)
        self.statusBar().showMessage("Sẵn sàng")

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
        for r in self.bank.stats():
            lop, mon, ch, n = r["lop"], r["mon"], r["chuong"], r["n"]
            path = [("lop", lop, f"Lớp {LOP.get(lop, lop)}" if lop else "Chưa có ID"),
                    ("mon", mon, MON.get(mon, mon or "?")),
                    ("chuong", ch, f"Chương {ch}")]
            parent, filt = root, {}
            for key, val, label in path:
                if not lop and key != "lop":
                    break
                filt = {**filt, key: val}
                k = tuple(sorted(filt.items()))
                if k not in nodes:
                    it = QTreeWidgetItem([label, "0"])
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
                              id_like=self.f_id.text().strip() or None, text=self.f_text.text().strip() or None,
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
        p, _ = QFileDialog.getOpenFileName(self, "Soát lỗi file .tex", self.settings.value("last_dir", ""),
                                           "LaTeX (*.tex)")
        if not p:
            return
        rows = []
        for i, q in enumerate(parse_file(p), 1):
            ws = validate(q)
            dup = self.bank.find_duplicate(q)
            if dup:
                ws.append(f"Trùng câu #{dup} trong kho")
            color = "#c00000" if ws else "#0b7a0b"
            rows.append(f"<tr><td>{i}</td><td>{q.qtype}</td><td>{q.id_code}</td><td>{q.answer_text}</td>"
                        f"<td style='color:{color}'>{'<br>'.join(ws) or '✔'}</td></tr>")
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Soát lỗi – {os.path.basename(p)}")
        dlg.resize(800, 600)
        tb = QTextBrowser()
        tb.setHtml("<table border=1 cellspacing=0 cellpadding=4><tr><th>Câu</th><th>Loại</th><th>ID</th>"
                   "<th>Đáp án</th><th>Kết quả</th></tr>" + "".join(rows) + "</table>")
        QVBoxLayout(dlg).addWidget(tb)
        dlg.exec()

    def show_stats(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Thống kê ngân hàng")
        dlg.resize(700, 500)
        stats = self.bank.stats()
        t = QTableWidget(len(stats), 6)
        t.setHorizontalHeaderLabels(["Lớp", "Môn", "Chương", "Loại", "Mức độ", "Số câu"])
        for r, s in enumerate(stats):
            vals = [LOP.get(s["lop"], s["lop"]), MON.get(s["mon"], s["mon"]), s["chuong"],
                    TEN_LOAI.get(s["qtype"], s["qtype"]), TEN_MUC.get(s["muc_do"], s["muc_do"]), s["n"]]
            for c, v in enumerate(vals):
                it = QTableWidgetItem()
                it.setData(Qt.ItemDataRole.DisplayRole, v)
                t.setItem(r, c, it)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setSortingEnabled(True)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"<b>Tổng số câu: {self.bank.count()}</b>"))
        lay.addWidget(t)
        dlg.exec()

    def open_generator(self):
        GeneratorDialog(self).exec()
        self.refresh()

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
class GeneratorDialog(QDialog):
    """Lập ma trận đề → sinh nhiều mã đề → xuất .tex/.csv (→ PDF nếu có xelatex)."""
    COLS = ["Loại câu", "Mẫu ID", "Mức độ", "Số câu", "Kho có"]

    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win = win
        self.st = win.settings
        self.setWindowTitle("Tạo đề theo ma trận")
        self.resize(900, 680)
        lay = QVBoxLayout(self)

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
        self.e_ma.setPlaceholderText("để trống = 101, 102, …   hoặc nhập: 132, 209, 357, 485")
        self.e_seed = QLineEdit()
        self.e_seed.setPlaceholderText("để trống = ngẫu nhiên; nhập số để tạo lại đúng bộ đề cũ")
        self.e_out = self._path_row(self.st.value("gen/out", os.path.join(resource_dir(), "de_xuat")), folder=True)
        self.e_tpl = self._path_row(self.st.value("gen/tpl", ""), folder=False)
        self.e_tpl[0].setPlaceholderText("để trống = dùng mẫu có sẵn")
        fl.addRow("Tên đề", self.e_ten)
        fl.addRow("Trường", self.e_truong)
        fl.addRow("Thời gian (phút)", self.e_tg)
        fl.addRow("Số mã đề", self.e_n)
        fl.addRow("Danh sách mã đề", self.e_ma)
        fl.addRow("Hạt giống (seed)", self.e_seed)
        fl.addRow("Thư mục xuất", self.e_out[1])
        fl.addRow("File mẫu .tex", self.e_tpl[1])
        self.c_diff = QCheckBox("Mỗi mã đề một bộ câu khác nhau")
        self.c_unused = QCheckBox("Ưu tiên câu ít được dùng")
        self.c_unused.setChecked(True)
        self.c_pdf = QCheckBox("Biên dịch PDF bằng xelatex (nếu máy có cài)")
        self.c_pdf.setEnabled(bool(shutil.which("xelatex")))
        for c in (self.c_diff, self.c_unused, self.c_pdf):
            fl.addRow("", c)
        lay.addWidget(g)

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
        close = QPushButton("Đóng")
        close.clicked.connect(self.reject)
        row.addWidget(b)
        row.addWidget(close)
        lay.addLayout(row)

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

    def del_row(self):
        for r in sorted({i.row() for i in self.t.selectedIndexes()}, reverse=True):
            self.t.removeRow(r)
        self.update_avail()

    def rules_dicts(self):
        out = []
        for i in range(self.t.rowCount()):
            out.append({"qtype": self.t.cellWidget(i, 0).currentData(),
                        "id": (self.t.item(i, 1).text().strip() if self.t.item(i, 1) else "") or "*",
                        "muc_do": self.t.cellWidget(i, 2).currentData() or None,
                        "count": self.t.cellWidget(i, 3).value()})
        return out

    def update_avail(self):
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
        codes = self.codes() or None
        seed = int(self.e_seed.text()) if self.e_seed.text().strip().isdigit() else None
        try:
            vs = make_versions(self.win.bank, rules, len(codes) if codes else self.e_n.value(), codes=codes,
                               seed=seed, same_questions=not self.c_diff.isChecked(),
                               prefer_unused=self.c_unused.isChecked())
        except NotEnoughQuestions as e:
            QMessageBox.warning(self, "Không đủ câu", str(e))
            return
        out = self.e_out[0].text()
        try:
            files = export_versions(vs, out, template_path=self.e_tpl[0].text() or None,
                                    ten_de=self.e_ten.text(), truong=self.e_truong.text(),
                                    thoi_gian=self.e_tg.value())
        except OSError as e:
            QMessageBox.critical(self, "Lỗi ghi file", str(e))
            return
        self.win.bank.mark_used({q.db_id for v in vs for q in v.all_questions()})
        for k, v in (("ten", self.e_ten.text()), ("truong", self.e_truong.text()), ("tg", self.e_tg.value()),
                     ("n", self.e_n.value()), ("ma", self.e_ma.text()), ("out", out),
                     ("tpl", self.e_tpl[0].text()), ("matrix", json.dumps(rd, ensure_ascii=False))):
            self.st.setValue(f"gen/{k}", v)
        msg = f"Đã tạo {len(vs)} mã đề: {', '.join(v.code for v in vs)}\nThư mục: {out}"
        if self.c_pdf.isChecked():
            fails = compile_pdfs([f for f in files if f.endswith(".tex")], out)
            msg += "\n\nBiên dịch PDF: " + ("thành công" if not fails else "lỗi ở " + ", ".join(fails))
        if QMessageBox.question(self, "Xong", msg + "\n\nMở thư mục kết quả?") == QMessageBox.StandardButton.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out)))


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
