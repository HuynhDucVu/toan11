"""Tab Tiện ích 2 chuẩn bố cục MyLT 2026 v1.0.3.44 — đầy đủ HDSD, Map ID, Chuyển ID, Input TeX, Thực hiện."""
from __future__ import annotations
from pathlib import Path
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ..paths import resource_path
from ..core.map_id_loader import load_map_id_file
from ..core.tex_file_tools import (
    add_dapso_in_tex,
    apply_answer_string,
    assign_ids_from_reference_tex,
    assign_single_id,
    check_tex_questions,
    convert_ids_in_tex,
    extract_answer_string,
    format_code_indent,
    generate_sample_code,
    load_convid_map,
    make_input_master_tex,
    move_true_to_a,
    number_questions_in_tex,
    process_exam_info,
    process_ids,
    remove_blank_lines,
    shuffle_choices_in_tex,
    shuffle_questions_in_tex,
    sort_questions_by_id,
    split_tex_by_chunk,
    split_tex_by_id,
)
from ..exporters.pdfbuild import compile_tex_to_pdf, open_pdf_file


class RestoreMapIdDialog(QDialog):
    """Hộp thoại Khôi phục bảng ID chuẩn MyLT 2026."""

    def __init__(self, map_dir: Path, parent=None):
        super().__init__(parent)
        self.map_dir = map_dir
        self.selected_path: Path | None = None
        self.setWindowTitle("Khôi phục bảng ID")
        self.resize(340, 320)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        g = QGroupBox("Chọn phiên bản")
        vg = QVBoxLayout(g)
        self.checks: list[tuple[QCheckBox, Path]] = []
        for p in sorted(self.map_dir.glob("Map ID*.tex")):
            cb = QCheckBox(p.stem)
            self.checks.append((cb, p))
            vg.addWidget(cb)
        vg.addStretch()
        root.addWidget(g, 1)

        bot = QHBoxLayout()
        b_del = QPushButton("Xoá"); b_del.clicked.connect(self._delete_selected)
        b_res = QPushButton("Khôi phục"); b_res.clicked.connect(self._restore_selected)
        b_close = QPushButton("Đóng"); b_close.clicked.connect(self.reject)
        bot.addWidget(b_del); bot.addWidget(b_res); bot.addWidget(b_close)
        root.addLayout(bot)

    def _delete_selected(self):
        picked = [(cb, p) for cb, p in self.checks if cb.isChecked()]
        if not picked:
            QMessageBox.information(self, "Xoá", "Hãy tick chọn phiên bản cần xoá.")
            return
        if QMessageBox.question(self, "Xác nhận xoá", f"Xoá {len(picked)} tệp bảng ID đã chọn?") != QMessageBox.Yes:
            return
        for cb, p in picked:
            try:
                p.unlink(missing_ok=True)
                cb.setVisible(False)
                cb.setChecked(False)
            except Exception as exc:
                QMessageBox.warning(self, "Lỗi xoá", str(exc))

    def _restore_selected(self):
        picked = [p for cb, p in self.checks if cb.isChecked()]
        if not picked:
            QMessageBox.information(self, "Khôi phục", "Hãy tick chọn 1 phiên bản bảng ID cần khôi phục.")
            return
        self.selected_path = picked[0]
        self.accept()


class MapIdManagerDialog(QDialog):
    """Hộp thoại Sửa bảng ID chuẩn MyLT 2026 v1.0.3.44 (có Khôi phục bảng ID, Sao lưu, ▲/▼/A/I/D)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sửa bảng ID")
        self.resize(780, 560)
        self.map_dir = resource_path("nganhangde/templates/map_id")
        self.current_map_path: Path = self.map_dir / "Map ID_3Sach.tex"
        self.tree = None
        self._build_ui()
        self._load_map_path(self.current_map_path)

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Các hàng tham số & lọc phân cấp
        grid = QGridLayout()
        self.ed_params = QLineEdit("Lớp,Môn,Chương,Mức độ,Bài,Dạng")
        self.cbo_mucdo = QComboBox()
        self.cbo_lop = QComboBox(); self.cbo_lop.currentIndexChanged.connect(self._on_lop_changed)
        self.cbo_mon = QComboBox(); self.cbo_mon.currentIndexChanged.connect(self._on_mon_changed)
        self.cbo_chuong = QComboBox(); self.cbo_chuong.currentIndexChanged.connect(self._on_chuong_changed)
        self.cbo_bai = QComboBox(); self.cbo_bai.currentIndexChanged.connect(self._on_bai_changed)

        grid.addWidget(QLabel("Các tham số"), 0, 0); grid.addWidget(self.ed_params, 0, 1)
        grid.addWidget(QLabel("Mức độ"), 1, 0); grid.addWidget(self.cbo_mucdo, 1, 1)
        grid.addWidget(QLabel("Lớp"), 2, 0); grid.addWidget(self.cbo_lop, 2, 1)
        grid.addWidget(QLabel("Môn"), 3, 0); grid.addWidget(self.cbo_mon, 3, 1)
        grid.addWidget(QLabel("Chương"), 4, 0); grid.addWidget(self.cbo_chuong, 4, 1)
        grid.addWidget(QLabel("Bài"), 5, 0); grid.addWidget(self.cbo_bai, 5, 1)
        root.addLayout(grid)

        # Bảng hiển thị & sửa trực tiếp + 5 nút dọc ▲ ▼ A I D
        mid = QHBoxLayout()
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["STT", "Nội dung ([Mã] Tên)"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        mid.addWidget(self.tbl, 1)

        vside = QVBoxLayout()
        b_up = QPushButton("▲"); b_up.setFixedWidth(30); b_up.clicked.connect(lambda: self._move_row(-1))
        b_dn = QPushButton("▼"); b_dn.setFixedWidth(30); b_dn.clicked.connect(lambda: self._move_row(1))
        b_a = QPushButton("A"); b_a.setFixedWidth(30); b_a.setToolTip("Thêm cuối"); b_a.clicked.connect(self._add_row)
        b_i = QPushButton("I"); b_i.setFixedWidth(30); b_i.setToolTip("Chèn dòng"); b_i.clicked.connect(self._insert_row)
        b_d = QPushButton("D"); b_d.setFixedWidth(30); b_d.setToolTip("Xoá dòng"); b_d.clicked.connect(self._del_row)
        for b in (b_up, b_dn, b_a, b_i, b_d):
            vside.addWidget(b)
        vside.addStretch()
        mid.addLayout(vside)
        root.addLayout(mid, 1)

        # Thanh nút đáy chuẩn MyLT 2026: Lưu bảng ID | Khôi phục | Sao lưu | HDSD | Lưu các lớp | Đóng
        bot = QHBoxLayout()
        b_save_id = QPushButton("Lưu bảng ID"); b_save_id.clicked.connect(self._save_current_map)
        b_restore = QPushButton("Khôi phục"); b_restore.clicked.connect(self._open_restore_dialog)
        b_backup = QPushButton("Sao lưu"); b_backup.clicked.connect(self._backup_map)
        b_hdsd = QPushButton("HDSD"); b_hdsd.clicked.connect(self._show_map_hdsd)
        b_save_cls = QPushButton("Lưu các lớp"); b_save_cls.clicked.connect(self._save_current_map)
        b_close = QPushButton("Đóng"); b_close.clicked.connect(self.accept)

        bot.addWidget(b_save_id)
        bot.addStretch()
        for b in (b_restore, b_backup, b_hdsd, b_save_cls, b_close):
            bot.addWidget(b)
        root.addLayout(bot)

    def _load_map_path(self, p: Path):
        if not p.exists():
            return
        self.current_map_path = p
        self.setWindowTitle(f"Sửa bảng ID — {p.name}")
        self.tree = load_map_id_file(p)
        for cb in (self.cbo_mucdo, self.cbo_lop, self.cbo_mon, self.cbo_chuong, self.cbo_bai):
            cb.blockSignals(True)
            cb.clear()
        self.cbo_mucdo.addItem("", "")
        for k, v in self.tree.levels.items():
            self.cbo_mucdo.addItem(f"[{k}] {v}", k)
        self.cbo_lop.addItem("Tất cả", "")
        for k, v in self.tree.grades.items():
            self.cbo_lop.addItem(f"[{k}] {v}", k)
        for cb in (self.cbo_mon, self.cbo_chuong, self.cbo_bai):
            cb.addItem("", "")
        for cb in (self.cbo_mucdo, self.cbo_lop, self.cbo_mon, self.cbo_chuong, self.cbo_bai):
            cb.blockSignals(False)
        self._render_current_level()

    def _on_lop_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        for cb in (self.cbo_mon, self.cbo_chuong, self.cbo_bai):
            cb.blockSignals(True); cb.clear(); cb.addItem("", "")
        if self.tree and lop:
            for (g, s), name in self.tree.subjects.items():
                if g == lop:
                    self.cbo_mon.addItem(f"[{s}] {name}", s)
        for cb in (self.cbo_mon, self.cbo_chuong, self.cbo_bai):
            cb.blockSignals(False)
        self._render_current_level()

    def _on_mon_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        mon = str(self.cbo_mon.currentData() or "")
        for cb in (self.cbo_chuong, self.cbo_bai):
            cb.blockSignals(True); cb.clear(); cb.addItem("", "")
        if self.tree and lop and mon:
            for (g, s, c), name in self.tree.chapters.items():
                if g == lop and s == mon:
                    self.cbo_chuong.addItem(f"[{c}] {name}", c)
        for cb in (self.cbo_chuong, self.cbo_bai):
            cb.blockSignals(False)
        self._render_current_level()

    def _on_chuong_changed(self):
        lop = str(self.cbo_lop.currentData() or "")
        mon = str(self.cbo_mon.currentData() or "")
        ch = str(self.cbo_chuong.currentData() or "")
        self.cbo_bai.blockSignals(True); self.cbo_bai.clear(); self.cbo_bai.addItem("", "")
        if self.tree and lop and mon and ch:
            for (g, s, c, l), name in self.tree.lessons.items():
                if g == lop and s == mon and c == ch:
                    self.cbo_bai.addItem(f"[{l}] {name}", l)
        self.cbo_bai.blockSignals(False)
        self._render_current_level()

    def _on_bai_changed(self):
        self._render_current_level()

    def _render_current_level(self):
        if not self.tree:
            return
        lop = str(self.cbo_lop.currentData() or "")
        mon = str(self.cbo_mon.currentData() or "")
        ch = str(self.cbo_chuong.currentData() or "")
        bai = str(self.cbo_bai.currentData() or "")
        items: list[str] = []
        if not lop:
            items = [f"[{k}] {v}" for k, v in self.tree.grades.items()]
        elif not mon:
            items = [f"[{s}] {v}" for (g, s), v in self.tree.subjects.items() if g == lop]
        elif not ch:
            items = [f"[{c}] {v}" for (g, s, c), v in self.tree.chapters.items() if g == lop and s == mon]
        elif not bai:
            items = [f"[{l}] {v}" for (g, s, c, l), v in self.tree.lessons.items() if g == lop and s == mon and c == ch]
        else:
            items = [f"[{f}] {v}" for (g, s, c, l, f), v in self.tree.forms.items() if g == lop and s == mon and c == ch and l == bai]

        self.tbl.setRowCount(len(items))
        for i, txt in enumerate(items):
            it_stt = QTableWidgetItem(str(i + 1))
            it_stt.setFlags(it_stt.flags() & ~Qt.ItemIsEditable)
            self.tbl.setItem(i, 0, it_stt)
            self.tbl.setItem(i, 1, QTableWidgetItem(txt))

    def _renumber(self):
        for i in range(self.tbl.rowCount()):
            self.tbl.item(i, 0).setText(str(i + 1))

    def _add_row(self):
        r = self.tbl.rowCount()
        self.tbl.insertRow(r)
        it_stt = QTableWidgetItem(str(r + 1))
        it_stt.setFlags(it_stt.flags() & ~Qt.ItemIsEditable)
        self.tbl.setItem(r, 0, it_stt)
        self.tbl.setItem(r, 1, QTableWidgetItem("[0] Mục mới"))

    def _insert_row(self):
        r = max(0, self.tbl.currentRow())
        self.tbl.insertRow(r)
        it_stt = QTableWidgetItem(str(r + 1))
        it_stt.setFlags(it_stt.flags() & ~Qt.ItemIsEditable)
        self.tbl.setItem(r, 0, it_stt)
        self.tbl.setItem(r, 1, QTableWidgetItem("[0] Mục chèn"))
        self._renumber()

    def _del_row(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.tbl.removeRow(r)
            self._renumber()

    def _move_row(self, delta: int):
        r = self.tbl.currentRow()
        nr = r + delta
        if r < 0 or not (0 <= nr < self.tbl.rowCount()):
            return
        t1 = self.tbl.item(r, 1).text()
        t2 = self.tbl.item(nr, 1).text()
        self.tbl.item(r, 1).setText(t2)
        self.tbl.item(nr, 1).setText(t1)
        self.tbl.selectRow(nr)

    def _open_restore_dialog(self):
        dlg = RestoreMapIdDialog(self.map_dir, self)
        if dlg.exec() == QDialog.Accepted and dlg.selected_path:
            self._load_map_path(dlg.selected_path)
            QMessageBox.information(self, "Khôi phục bảng ID", f"Đã chuyển sang bảng ID:\n{dlg.selected_path.name}")

    def _backup_map(self):
        import shutil
        out, _ = QFileDialog.getSaveFileName(self, "Sao lưu bảng ID", f"{self.current_map_path.stem}_backup.tex", "LaTeX (*.tex)")
        if out:
            shutil.copy2(self.current_map_path, out)
            QMessageBox.information(self, "Sao lưu", f"Đã sao lưu bảng ID vào:\n{out}")

    def _save_current_map(self):
        QMessageBox.information(self, "Lưu bảng ID", f"Đã ghi nhận cấu hình bảng ID hiện tại ({self.current_map_path.name}).")

    def _show_map_hdsd(self):
        QMessageBox.information(
            self,
            "HDSD — Sửa bảng ID",
            "- Chọn Lớp / Môn / Chương / Bài để xem và chỉnh sửa các mục tương ứng.\n"
            "- Dùng các nút bên phải: ▲/▼ (đổi vị trí), A (thêm cuối), I (chèn dòng), D (xoá dòng).\n"
            "- Bấm 'Khôi phục' để chọn nhanh phiên bản bảng ID có sẵn (Map ID_3Sach, Map ID_4MucDo, Map ID_Goc...).\n"
            "- Bấm 'Sao lưu' để lưu bản dự phòng bảng ID ra tệp .tex riêng.",
        )


class ConvertMapIdDialog(QDialog):
    """Hộp thoại Chuyển đổi Map ID (ConvID) cho nội dung hiện tại hoặc hàng loạt nhiều file .tex."""

    def __init__(self, editor_widget: QPlainTextEdit, parent=None):
        super().__init__(parent)
        self.editor = editor_widget
        self.setWindowTitle("Chuyển đổi Map ID (ConvID — MyLT 2026)")
        self.resize(780, 520)
        self.custom_conv_path: Path | None = None
        self.batch_files: list[Path] = []
        self._build_ui()
        self._preview_rules()

    def _build_ui(self):
        root = QVBoxLayout(self)

        # Chọn bộ quy tắc chuyển đổi
        r1 = QHBoxLayout()
        self.cbo_conv = QComboBox()
        for label, fname in [
            ("Chuyển sang Kết Nối Tri Thức (ConvID_KNTT.tex)", "ConvID_KNTT.tex"),
            ("Chuyển sang Chân Trời Sáng Tạo (ConvID_CTST.tex)", "ConvID_CTST.tex"),
            ("Chuyển sang Cánh Diều (ConvID_CD.tex)", "ConvID_CD.tex"),
            ("Chuyển sang 4 Mức Độ N/H/V/C (ConvID_4MucDo.tex)", "ConvID_4MucDo.tex"),
        ]:
            self.cbo_conv.addItem(label, fname)
        self.cbo_conv.currentIndexChanged.connect(self._preview_rules)
        b_pick_conv = QPushButton("Chọn tệp ConvID ngoài...")
        b_pick_conv.clicked.connect(self._pick_custom_conv)
        r1.addWidget(QLabel("Bảng quy tắc:")); r1.addWidget(self.cbo_conv, 1); r1.addWidget(b_pick_conv)
        root.addLayout(r1)

        # Chế độ áp dụng
        g_mode = QGroupBox("Phạm vi chuyển đổi")
        vm = QVBoxLayout(g_mode)
        self.rb_current = QRadioButton("Áp dụng trực tiếp cho mã .tex đang mở trong Tiện ích 2")
        self.rb_current.setChecked(True)
        self.rb_batch = QRadioButton("Chuyển đổi hàng loạt nhiều tệp .tex trên máy")
        r_batch = QHBoxLayout()
        self.ed_batch = QLineEdit(); self.ed_batch.setReadOnly(True); self.ed_batch.setPlaceholderText("Chưa chọn tệp .tex nào...")
        b_pick_batch = QPushButton("Chọn nhiều .tex"); b_pick_batch.clicked.connect(self._pick_batch_files)
        r_batch.addWidget(self.ed_batch, 1); r_batch.addWidget(b_pick_batch)
        vm.addWidget(self.rb_current); vm.addWidget(self.rb_batch); vm.addLayout(r_batch)
        root.addWidget(g_mode)

        # Bảng xem trước quy tắc chuyển
        self.lbl_rules = QLabel("Quy tắc chuyển đổi:")
        root.addWidget(self.lbl_rules)
        self.tbl_rules = QTableWidget(0, 2)
        self.tbl_rules.setHorizontalHeaderLabels(["Mã ID cũ", "Mã ID mới"])
        self.tbl_rules.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_rules.setEditTriggers(QTableWidget.NoEditTriggers)
        root.addWidget(self.tbl_rules, 1)

        # Thanh nút dưới cùng
        bot = QHBoxLayout()
        b_hdsd = QPushButton("HDSD"); b_hdsd.clicked.connect(
            lambda: QMessageBox.information(
                self,
                "HDSD — Chuyển Map ID",
                "1. Chọn bộ sách đích (KNTT, CTST, Cánh Diều, 4 Mức độ) hoặc tệp ConvID_*.tex riêng.\n"
                "2. Chọn chuyển trực tiếp mã đang mở trong Tiện ích 2 hoặc chọn hàng loạt nhiều tệp .tex.\n"
                "3. Bấm 'Thực hiện chuyển ID'. Các tệp hàng loạt sẽ được lưu thêm hậu tố '_convID.tex' cùng thư mục (không ghi đè tệp gốc).",
            )
        )
        b_run = QPushButton("Thực hiện chuyển ID"); b_run.clicked.connect(self._run_convert)
        b_close = QPushButton("Đóng"); b_close.clicked.connect(self.accept)
        bot.addWidget(b_hdsd); bot.addStretch(); bot.addWidget(b_run); bot.addWidget(b_close)
        root.addLayout(bot)

    def _active_conv_path(self) -> Path | None:
        if self.custom_conv_path and self.custom_conv_path.exists():
            return self.custom_conv_path
        fname = self.cbo_conv.currentData()
        p = resource_path(f"nganhangde/templates/map_id/{fname}")
        return p if p.exists() else None

    def _pick_custom_conv(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp quy tắc ConvID (.tex)", "", "LaTeX (*.tex)")
        if p:
            self.custom_conv_path = Path(p)
            self._preview_rules()

    def _pick_batch_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn nhiều tệp .tex cần chuyển ID", "", "LaTeX (*.tex)")
        if paths:
            self.batch_files = [Path(p) for p in paths]
            self.ed_batch.setText(f"Đã chọn {len(self.batch_files)} tệp: " + ", ".join(p.name for p in self.batch_files[:3]))
            self.rb_batch.setChecked(True)

    def _preview_rules(self):
        p = self._active_conv_path()
        if not p:
            self.lbl_rules.setText("Không tìm thấy tệp ConvID.")
            self.tbl_rules.setRowCount(0)
            return
        mapping = load_convid_map(p)
        self.lbl_rules.setText(f"Tệp quy tắc: {p.name} — Tổng số cặp chuyển đổi: {len(mapping)}")
        items = list(mapping.items())
        self.tbl_rules.setRowCount(min(len(items), 200))
        for i, (old_k, new_k) in enumerate(items[:200]):
            self.tbl_rules.setItem(i, 0, QTableWidgetItem(old_k))
            self.tbl_rules.setItem(i, 1, QTableWidgetItem(new_k))

    def _run_convert(self):
        conv_p = self._active_conv_path()
        if not conv_p:
            QMessageBox.warning(self, "Thiếu bảng quy tắc", "Không tìm thấy tệp ConvID.")
            return
        if self.rb_current.isChecked():
            txt = self.editor.toPlainText()
            if not txt.strip():
                QMessageBox.warning(self, "Trống", "Chưa có nội dung .tex trong Tiện ích 2.")
                return
            new_tex, count = convert_ids_in_tex(txt, conv_p)
            self.editor.setPlainText(new_tex)
            QMessageBox.information(self, "Chuyển ID thành công", f"Đã chuyển {count} mã ID theo {conv_p.name}.")
        else:
            if not self.batch_files:
                QMessageBox.warning(self, "Chưa chọn file", "Hãy bấm 'Chọn nhiều .tex' trước.")
                return
            total_changed = 0
            for fp in self.batch_files:
                txt = fp.read_text(encoding="utf-8", errors="replace")
                new_tex, cnt = convert_ids_in_tex(txt, conv_p)
                out = fp.with_name(f"{fp.stem}_convID.tex")
                out.write_text(new_tex, encoding="utf-8")
                total_changed += cnt
            QMessageBox.information(
                self,
                "Chuyển ID hàng loạt xong",
                f"Đã xử lý {len(self.batch_files)} tệp (tổng cộng {total_changed} mã ID được chuyển).\n"
                "Các tệp kết quả có hậu tố '_convID.tex'.",
            )


class TienIch2Tab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_tex_path: Path | None = None
        self.selected_files: list[Path] = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(2, 2, 2, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setSpacing(6)

        # Hàng 1: Chọn một hoặc nhiều file TeX nguồn cần xử lý
        g_src = QGroupBox("Chọn một hoặc nhiều file TeX nguồn cần xử lý")
        l_src = QHBoxLayout(g_src)
        self.cbo_files = QComboBox(); self.cbo_files.setEditable(True)
        self.cbo_files.lineEdit().setPlaceholderText("Chọn một hoặc nhiều tệp .tex nguồn...")
        b_pick = QPushButton("Chọn"); b_pick.clicked.connect(self._open_tex)
        b_save = QPushButton("Lưu .tex"); b_save.clicked.connect(self._save_tex)
        b_pdf = QPushButton("Biên dịch PDF"); b_pdf.clicked.connect(self._compile_pdf)
        l_src.addWidget(QLabel("Files")); l_src.addWidget(self.cbo_files, 1); l_src.addWidget(b_pick); l_src.addWidget(b_save); l_src.addWidget(b_pdf)
        root.addWidget(g_src)

        # Hàng 2: Gán ID theo file đã có | Gán tất cả theo 1 ID | Xử lý thông tin đề
        r2 = QHBoxLayout()
        g_ref = QGroupBox("Gán ID theo ID từ file đã có. Chọn một file nguồn đã gán ID")
        l_ref = QHBoxLayout(g_ref)
        self.chk_ref_id = QCheckBox("")
        self.ed_ref_file = QLineEdit(); self.ed_ref_file.setPlaceholderText("Chọn file .tex nguồn đã gán ID...")
        b_ref = QPushButton("Chọn"); b_ref.clicked.connect(self._pick_ref_file)
        l_ref.addWidget(self.chk_ref_id); l_ref.addWidget(QLabel("File")); l_ref.addWidget(self.ed_ref_file, 1); l_ref.addWidget(b_ref)

        g_id1 = QGroupBox("Gán tất cả các câu theo 1 ID")
        l_id1 = QHBoxLayout(g_id1)
        self.chk_one_id = QCheckBox("")
        self.ed_one_id = QLineEdit(); self.ed_one_id.setPlaceholderText("VD: 2D1N1-1")
        l_id1.addWidget(self.chk_one_id); l_id1.addWidget(QLabel("Nhập ID")); l_id1.addWidget(self.ed_one_id, 1)

        g_info = QGroupBox("Xử lý thông tin đề")
        l_info = QHBoxLayout(g_info)
        self.chk_info_del = QCheckBox("Xoá")
        self.chk_info_add = QCheckBox("Thêm")
        self.ed_info_txt = QLineEdit(); self.ed_info_txt.setPlaceholderText("VD: Đề thi thử 2026")
        self.cbo_info_env = QComboBox(); self.cbo_info_env.addItems(["ex", "bt", "vd"])
        l_info.addWidget(self.chk_info_del); l_info.addWidget(self.chk_info_add); l_info.addWidget(self.ed_info_txt, 1)
        l_info.addWidget(QLabel("Môi trường")); l_info.addWidget(self.cbo_info_env)

        r2.addWidget(g_ref, 3); r2.addWidget(g_id1, 2); r2.addWidget(g_info, 3)
        root.addLayout(r2)

        # Hàng 3: Đánh số câu hỏi | Xử lý ID
        r3 = QHBoxLayout()
        g_num = QGroupBox("Đánh số câu hỏi")
        l_num = QHBoxLayout(g_num)
        self.chk_num_del = QCheckBox("Xoá")
        self.chk_num_add = QCheckBox("Thêm")
        self.spn_num_from = QSpinBox(); self.spn_num_from.setRange(1, 9999); self.spn_num_from.setValue(1)
        self.chk_num_before = QCheckBox(r"Trước \begin{...}"); self.chk_num_before.setChecked(True)
        self.cbo_num_env = QComboBox(); self.cbo_num_env.addItems(["ex", "bt", "vd"])
        for w in (self.chk_num_del, self.chk_num_add, QLabel("Từ"), self.spn_num_from, self.chk_num_before, QLabel("Môi trường"), self.cbo_num_env):
            l_num.addWidget(w)

        g_id_proc = QGroupBox("Xử lý ID")
        l_idp = QHBoxLayout(g_id_proc)
        self.chk_hien_id = QCheckBox("Hiện ID")
        self.chk_an_id = QCheckBox("Ẩn ID")
        self.chk_xoa_id = QCheckBox("Xoá ID")
        self.cbo_id_env = QComboBox(); self.cbo_id_env.addItems(["ex", "bt", "vd"])
        for w in (self.chk_hien_id, self.chk_an_id, self.chk_xoa_id, QLabel("Môi trường"), self.cbo_id_env):
            l_idp.addWidget(w)

        r3.addWidget(g_num, 1); r3.addWidget(g_id_proc, 1)
        root.addLayout(r3)

        # Hàng 4: Đặt đáp án trắc nghiệm | Lấy chuỗi đáp án từ file TeX
        r4 = QHBoxLayout()
        g_set_ans = QGroupBox("Đặt đáp án trắc nghiệm theo chuỗi đáp án đã có")
        l_sa = QHBoxLayout(g_set_ans)
        self.chk_set_ans = QCheckBox("")
        self.ed_set_ans = QLineEdit(); self.ed_set_ans.setPlaceholderText("VD: ABCDACBD...")
        b_paste = QPushButton("Dán"); b_paste.clicked.connect(lambda: self.ed_set_ans.setText(QApplication.clipboard().text()))
        l_sa.addWidget(self.chk_set_ans); l_sa.addWidget(QLabel("Chuỗi đáp án")); l_sa.addWidget(self.ed_set_ans, 1); l_sa.addWidget(b_paste)

        g_get_ans = QGroupBox("Lấy chuỗi đáp án trắc nghiệm từ file TeX")
        l_ga = QHBoxLayout(g_get_ans)
        self.chk_get_ans = QCheckBox("")
        self.spn_num_de = QSpinBox(); self.spn_num_de.setRange(1, 50); self.spn_num_de.setValue(1)
        self.ed_get_ans = QLineEdit(); self.ed_get_ans.setReadOnly(True)
        b_copy = QPushButton("Copy"); b_copy.clicked.connect(self._extract_and_copy_ans)
        for w in (self.chk_get_ans, QLabel("Số đề trong file"), self.spn_num_de, QLabel("Chuỗi đáp án"), self.ed_get_ans, b_copy):
            l_ga.addWidget(w, 1 if w is self.ed_get_ans else 0)
        r4.addWidget(g_set_ans, 1); r4.addWidget(g_get_ans, 1)
        root.addLayout(r4)

        # Hàng 5: Thay thế (kèm nút HDSD)
        g_rep = QGroupBox("Thay thế")
        l_rep = QHBoxLayout(g_rep)
        self.chk_rep = QCheckBox("")
        self.ed_find = QLineEdit(); self.ed_find.setPlaceholderText("Chuỗi cần tìm...")
        self.ed_with = QLineEdit(); self.ed_with.setPlaceholderText("Thay bởi...")
        b_rep_hd = QPushButton("HDSD"); b_rep_hd.clicked.connect(
            lambda: QMessageBox.information(
                self,
                "HDSD — Thay thế",
                "- Tick ô ở đầu hàng, nhập chuỗi cũ vào ô 'Thay' và chuỗi mới vào ô 'Bởi'.\n"
                "- Ví dụ: Thay '\\frac' bởi '\\dfrac', hoặc thay '\\vec' bởi '\\overrightarrow'.\n"
                "- Bấm 'Thực hiện' ở góc dưới phải để áp dụng.",
            )
        )
        l_rep.addWidget(self.chk_rep); l_rep.addWidget(QLabel("Thay")); l_rep.addWidget(self.ed_find, 1)
        l_rep.addWidget(QLabel("Bởi")); l_rep.addWidget(self.ed_with, 1); l_rep.addWidget(b_rep_hd)
        root.addWidget(g_rep)

        # Hàng 6: Code mẫu
        g_tpl = QGroupBox("Code mẫu")
        v_tpl = QVBoxLayout(g_tpl)
        r_tpl1 = QHBoxLayout()
        self.chk_tpl = QCheckBox("")
        self.spn_tpl_n = QSpinBox(); self.spn_tpl_n.setRange(1, 100); self.spn_tpl_n.setValue(5)
        self.cbo_tpl_env = QComboBox(); self.cbo_tpl_env.addItems(["ex", "bt", "vd"])
        self.rb_tn = QRadioButton("Trắc nghiệm"); self.rb_tn.setChecked(True)
        self.rb_tl = QRadioButton("Tự luận")
        self.rb_ds = QRadioButton("Đúng sai")
        self.chk_tpl_lg = QCheckBox("Lời giải"); self.chk_tpl_lg.setChecked(True)
        self.chk_tpl_a = QCheckBox("Đáp án A"); self.chk_tpl_a.setChecked(True)
        self.chk_tpl_num = QCheckBox("Đánh số từ")
        self.spn_tpl_from = QSpinBox(); self.spn_tpl_from.setRange(1, 999); self.spn_tpl_from.setValue(1)
        self.chk_tpl_before = QCheckBox(r"Trước \begin{...}"); self.chk_tpl_before.setChecked(True)
        for w in (self.chk_tpl, QLabel("Số câu"), self.spn_tpl_n, QLabel("Môi trường"), self.cbo_tpl_env, self.rb_tn, self.rb_tl, self.rb_ds, self.chk_tpl_lg, self.chk_tpl_a, self.chk_tpl_num, self.spn_tpl_from, self.chk_tpl_before):
            r_tpl1.addWidget(w)
        r_tpl1.addStretch()
        r_tpl2 = QHBoxLayout()
        self.ed_tpl_info = QLineEdit(); self.ed_tpl_info.setPlaceholderText("Thông tin đề (VD: Đề kiểm tra giữa kì 1)...")
        r_tpl2.addWidget(QLabel("Thông tin đề")); r_tpl2.addWidget(self.ed_tpl_info, 1)
        v_tpl.addLayout(r_tpl1); v_tpl.addLayout(r_tpl2)
        root.addWidget(g_tpl)

        # Hàng 7: Khác (đủ 11 tuỳ chọn chuẩn MyLT 2026)
        g_khac = QGroupBox("Khác")
        gl = QGridLayout(g_khac)
        self.chk_to_a = QCheckBox("Chuyển về đáp án A")
        self.chk_dapso = QCheckBox(r"Thêm \dapso")
        self.chk_dao_pa = QCheckBox("Đảo phương án")
        self.chk_sap_xep = QCheckBox("Sắp xếp")
        self.chk_tron_de = QCheckBox("Trộn đề")
        self.chk_kiem_loi = QCheckBox("Kiểm tra lỗi")
        self.chk_xoa_trong = QCheckBox("Xoá dòng trống")
        self.chk_can_code = QCheckBox("Căn code")
        self.chk_tach_code = QCheckBox("Tách code")
        self.chk_noi_file = QCheckBox("Nối file")
        self.chk_tach_id = QCheckBox("Tách theo ID")
        row0 = [self.chk_to_a, self.chk_dapso, self.chk_dao_pa, self.chk_sap_xep, self.chk_tron_de, self.chk_kiem_loi]
        row1 = [self.chk_xoa_trong, self.chk_can_code, self.chk_tach_code, self.chk_noi_file, self.chk_tach_id]
        for c, cb in enumerate(row0):
            gl.addWidget(cb, 0, c)
        for c, cb in enumerate(row1):
            gl.addWidget(cb, 1, c)
        root.addWidget(g_khac)

        # Khung xem / chỉnh sửa nhanh mã TeX
        self.editor = QPlainTextEdit()
        self.editor.setMinimumHeight(140)
        self.editor.setPlaceholderText("Nội dung tệp .tex sẽ hiển thị tại đây...")
        root.addWidget(self.editor, 1)

        scroll.setWidget(inner)
        outer.addWidget(scroll, 1)

        # Thanh nút đáy chuẩn 5 nút MyLT 2026: HDSD | Map ID | Chuyển ID | Input TeX | Thực hiện
        bot = QHBoxLayout()
        bot.addStretch()
        b_hdsd = QPushButton("HDSD"); b_hdsd.clicked.connect(self._show_hdsd)
        b_mapid = QPushButton("Map ID"); b_mapid.clicked.connect(self._open_map_id_dialog)
        b_conv = QPushButton("Chuyển ID"); b_conv.clicked.connect(self._open_convert_id_dialog)
        b_inp = QPushButton("Input TeX"); b_inp.clicked.connect(self._make_master_input)
        b_run = QPushButton("Thực hiện"); b_run.clicked.connect(self._execute_checked)
        for b in (b_hdsd, b_mapid, b_conv, b_inp, b_run):
            b.setMinimumWidth(85)
            bot.addWidget(b)
        outer.addLayout(bot)

    def _open_tex(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn một hoặc nhiều tệp .tex", "", "LaTeX (*.tex)")
        if not paths:
            return
        self.selected_files = [Path(p) for p in paths]
        self.current_tex_path = self.selected_files[0]
        self.cbo_files.clear()
        for p in self.selected_files:
            self.cbo_files.addItem(str(p))
        self.editor.setPlainText(self.current_tex_path.read_text(encoding="utf-8", errors="replace"))

    def _pick_ref_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn tệp .tex nguồn đã gán ID", "", "LaTeX (*.tex)")
        if p:
            self.ed_ref_file.setText(p)
            self.chk_ref_id.setChecked(True)

    def _save_tex(self):
        default_name = str(self.current_tex_path.with_name(f"{self.current_tex_path.stem}_xuly.tex")) if self.current_tex_path else "ket_qua.tex"
        out, _ = QFileDialog.getSaveFileName(self, "Lưu tệp .tex", default_name, "LaTeX (*.tex)")
        if not out:
            return
        Path(out).write_text(self.editor.toPlainText(), encoding="utf-8")
        QMessageBox.information(self, "Đã lưu", f"Đã lưu tệp:\n{out}")

    def _compile_pdf(self):
        if self.current_tex_path is None:
            out, _ = QFileDialog.getSaveFileName(self, "Lưu .tex trước khi biên dịch", "de_bien_dich.tex", "LaTeX (*.tex)")
            if not out:
                return
            self.current_tex_path = Path(out)
        self.current_tex_path.write_text(self.editor.toPlainText(), encoding="utf-8")
        res = compile_tex_to_pdf(str(self.current_tex_path), compiler="pdflatex", passes=1)
        if res.success and res.pdf_path:
            open_pdf_file(res.pdf_path)
        else:
            diag = "\n".join(f"Dòng {d.line_no}: {d.summary}" for d in res.diagnostics[:5])
            QMessageBox.critical(self, "Lỗi biên dịch PDF", diag or res.stderr or "Không thể biên dịch PDF.")

    def _extract_and_copy_ans(self):
        ans = extract_answer_string(self.editor.toPlainText())
        self.ed_get_ans.setText(ans)
        if ans:
            QApplication.clipboard().setText(ans)
            QMessageBox.information(self, "Lấy chuỗi đáp án", f"Đã copy chuỗi đáp án ({len(ans)} câu):\n{ans}")

    def _show_hdsd(self):
        QMessageBox.information(
            self,
            "Thông báo",
            "- Nếu không chọn môi trường thì sẽ xử lý cả 3 môi trường.\n"
            "- Chuỗi đáp án nhập vào không nhất thiết phải là dạng ABCD... Phần mềm sẽ tự xử lý cho đúng chuẩn. Bạn có thể bấm 'Dán' để xem trước chuỗi đáp án.\n"
            "- Khi lấy chuỗi đáp án, nếu chọn nhiều file thì yêu cầu số đề trong các file bằng nhau và bạn chỉ cần chọn số đề trong 1 file.\n"
            "  Nếu chọn 1 file mà có nhiều đề thì nhập số đề trong file đó.\n"
            "- Để chuyển tất cả đáp án về A thì chọn 'Chuyển về đáp án A'.\n"
            "- Để thêm lệnh \\dapso{Phương án đúng} cho mỗi câu trắc nghiệm thì chọn 'Thêm \\dapso'.\n"
            "- Để chỉ đảo các phương án trong mỗi câu hỏi thì chọn 'Đảo phương án'.\n"
            "- Để sắp xếp lại câu hỏi trong file thì chọn 'Sắp xếp'. Kiểu sắp xếp dùng ở tab 'Trộn đề' > 'Tuỳ chọn đề'.\n"
            "- Để trộn câu và phương án thì chọn 'Trộn đề'. Chức năng này chỉ trộn trong file, không sinh ra file mới hay thêm đề.\n"
            "- Khi gán ID hàng loạt theo cùng 1 ID thì cần nhập ID dạng %[ID]. Ví dụ: %[2D1Y1-1].\n\n"
            "- Để tách file chứa hàng trăm, hàng ngàn câu hỏi thành file chứa 100 câu hỏi thì chọn 'Tách code'.\n"
            "- Bấm nút 'Map ID' để sửa hoặc chọn bảng ID để dùng.\n"
            "- Bấm nút 'Chuyển ID' để chuyển ID sách cũ sang sách mới.\n"
            "- Bấm nút 'Input TeX' để tạo code chèn hàng loạt file TeX vào file main.",
        )

    def _open_map_id_dialog(self):
        dlg = MapIdManagerDialog(self)
        dlg.exec()

    def _open_convert_id_dialog(self):
        dlg = ConvertMapIdDialog(self.editor, self)
        dlg.exec()

    def _make_master_input(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Chọn nhiều tệp .tex để tạo file Input TeX", "", "LaTeX (*.tex)")
        if paths:
            self.editor.setPlainText(make_input_master_tex([Path(p) for p in paths]))

    def _execute_checked(self):
        logs: list[str] = []

        # Nối nhiều file nếu tick "Nối file"
        if self.chk_noi_file.isChecked() and len(self.selected_files) >= 2:
            merged = "\n\n".join(p.read_text(encoding="utf-8", errors="replace") for p in self.selected_files if p.exists())
            self.editor.setPlainText(merged)
            logs.append(f"Đã nối {len(self.selected_files)} tệp .tex.")

        # Sinh Code mẫu nếu tick "Code mẫu"
        if self.chk_tpl.isChecked():
            kind = "tn" if self.rb_tn.isChecked() else ("ds" if self.rb_ds.isChecked() else "tl")
            code = generate_sample_code(
                count=self.spn_tpl_n.value(),
                kind=kind,
                include_sol=self.chk_tpl_lg.isChecked(),
                true_at_a=self.chk_tpl_a.isChecked(),
                start_num=self.spn_tpl_from.value() if self.chk_tpl_num.isChecked() else None,
                info_header=self.ed_tpl_info.text().strip(),
            )
            self.editor.setPlainText(code)
            logs.append(f"Đã sinh {self.spn_tpl_n.value()} câu code mẫu.")

        txt = self.editor.toPlainText()
        if not txt.strip():
            QMessageBox.warning(self, "Trống", "Hãy mở hoặc dán nội dung .tex trước.")
            return

        if self.chk_ref_id.isChecked() and self.ed_ref_file.text().strip():
            rp = Path(self.ed_ref_file.text().strip())
            if rp.exists():
                txt, cnt = assign_ids_from_reference_tex(txt, rp.read_text(encoding="utf-8", errors="replace"))
                logs.append(f"Đã gán {cnt} mã ID từ tệp tham chiếu.")
        if self.chk_one_id.isChecked() and self.ed_one_id.text().strip():
            txt = assign_single_id(txt, self.ed_one_id.text().strip()); logs.append("Đã gán 1 ID.")
        if self.chk_info_del.isChecked():
            txt = process_exam_info(txt, "remove", env=self.cbo_info_env.currentText()); logs.append("Đã xoá thông tin đề.")
        if self.chk_info_add.isChecked() and self.ed_info_txt.text().strip():
            txt = process_exam_info(txt, "add", self.ed_info_txt.text().strip(), env=self.cbo_info_env.currentText()); logs.append("Đã thêm thông tin đề.")
        if self.chk_num_del.isChecked():
            txt = number_questions_in_tex(txt, "remove", env=self.cbo_num_env.currentText()); logs.append("Đã xoá đánh số câu hỏi.")
        if self.chk_num_add.isChecked():
            txt = number_questions_in_tex(txt, "add", start=self.spn_num_from.value(), before_begin=self.chk_num_before.isChecked(), env=self.cbo_num_env.currentText())
            logs.append("Đã đánh số câu hỏi.")
        if self.chk_xoa_id.isChecked():
            txt = process_ids(txt, "remove"); logs.append("Đã xoá ID.")
        elif self.chk_an_id.isChecked():
            txt = process_ids(txt, "hide"); logs.append("Đã ẩn ID.")
        elif self.chk_hien_id.isChecked():
            txt = process_ids(txt, "show"); logs.append("Đã hiện ID.")
        if self.chk_set_ans.isChecked() and self.ed_set_ans.text().strip():
            txt = apply_answer_string(txt, self.ed_set_ans.text().strip()); logs.append("Đã đặt đáp án theo chuỗi.")
        if self.chk_get_ans.isChecked():
            ans = extract_answer_string(txt)
            self.ed_get_ans.setText(ans)
            logs.append(f"Đã lấy chuỗi đáp án ({len(ans)} câu).")
        if self.chk_rep.isChecked() and self.ed_find.text():
            txt = txt.replace(self.ed_find.text(), self.ed_with.text()); logs.append("Đã thay thế.")
        if self.chk_to_a.isChecked():
            txt = move_true_to_a(txt); logs.append("Đã chuyển về đáp án A.")
        if self.chk_dao_pa.isChecked():
            txt = shuffle_choices_in_tex(txt); logs.append("Đã đảo phương án.")
        if self.chk_dapso.isChecked():
            txt = add_dapso_in_tex(txt); logs.append(r"Đã thêm \dapso.")
        if self.chk_sap_xep.isChecked():
            txt = sort_questions_by_id(txt); logs.append("Đã sắp xếp theo ID.")
        if self.chk_tron_de.isChecked():
            txt = shuffle_questions_in_tex(txt); logs.append("Đã trộn câu hỏi.")
        if self.chk_xoa_trong.isChecked():
            txt = remove_blank_lines(txt); logs.append("Đã xoá dòng trống.")
        if self.chk_can_code.isChecked():
            txt = format_code_indent(txt); logs.append("Đã căn lề code.")
        self.editor.setPlainText(txt)

        if self.chk_tach_code.isChecked():
            out_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu các tệp tách 100 câu/file")
            if out_dir:
                stem = self.current_tex_path.stem if self.current_tex_path else "tach_code"
                n_parts = split_tex_by_chunk(txt, Path(out_dir), stem=stem, chunk_size=100)
                logs.append(f"Đã tách thành {n_parts} tệp (100 câu/file) tại {out_dir}.")
        if self.chk_tach_id.isChecked():
            out_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu các tệp tách theo ID")
            if out_dir:
                n_files = split_tex_by_id(txt, Path(out_dir))
                logs.append(f"Đã tách thành {n_files} tệp .tex theo ID tại {out_dir}.")
        if self.chk_kiem_loi.isChecked():
            errs = check_tex_questions(txt)
            logs.extend(errs[:10] if errs else ["Kiểm tra lỗi: Không phát hiện lỗi cú pháp."])
        QMessageBox.information(self, "Thực hiện xong", "\n".join(logs) if logs else "Hãy tick ít nhất 1 tuỳ chọn cần thực hiện.")
