"""Cửa sổ chính: menu, thanh công cụ, tab Ngân hàng câu hỏi và các thao tác trên kho."""
from __future__ import annotations

import os

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QAction, QColor, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QComboBox,
    QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView, QLineEdit, QMainWindow,
    QMessageBox, QProgressDialog, QPushButton, QSplitter, QTabWidget, QTableWidget, QTableWidgetItem, QTextBrowser,
    QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from .. import __version__
from ..db import Bank
from ..exporter import export_questions
from ..idcode import LOP, MON, parse_id
from ..parser import parse_file, validate
from .common import APP_NAME, TEN_LOAI, TEN_MUC, latex_editor, make_settings
from .dialogs.ai_settings import GeminiSettingsDialog
from .dialogs.assign_id import AssignIdDialog
from .dialogs.edit import EditDialog
from .dialogs.idmap import IdMapDialog
from .dialogs.pdf import PdfResultDialog, PdfSettingsDialog, prepare_tex_for_pdf
from .dialogs.update import UpdateDialog
from .workers import BuildWorker
from .bank_actions import BankActionsMixin
from .layout import LayoutMixin


class MainWindow(LayoutMixin, BankActionsMixin, QMainWindow):
    def __init__(self, db_path: str | None = None):
        super().__init__()
        from ..appdirs import default_db, ensure_layout
        ensure_layout()
        self.settings = make_settings()
        db_path = db_path or self.settings.value("db_path") or default_db()
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
        self._act(m, "Mở thư mục phần mềm (kho, mẫu đề, đề đã trộn…)", self.open_app_folder)
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
        self._act(m, "Gán ID tự động bằng AI…", lambda: self.assign_ids(use_ai=True), "Shift+F3")
        self._act(m, "Trợ lý AI (câu tương tự, bù ma trận, PDF → LaTeX, chấm tự luận)…", self.ai_assistant,
                  "Ctrl+Shift+I")
        self._act(m, "Tìm và thay thế…", self.find_replace, "Ctrl+H")
        self._act(m, "Khôi phục câu đã xoá…", self.restore_deleted)
        m = mb.addMenu("Đề &thi")
        self._act(m, "Tạo đề theo ma trận…", self.open_generator, "Ctrl+G")
        self._act(m, "Rà soát đáp án và lời giải…", self.open_review, "Ctrl+R")
        self._act(m, "Lịch sử ra đề…", self.show_batches)
        self._act(m, "Phòng thi LAN (học sinh làm bài qua Wi-Fi)…", self.open_arena)
        self._act(m, "Trình chiếu câu đã chọn (chữa đề trên máy chiếu)", self.present, "F11")
        m = mb.addMenu("Công &cụ")
        self._act(m, "Soát lỗi file .tex…", self.check_file)
        self._act(m, "Giải nghĩa ID (Map ID)…", self.edit_idmap, "Ctrl+M")
        self._act(m, "Tìm câu gần trùng trong kho…", self.near_dups)
        m.addSeparator()
        self._act(m, "Xem PDF câu đã chọn", self.preview_pdf, "F5")
        self._act(m, "Mở câu đã chọn trong TeXstudio", self.open_texstudio, "Ctrl+T")
        self._act(m, "Biên dịch file .tex → PDF…", self.compile_files)
        self._act(m, "Cài đặt biên dịch PDF…", self.pdf_settings_dialog)
        self._act(m, "Cài đặt AI (Gemini, Claude, OpenAI…)…", lambda: GeminiSettingsDialog(self).exec())
        self._act(m, "Thống kê ngân hàng", self.show_stats)
        m = mb.addMenu("Trợ &giúp")
        self._act(m, "Cập nhật phần mềm…", self.check_update)
        self._act(m, "Giới thiệu", self.about)

        # --- thanh công cụ
        tb = QToolBar("Công cụ")
        tb.setMovable(False)
        self.addToolBar(tb)
        for text, fn in (("📥 Nhập .tex", self.import_files), ("➕ Thêm câu", self.add_question),
                         ("✏️ Sửa", self.edit_question), ("🗑 Xoá", self.delete_questions),
                         ("🏷 Gán ID", self.assign_ids),
                         ("📤 Xuất câu", self.export_selected), ("🎲 Tạo đề", self.open_generator),
                         ("✅ Rà soát", self.open_review), ("📄 Xem PDF", self.preview_pdf),
                         ("📊 Thống kê", self.show_stats)):
            tb.addAction(text, fn)

        # --- cột trái: cây chương + bộ lọc
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(6, 6, 6, 6)
        ll.addWidget(self._source_box())
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
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["#", "Loại", "ID", "Mức độ", "Đáp án", "Đã dùng", "Diễn giải ID",
                                              "Nội dung"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        hh = self.table.horizontalHeader()
        for c, w in enumerate((50, 100, 90, 100, 70, 60, 220)):
            self.table.setColumnWidth(c, w)
        hh.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
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
        self._build_tabs(split)
        self.main_tabs.currentChanged.connect(self.on_tab_changed)
        self.setCentralWidget(self.main_tabs)
        self.statusBar().showMessage("Sẵn sàng")

    def on_tab_changed(self, _idx):
        w = self.current_panel()
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
    def open_bank(self, path: str, remember: bool = True):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            bank = Bank(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Lỗi", f"Không mở được kho:\n{path}\n\n{e}")
            return
        if self.bank:
            self.bank.close()
        self.bank = bank
        if remember:
            self.settings.setValue("db_path", os.path.abspath(path))
        self.setWindowTitle(f"{APP_NAME} – {os.path.abspath(path)}")
        notes = []
        if bank.migrated_from:
            notes.append(f"Kho đã được nâng cấp lên định dạng mới (bản sao lưu: {os.path.basename(path)}.bak).")
        if not [k for k in bank.idmap() if not k.startswith("#")]:
            from ..idmap import builtin_map
            m = builtin_map()
            if m:
                bank.set_idmap(m)
                notes.append(f"Đã nạp sẵn danh mục ID Toán 6–12 ({len(m)} mục) – sửa ở Công cụ → Giải nghĩa ID.")
        self.build_tree()
        self.refresh()
        self.gen_panel.update_avail()
        self.stats_panel.reload()
        if notes:
            self.statusBar().showMessage("  ".join(notes), 20000)

    def open_app_folder(self):
        from ..appdirs import home
        QDesktopServices.openUrl(QUrl.fromLocalFile(home()))

    def open_arena(self):
        from .dialogs.arena import ArenaDialog
        ArenaDialog(self).exec()

    def present(self):
        import tempfile
        from ..slides import export_slides
        ids = self.selected_ids()
        qs = [q for q in (self.bank.get(i) for i in ids) if q is not None] if ids else self.bank.search()[:50]
        if not qs:
            return
        d = tempfile.mkdtemp(prefix="nhd_trinhchieu_")
        p = export_slides(qs, os.path.join(d, "trinh_chieu.html"), "Trình chiếu")
        QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        self.statusBar().showMessage("Đã mở trình chiếu trong trình duyệt – bấm F để toàn màn hình, ←/→ chuyển câu, "
                                     "A đáp án, L lời giải, B bút vẽ.", 15000)

    def ai_assistant(self, tab: int = 0):
        from .dialogs.ai_assistant import AiAssistantDialog
        AiAssistantDialog(self, tab).exec()

    def show_batches(self):
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        rows = self.bank.batches()
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Lịch sử ra đề ({len(rows)} đợt)")
        dlg.resize(900, 460)
        lay = QVBoxLayout(dlg)
        t = QTableWidget(len(rows), 6)
        t.setHorizontalHeaderLabels(["Thời điểm", "Tên đề", "Mã đề", "Số câu", "Seed", "Thư mục"])
        t.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        for r_, b in enumerate(rows):
            for c, v in enumerate((b["at"].replace("T", " "), b["ten_de"], b["codes"], str(b["n"]), b["seed"],
                                   b["out_dir"])):
                t.setItem(r_, c, QTableWidgetItem(v))
        t.doubleClicked.connect(lambda i: QDesktopServices.openUrl(QUrl.fromLocalFile(rows[i.row()]["out_dir"])))
        lay.addWidget(t)
        from PySide6.QtWidgets import QLabel
        lay.addWidget(QLabel("Nhấp đúp để mở thư mục đề. Ở tab Tạo đề có ô «Tránh câu đã dùng trong N đợt gần nhất»."))
        dlg.exec()

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
        for r in self.bank.tree_stats():
            lop, mon, ch, n = r["lop"], r["mon"], r["chuong"], r["n"]
            bai, dang = r["bai"] or "", r["dang"] or ""
            kb = (lop or "") + (mon or "") + (ch or "") + bai
            path = [("lop", lop, f"Lớp {LOP.get(lop, lop)}" if lop else "Chưa có ID"),
                    ("mon", mon, names.get(lop + mon) or MON.get(mon, mon or "?")),
                    ("chuong", ch, names.get(lop + mon + ch) or f"Chương {ch}")]
            if bai:
                path.append(("bai", bai, f"Bài {bai}. {names[kb]}" if kb in names else f"Bài {bai}"))
                if dang:
                    kd = f"{kb}-{dang}"
                    path.append(("dang", dang, f"Dạng {dang}. {names[kd]}" if kd in names else f"Dạng {dang}"))
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
                              lop=tf.get("lop"), mon=tf.get("mon"), chuong=tf.get("chuong"),
                              bai=tf.get("bai"), dang=tf.get("dang"))
        used = dict(self.bank.con.execute("SELECT id, used_count FROM questions").fetchall())
        names = self.bank.idmap()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(qs))
        for r, q in enumerate(qs):
            idc = parse_id(q.id_code) if q.id_code else None
            expl = ""
            if idc:
                kb = idc.lop + idc.mon + idc.chuong + idc.bai
                expl = names.get(f"{kb}-{idc.dang}") or names.get(kb) or names.get(kb[:3], "")
            vals = [q.db_id, TEN_LOAI[q.qtype], q.id_code, TEN_MUC.get(idc.muc_do, "") if idc else "",
                    q.answer_text, used.get(q.db_id, 0), expl, " ".join(q.stem.split())]
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

    def check_update(self, silent=False, rel=None):
        """Mở hộp cập nhật. silent=True: chỉ hiện khi có bản mới (dùng lúc khởi động)."""
        from .. import updater
        if rel is None:
            try:
                rel = updater.latest_release()
            except updater.UpdateError as e:
                if not silent:
                    QMessageBox.warning(self, "Cập nhật", str(e))
                return
        if not updater.is_newer(rel.version, __version__):
            if not silent:
                QMessageBox.information(self, "Cập nhật", f"Bạn đang dùng bản mới nhất ({__version__}).")
            return
        if silent and self.settings.value("update/skip", "") == rel.version:
            return
        UpdateDialog(self, rel).exec()

    def open_texstudio(self):
        from ..editor import open_in_texstudio
        from ..exporter import fill, load_template, questions_to_tex
        ids = self.selected_ids()
        if not ids:
            QMessageBox.information(self, "TeXstudio", "Chọn câu cần mở trong bảng.")
            return
        import tempfile
        d = tempfile.mkdtemp(prefix="nhd_tex_")
        p = os.path.join(d, "cau_hoi.tex")
        qs = [self.bank.get(i) for i in ids]
        with open(p, "w", encoding="utf-8") as f:
            f.write(fill(load_template(self.gen_panel.e_tpl[0].text() or None), MODE="loigiai",
                         NOI_DUNG=questions_to_tex(qs), TEN_DE="CÂU HỎI TỪ KHO", MA_DE="—"))
        if not open_in_texstudio(p, custom=self.settings.value("pdf/texstudio", "")):
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        self.statusBar().showMessage(f"Đã mở {len(qs)} câu ({p}). Sửa xong muốn lưu vào kho: dán lại vào hộp Sửa câu "
                                     "hoặc nhập lại file .tex.", 15000)

    def edit_similar(self, idx):
        db_id = self.sim.item(idx.row(), 0).data(Qt.ItemDataRole.UserRole)
        if EditDialog(self, db_id).exec():
            self.refresh()

    # ---------------------------------------------------------- kho: sao lưu / gộp / tách / Map ID
    def backup_bank(self):
        from datetime import datetime
        base = os.path.splitext(os.path.basename(self.bank.path))[0]
        name = f"{base}_saoluu_{datetime.now():%Y%m%d_%H%M}.db"
        from ..appdirs import path as app_path
        p, _ = QFileDialog.getSaveFileName(self, "Sao lưu kho", app_path("sao_luu", name), "Kho câu hỏi (*.db)")
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

    def assign_ids(self, use_ai=False):
        ids = self.selected_ids()
        if ids:
            qs = [self.bank.get(i) for i in ids]
        else:
            qs = [q for q in self.bank.search() if not q.id_code]
            if not qs:
                QMessageBox.information(self, "Gán ID", "Hãy chọn các câu cần gán/đổi ID trong bảng "
                                        "(kho hiện không có câu nào thiếu ID).")
                return
        dlg = AssignIdDialog(self, qs, [f"Kho #{q.db_id}" for q in qs])
        if use_ai:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(200, dlg.run_gemini)
        if dlg.exec():
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
        self.show_panel(self.tools_panel)
        self.tools_panel.check_file()

    def show_stats(self):
        self.show_panel(self.stats_panel)

    # ---------------------------------------------------------- PDF
    def pdf_opts(self) -> dict:
        st = self.settings
        return {"preferred": st.value("pdf/engine", "auto"), "custom": st.value("pdf/custom", ""),
                "extest_dir": st.value("pdf/extest", ""), "runs": int(st.value("pdf/runs", 2)),
                "clean": str(st.value("pdf/clean", True)).lower() == "true",
                "open": str(st.value("pdf/open", True)).lower() == "true"}

    def engine(self, quiet=False):
        from ..pdfbuild import EngineMissing, find_engine
        o = self.pdf_opts()
        try:
            return find_engine(o["preferred"], o["custom"])
        except EngineMissing as e:
            if not quiet:
                QMessageBox.warning(self, "Chưa có LaTeX", f"{e}\n\nMenu Công cụ → Cài đặt biên dịch PDF.")
            return None

    def build_pdfs(self, paths, title="Biên dịch PDF", open_single=True):
        """Biên dịch nhiều file trong luồng nền (không treo giao diện), hiện kết quả."""
        eng = self.engine()
        if not eng or not paths:
            return []
        o = self.pdf_opts()
        dlg = QProgressDialog("Đang biên dịch…", "Huỷ", 0, len(paths), self)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        worker = BuildWorker(paths, eng, o)
        worker.progress.connect(lambda i, n, p: (dlg.setValue(i - 1), dlg.setLabelText(f"Đang biên dịch {i}/{n}: "
                                                                                       f"{os.path.basename(p)}")))
        dlg.canceled.connect(worker.requestInterruption)
        results = []
        worker.done.connect(lambda r: results.extend(r))
        worker.start()
        while worker.isRunning():
            QApplication.processEvents()
            worker.wait(50)
        QApplication.processEvents()
        dlg.close()
        if len(results) == 1 and results[0].ok and open_single and o["open"]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(results[0].pdf))
        else:
            PdfResultDialog(self, results).exec()
        return results

    def preview_pdf(self):
        from ..pdfbuild import preview_questions
        ids = self.selected_ids()
        if not ids:
            QMessageBox.information(self, "Xem PDF", "Chọn một hoặc nhiều câu trong bảng (tối đa 50).")
            return
        eng = self.engine()
        if not eng:
            return
        qs = [self.bank.get(i) for i in ids[:50]]
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            r = preview_questions(qs, mode="loigiai", engine=eng, extest_dir=self.pdf_opts()["extest_dir"],
                                  template_path=self.gen_panel.e_tpl[0].text() or None)
        finally:
            QApplication.restoreOverrideCursor()
        if r.pdf:
            QDesktopServices.openUrl(QUrl.fromLocalFile(r.pdf))
        if not r.ok:
            PdfResultDialog(self, [r]).exec()

    def compile_files(self):
        ps, _ = QFileDialog.getOpenFileNames(self, "Chọn file .tex cần biên dịch", self.settings.value("last_dir", ""),
                                             "LaTeX (*.tex)")
        if ps:
            self.build_pdfs(prepare_tex_for_pdf(ps, self.gen_panel.e_tpl[0].text() or None))

    def pdf_settings_dialog(self):
        PdfSettingsDialog(self).exec()
        self.gen_panel.c_pdf.setEnabled(bool(self.engine(quiet=True)))

    def open_review(self):
        self.show_panel(self.review_panel)

    def open_generator(self):
        self.show_panel(self.gen_panel)

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
