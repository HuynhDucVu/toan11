"""3 Tab chuẩn MyLT 2026 v1.0.3.44: BBT&XD, Biểu diễn nghiệm, Soạn thảo (5 tab con)."""
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from .pdf_preview import InlinePdfPreviewPanel
from .doi_so_tab import DoiSoTab


class _TikzCodePreviewBase(QWidget):
    """Bố cục chung cho BBT&XD và Biểu diễn nghiệm: Code bên trái | PDF Xem trước trực tiếp bên phải."""
    def __init__(self, buttons: list[tuple[str, str]], parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)

        top = QHBoxLayout()
        for label, snippet in buttons:
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, s=snippet: self._select_preset(s))
            top.addWidget(b)
        top.addStretch()
        root.addLayout(top)

        sp = QSplitter(Qt.Horizontal)
        self.ed_code = QPlainTextEdit()
        self.ed_code.setPlaceholderText("Mã TikZ / tkz-tab sẽ hiển thị tại đây...")
        self.preview_panel = InlinePdfPreviewPanel(auto_checked=True)
        sp.addWidget(self.ed_code)
        sp.addWidget(self.preview_panel)
        sp.setSizes([560, 560])
        root.addWidget(sp, 1)

        bot = QHBoxLayout()
        bot.addStretch()
        b_new = QPushButton("Hình mới"); b_new.clicked.connect(self._clear_all)
        b_pdf = QPushButton("Xem PDF"); b_pdf.clicked.connect(self._view_pdf)
        b_copy = QPushButton("Copy code"); b_copy.clicked.connect(lambda: QApplication.clipboard().setText(self.ed_code.toPlainText()))
        b_edit = QPushButton("Sửa code"); b_edit.clicked.connect(self.ed_code.setFocus)
        b_copy_img = QPushButton("Copy hình"); b_copy_img.clicked.connect(self._copy_img)
        for b in (b_new, b_pdf, b_copy, b_edit, b_copy_img):
            bot.addWidget(b)
        bot.addStretch()
        root.addLayout(bot)

    def _select_preset(self, snippet: str):
        self.ed_code.setPlainText(snippet)
        if self.preview_panel.is_auto_preview():
            self.preview_panel.compile_and_show_tikz(snippet)

    def _clear_all(self):
        self.ed_code.clear()
        self.preview_panel.clear()

    def _view_pdf(self):
        code = self.ed_code.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "Trống", "Chưa có mã để biên dịch PDF.")
            return
        self.preview_panel.compile_and_show_tikz(code)

    def _copy_img(self):
        if self.preview_panel.copy_image_to_clipboard():
            QMessageBox.information(self, "Copy hình", "Đã sao chép hình ảnh vào clipboard.")
        else:
            QMessageBox.warning(self, "Chưa có hình", "Hãy bấm 'Xem PDF' để biên dịch hình trước.")


class BBTXDMyLT2026Tab(_TikzCodePreviewBase):
    def __init__(self, parent=None):
        presets = [
            (
                "BBT các hàm cơ bản",
                r"""\begin{tikzpicture}
\tkzTabInit[nocadre=false,lgt=1.2,espcl=2.2]
{$x$/0.7,$y'$/0.7,$y$/2}
{$-\infty$,$-1$,$1$,$+\infty$}
\tkzTabLine{,+,0,-,0,+,}
\tkzTabVar{-/$-\infty$,+/$3$,-/$-1$,+/$+\infty$}
\end{tikzpicture}""",
            ),
            (
                "BBT bất kỳ",
                r"""\begin{tikzpicture}
\tkzTabInit[nocadre=false,lgt=1.2,espcl=2.2]
{$x$/0.7,$y'$/0.7,$y$/2}
{$-\infty$,$1$,$+\infty$}
\tkzTabLine{,-,d,-,}
\tkzTabVar{+/$2$,-D+/$-\infty$/$+\infty$,-/$2$}
\end{tikzpicture}""",
            ),
            (
                "Bảng xét dấu",
                r"""\begin{tikzpicture}
\tkzTabInit[nocadre=false,lgt=1.5,espcl=2.2]
{$x$/0.7,$f(x)$/0.8}
{$-\infty$,$-2$,$3$,$+\infty$}
\tkzTabLine{,+,0,-,0,+,}
\end{tikzpicture}""",
            ),
        ]
        super().__init__(presets, parent)


class BieuDienNghiemMyLT2026Tab(_TikzCodePreviewBase):
    def __init__(self, parent=None):
        presets = [
            (
                "Trục số",
                r"""\begin{tikzpicture}[>=stealth]
\draw[->] (-3.5,0)--(3.5,0) node[below]{$x$};
\draw[thick] (-1,0) node[below]{$-1$} (2,0) node[below]{$2$};
\draw[very thick,blue] (-1,0)--(2,0);
\end{tikzpicture}""",
            ),
            (
                "Vẽ cung LG",
                r"""\begin{tikzpicture}[>=stealth,scale=1.5]
\draw[->] (-1.4,0)--(1.4,0) node[below]{$\cos$};
\draw[->] (0,-1.4)--(0,1.4) node[left]{$\sin$};
\draw (0,0) circle (1);
\fill[red] (60:1) circle (1.5pt) node[above right]{$\dfrac{\pi}{3}$};
\end{tikzpicture}""",
            ),
            (
                "Biểu diễn cung LG",
                r"""\begin{tikzpicture}[>=stealth,scale=1.5]
\draw[->] (-1.4,0)--(1.4,0); \draw[->] (0,-1.4)--(0,1.4);
\draw (0,0) circle (1);
\draw[very thick,red,->] (30:1) arc (30:150:1);
\end{tikzpicture}""",
            ),
            (
                "Miền nghiệm hệ BPT",
                r"""\begin{tikzpicture}[>=stealth,scale=0.8]
\fill[teal!25] (0,0)--(3,0)--(0,2)--cycle;
\draw[->] (-1,0)--(4,0) node[below]{$x$};
\draw[->] (0,-1)--(0,3.5) node[left]{$y$};
\draw[thick] (-0.5,2.33)--(3.5,-0.33);
\end{tikzpicture}""",
            ),
            (
                "Biểu đồ",
                r"""\begin{tikzpicture}
\draw[->] (0,0)--(6,0); \draw[->] (0,0)--(0,4);
\foreach \x/\h/\lb in {1/2.5/A, 2.5/3.2/B, 4/1.8/C} {
  \fill[teal!60] (\x,0) rectangle (\x+0.8,\h);
  \node[below] at (\x+0.4,0) {\lb};
}
\end{tikzpicture}""",
            ),
            (
                "Thống kê",
                r"""\begin{tikzpicture}
\draw[thick] (0,0)--(6,0);
\draw[fill=orange!30] (1.5,-0.4) rectangle (4.5,0.4);
\draw[very thick] (3,-0.4)--(3,0.4);
\node[below] at (1.5,-0.4) {$Q_1$}; \node[below] at (3,-0.4) {$Q_2$}; \node[below] at (4.5,-0.4) {$Q_3$};
\end{tikzpicture}""",
            ),
        ]
        super().__init__(presets, parent)


class SoanThaoMyLT2026Tab(QWidget):
    """Tab Soạn thảo 5 tab con đúng như MyLT 2026: Câu cùng đề | Câu đổi số | Câu đổi số tự tạo | Câu đổi số AI | Code Tikz."""
    def __init__(self, legacy_editor_widget: QWidget | None = None, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        tabs = QTabWidget()

        # 1. Câu cùng đề
        w_cd = QWidget(); vcd = QVBoxLayout(w_cd)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["STT", "Nội dung", "ID", "Loại", "Lấy"])
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        vcd.addWidget(self.tbl, 1)

        r_act = QHBoxLayout()
        for lb in ("Thêm", "Sửa", "Xoá", "Chọn hết", "Xoá chọn"):
            r_act.addWidget(QPushButton(lb))
        r_act.addWidget(QCheckBox("Xem PDF"))
        r_act.addStretch()
        vcd.addLayout(r_act)

        r_exp = QHBoxLayout()
        self.ed_out_name = QLineEdit("cau_cung_de.tex")
        self.chk_comp = QCheckBox("Biên dịch")
        self.rb_file = QRadioButton("Xuất ra file"); self.rb_file.setChecked(True)
        self.rb_copy = QRadioButton("Sao chép")
        b_exp = QPushButton("Xuất")
        b_exp.clicked.connect(lambda: QMessageBox.information(self, "Xuất", f"Sẵn sàng xuất tệp: {self.ed_out_name.text()}"))
        for w in (QLabel("Tên file"), self.ed_out_name, self.chk_comp, self.rb_file, self.rb_copy, b_exp):
            r_exp.addWidget(w)
        vcd.addLayout(r_exp)

        tabs.addTab(w_cd, "Câu cùng đề")
        tabs.addTab(DoiSoTab(), "Câu đổi số & Tự tạo")
        if legacy_editor_widget is not None:
            tabs.addTab(legacy_editor_widget, "Soạn thảo & Code Tikz")
        root.addWidget(tabs)
