"""Bố cục các tab chính và chế độ xem câu hỏi từ file (tách khỏi main_window.py cho gọn).

Tab chính: Trộn đề · Câu hỏi · Ma trận · Tiện ích · Vẽ hình · Đồ thị · BBT & Xét dấu · Biểu diễn nghiệm · Soạn thảo · Thông tin.
"""
from __future__ import annotations

import os
import tempfile

from PySide6.QtWidgets import QFileDialog, QGroupBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTabWidget, QVBoxLayout


class LayoutMixin:
    # ---------------------------------------------------------------- tab
    def _build_tabs(self, bank_widget):
        from .tabs.draw import DrawPanel
        from .tabs.generator import GeneratorPanel
        from .tabs.id_grid import IdGridPanel
        from .tabs.geometry import GeomPanel
        from .tabs.make_question import MakeQuestionPanel
        from .tabs.mix_more import FileMixPanel, PickPanel, SimilarExamPanel
        from .tabs.panels_more import ConvertPanel, EditorPanel, InfoPanel, MatrixPanel
        from .tabs.review import ReviewPanel
        from .tabs.stats import StatsPanel
        from .tabs.tools import ToolsPanel
        from .tabs.utils2 import Utils2Panel

        def sub(*pages):
            t = QTabWidget()
            t.setObjectName("subTabs")
            for w, name in pages:
                t.addTab(w, name)
            t.currentChanged.connect(lambda _i: self.on_tab_changed(None))
            return t

        self.gen_panel = GeneratorPanel(self)
        self.idgrid_panel = IdGridPanel(self)
        self.pick_panel = PickPanel(self)
        self.filemix_panel = FileMixPanel(self)
        self.similar_panel = SimilarExamPanel(self)
        self.review_panel = ReviewPanel(self)
        self.gen_q_panel = MakeQuestionPanel(self)
        self.tools_panel = ToolsPanel(self)
        self.stats_panel = StatsPanel(self)
        self.convert_panel = ConvertPanel(self)
        self.utils2_panel = Utils2Panel(self)
        self.matrix_panel = MatrixPanel(self)
        self.geom_panel = GeomPanel(self)
        self.graph_panel = DrawPanel(self, ("graph", "chart"))
        self.bbt_panel = DrawPanel(self, ("bbt", "sign"))
        self.sol_panel = DrawPanel(self, ("numline", "region", "trig"))
        self.solid_panel = DrawPanel(self, ("solid",))
        self.editor_panel = EditorPanel(self)
        self.info_panel = InfoPanel(self)
        from .tabs.update_panel import UpdatePanel
        self.update_panel = UpdatePanel(self)
        self.draw_panel = self.graph_panel          # tên cũ
        mt = self.main_tabs
        mt.addTab(sub((self.idgrid_panel, "Chọn theo ID"), (self.gen_panel, "Theo ma trận ID"), (self.pick_panel, "Tự chọn câu"),
                      (self.filemix_panel, "Theo file"), (self.similar_panel, "Đề tương tự")), "📝 Trộn đề")
        mt.addTab(bank_widget, "📚 Câu hỏi")
        mt.addTab(self.matrix_panel, "🧮 Ma trận")
        mt.addTab(sub((self.tools_panel, "Tiện ích 1"), (self.utils2_panel, "Tiện ích 2"),
                      (self.convert_panel, "Xuất && chuyển đổi"),
                      (self.review_panel, "Rà soát"), (self.gen_q_panel, "Sinh câu"),
                      (self.stats_panel, "Thống kê")), "🛠 Tiện ích")
        mt.addTab(sub((self.geom_panel, "Dựng hình phẳng"), (self.solid_panel, "Hình khối")), "📐 Vẽ hình")
        mt.addTab(self.graph_panel, "📈 Đồ thị")
        mt.addTab(self.bbt_panel, "📊 BBT && Xét dấu")
        mt.addTab(self.sol_panel, "🎯 Biểu diễn nghiệm")
        mt.addTab(self.editor_panel, "✍ Soạn thảo")
        mt.addTab(self.info_panel, "ℹ Thông tin")
        mt.addTab(self.update_panel, "⬆ Cập nhật")
        mt.setCurrentIndex(1)
        mt.tabBar().setExpanding(False)
        for p in (self.graph_panel, self.bbt_panel, self.sol_panel, self.solid_panel):
            p.sub.setObjectName("subTabs")

    def show_panel(self, w):
        """Chuyển tới widget w dù nó nằm trong tab con."""
        chain = []
        x = w
        while x is not None:
            chain.append(x)
            x = x.parentWidget()
        for i, t in enumerate(chain):
            if isinstance(t, QTabWidget):
                for y in chain[:i]:
                    if t.indexOf(y) >= 0:
                        t.setCurrentWidget(y)
                        break

    def current_panel(self):
        w = self.main_tabs.currentWidget()
        while isinstance(w, QTabWidget):
            w = w.currentWidget()
        return w

    # ---------------------------------------------------------------- xem câu hỏi từ file
    def _source_box(self):
        g = QGroupBox("Nguồn câu hỏi")
        v = QVBoxLayout(g)
        self.l_source = QLabel("Ngân hàng câu hỏi")
        self.l_source.setWordWrap(True)
        v.addWidget(self.l_source)
        row = QHBoxLayout()
        for text, fn in (("Từ file…", self.view_files), ("Về ngân hàng", self.back_to_bank),
                         ("Nạp vào kho", self.files_to_bank)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        v.addLayout(row)
        self.file_mode = False
        return g

    def view_files(self):
        from ..db import Bank
        from ..parser import parse_file
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file câu hỏi", "", "LaTeX (*.tex)")
        if not ps:
            return
        if not self.file_mode:
            self._main_bank_path = self.bank.path
        names = self.bank.idmap()
        d = tempfile.mkdtemp(prefix="nhd_xemfile_")
        tmp = os.path.join(d, "xem_file.db")
        b = Bank(tmp)
        if names:
            b.set_idmap(names)
        n = 0
        for p in ps:
            for q in parse_file(p):
                n += b.add(q, p) is not None
        b.close()
        self.open_bank(tmp, remember=False)
        self.file_mode = True
        self._viewed_files = ps
        self.l_source.setText(f"<b>Đang xem {len(ps)} file</b> ({n} câu): " + ", ".join(os.path.basename(p) for p in ps) +
                              "<br><i>Sửa ở đây không ghi vào file gốc – dùng «Xuất câu» hoặc «Nạp vào kho».</i>")
        self.show_panel(self.table)

    def back_to_bank(self):
        if self.file_mode:
            self.open_bank(self._main_bank_path)
            self.file_mode = False
            self.l_source.setText("Ngân hàng câu hỏi")

    def files_to_bank(self):
        from ..db import Bank
        if not self.file_mode:
            QMessageBox.information(self, "Nạp vào kho", "Hãy chọn «Từ file…» trước.")
            return
        tmp = self.bank.path
        main = Bank(self._main_bank_path)
        try:
            added, skipped = main.merge_from(tmp)
        finally:
            main.close()
        QMessageBox.information(self, "Nạp vào kho", f"Đã thêm {added} câu vào ngân hàng chính (bỏ {skipped} câu trùng).")
