"""Tab Câu hỏi đổi số tự động & Tự tạo (chuẩn MyLT 2026)."""
from __future__ import annotations
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt
from ..core.doi_so_engine import (
    generate_asymptote_rational,
    generate_cubic_monotonicity,
    generate_custom_parametric,
)


DEFAULT_CUSTOM_TEMPLATE = r"""\begin{ex}%[2D1N1-1]
Cho hai số nguyên $a = [a]$ và $b = [b]$. Giá trị của $S = 2a + b$ bằng
\choice
{\True ${{2*a + b}}$}
{${{2*a - b}}$}
{${{a + 2*b}}$}
{${{a + b}}$}
\loigiai{
Ta có $S = 2([a]) + ([b]) = {{2*a + b}}$.
}
\end{ex}"""


class DoiSoTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        sp = QSplitter(Qt.Horizontal)

        left = QWidget()
        ll = QVBoxLayout(left)

        g1 = QGroupBox("1. Sinh câu hỏi đổi số có sẵn (Đủ ID + Đáp án + Lời giải)")
        f1 = QFormLayout(g1)
        self.cbo_type = QComboBox()
        self.cbo_type.addItem("Đơn điệu hàm số bậc ba", "cubic_mono")
        self.cbo_type.addItem("Tiệm cận hàm bậc nhất trên bậc nhất", "asymptote")
        self.spn_count = QSpinBox()
        self.spn_count.setRange(1, 50)
        self.spn_count.setValue(5)
        b_gen = QPushButton("Sinh câu hỏi đổi số")
        b_gen.clicked.connect(self._on_gen_builtin)
        f1.addRow("Dạng toán:", self.cbo_type)
        f1.addRow("Số câu:", self.spn_count)
        f1.addRow("", b_gen)
        ll.addWidget(g1)

        g2 = QGroupBox("2. Câu hỏi đổi số tự tạo (Dùng [a], [b] và {{biểu thức}})")
        v2 = QVBoxLayout(g2)
        self.ed_ranges = QLineEdit("a:-5..5, b:-5..5, c:1..6")
        self.ed_tpl = QPlainTextEdit(DEFAULT_CUSTOM_TEMPLATE)
        b_custom = QPushButton("Sinh hàng loạt từ mẫu tự tạo")
        b_custom.clicked.connect(self._on_gen_custom)
        v2.addWidget(self.ed_ranges)
        v2.addWidget(self.ed_tpl, 1)
        v2.addWidget(b_custom)
        ll.addWidget(g2, 1)

        self.out_view = QPlainTextEdit()
        self.out_view.setPlaceholderText("Các câu hỏi đổi số sinh ra sẽ hiển thị tại đây...")

        sp.addWidget(left)
        sp.addWidget(self.out_view)
        sp.setSizes([460, 740])
        root.addWidget(sp)

    def _on_gen_builtin(self):
        kind = self.cbo_type.currentData()
        n = self.spn_count.value()
        if kind == "cubic_mono":
            self.out_view.setPlainText(generate_cubic_monotonicity(n))
        else:
            self.out_view.setPlainText(generate_asymptote_rational(n))

    def _on_gen_custom(self):
        ranges: dict[str, tuple[int, int]] = {}
        for part in self.ed_ranges.text().split(","):
            if ":" in part and ".." in part:
                k, rng = part.split(":", 1)
                lo, hi = rng.split("..", 1)
                ranges[k.strip()] = (int(lo.strip()), int(hi.strip()))
        res = generate_custom_parametric(self.ed_tpl.toPlainText(), ranges, self.spn_count.value())
        self.out_view.setPlainText(res)
