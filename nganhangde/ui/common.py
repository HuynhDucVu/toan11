"""Phần dùng chung của giao diện: hằng số, kiểu trình bày (STYLE), tô màu LaTeX, tiện ích."""
from __future__ import annotations

import os
import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import QFrame, QPlainTextEdit, QScrollArea, QWidget

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
    """Thư mục gốc của phần mềm (cạnh file .exe khi đã đóng gói) – xem appdirs.py."""
    from ..appdirs import home
    return home()


def make_settings():
    """Cài đặt lưu trong config.ini cạnh phần mềm (như MyLT). Lần đầu: chép cài đặt cũ từ Registry sang."""
    from PySide6.QtCore import QSettings
    from ..appdirs import settings_file
    p = settings_file()
    fresh = not os.path.exists(p)
    st = QSettings(p, QSettings.Format.IniFormat)
    if fresh and not os.environ.get("NHD_HOME"):
        old = QSettings("NganHangDe", "NganHangDe")
        for k in old.allKeys():
            st.setValue(k, old.value(k))
        st.sync()
    return st


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
