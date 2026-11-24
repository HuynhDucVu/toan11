"""Hộp thoại Tuỳ chọn chuyển Word/PDF sang TeX chuẩn MyLT 2026 v1.0.3.44."""
from __future__ import annotations
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)
from ..core.config_manager import ConfigManager


class WordPdfToTexOptionsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cfg = ConfigManager()
        self.setWindowTitle("Tuỳ chọn chuyển Word/PDF sang TeX")
        self.resize(740, 520)
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Hàng 1: Hiện Word + 4 chế độ chuyển đổi
        r1 = QHBoxLayout()
        self.chk_show_word = QCheckBox("Hiện Word")
        self.rb_conv_eq = QRadioButton("Dùng Convert Equations")
        self.rb_toggle_tex = QRadioButton("Dùng Toggle TeX")
        self.rb_mathpix = QRadioButton("Dùng Mathpix API")
        self.rb_gemini = QRadioButton("Dùng Gemini")
        self.rb_conv_eq.setChecked(True)
        for w in (self.chk_show_word, self.rb_conv_eq, self.rb_toggle_tex, self.rb_mathpix, self.rb_gemini):
            r1.addWidget(w)
        r1.addStretch()
        root.addLayout(r1)

        # Hàng 2: 5 tuỳ chọn nội dung
        r2 = QHBoxLayout()
        self.chk_img = QCheckBox("Chuyển hình")
        self.chk_table = QCheckBox("Chuyển bảng"); self.chk_table.setChecked(True)
        self.chk_ds = QCheckBox("Chuyển câu ĐS")
        self.chk_chuyende = QCheckBox("Chuyên đề")
        self.chk_hoa = QCheckBox("Môn Hoá")
        for w in (self.chk_img, self.chk_table, self.chk_ds, self.chk_chuyende, self.chk_hoa):
            r2.addWidget(w)
        r2.addStretch()
        root.addLayout(r2)

        # Hàng 3: Loại file
        r3 = QHBoxLayout()
        self.cbo_loai_file = QComboBox()
        self.cbo_loai_file.addItems(["Đề ex_test (Mặc định)", "Tài liệu chuyên đề (vd/bt)", "Đề gói dethi", "Trắc nghiệm + ĐS + TLN 2025"])
        self.cbo_loai_file.setMinimumWidth(220)
        r3.addWidget(QLabel("Loại file")); r3.addWidget(self.cbo_loai_file); r3.addStretch()
        root.addLayout(r3)

        # Nhóm: Thông tin Mathpix API
        g_mp = QGroupBox("Thông tin Mathpix API")
        rmp = QHBoxLayout(g_mp)
        self.ed_mp_id = QLineEdit(); self.ed_mp_id.setEchoMode(QLineEdit.Password); self.ed_mp_id.setPlaceholderText("App ID...")
        self.ed_mp_key = QLineEdit(); self.ed_mp_key.setEchoMode(QLineEdit.Password); self.ed_mp_key.setPlaceholderText("App Key...")
        b_mp_hd = QPushButton("HDSD"); b_mp_hd.clicked.connect(
            lambda: QMessageBox.information(self, "HDSD Mathpix API", "Đăng ký tài khoản tại accounts.mathpix.com để lấy App ID và App Key, nhập vào 2 ô rồi bấm 'Lưu'.")
        )
        b_mp_save = QPushButton("Lưu"); b_mp_save.clicked.connect(self._save_mathpix)
        for w in (QLabel("ID"), self.ed_mp_id, QLabel("Key"), self.ed_mp_key, b_mp_hd, b_mp_save):
            rmp.addWidget(w, 1 if w in (self.ed_mp_id, self.ed_mp_key) else 0)
        root.addWidget(g_mp)

        # Nhóm: Thông tin Gemini AI
        g_gem = QGroupBox("Thông tin Gemini AI")
        rgem = QHBoxLayout(g_gem)
        self.ed_gem_key = QLineEdit(); self.ed_gem_key.setEchoMode(QLineEdit.Password); self.ed_gem_key.setPlaceholderText("Gemini API Key...")
        b_gem_hd = QPushButton("HDSD"); b_gem_hd.clicked.connect(
            lambda: QMessageBox.information(self, "HDSD Gemini AI", "Lấy API Key tại aistudio.google.com/apikey, dán vào ô API rồi bấm 'Lưu'.")
        )
        b_gem_save = QPushButton("Lưu"); b_gem_save.clicked.connect(self._save_gemini)
        for w in (QLabel("API"), self.ed_gem_key, b_gem_hd, b_gem_save):
            rgem.addWidget(w, 1 if w is self.ed_gem_key else 0)
        root.addWidget(g_gem)

        # Thay thế cá nhân
        self.chk_personal_rep = QCheckBox("Thay thế cá nhân")
        root.addWidget(self.chk_personal_rep)

        r_tbl = QHBoxLayout()
        self.tbl_rep = QTableWidget(0, 3)
        self.tbl_rep.setHorizontalHeaderLabels(["STT", "Thay", "Bởi"])
        self.tbl_rep.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl_rep.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tbl_rep.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        r_tbl.addWidget(self.tbl_rep, 1)

        v_side = QVBoxLayout()
        b_q = QPushButton("?"); b_q.setFixedWidth(30); b_q.clicked.connect(
            lambda: QMessageBox.information(self, "Thay thế cá nhân", "A: Thêm dòng mới\nD: Xoá dòng đang chọn\nS: Lưu bảng thay thế vào config.ini\n\nVí dụ: Thay '\\frac' bởi '\\dfrac', thay '\\vec' bởi '\\overrightarrow'.")
        )
        b_a = QPushButton("A"); b_a.setFixedWidth(30); b_a.setToolTip("Thêm dòng"); b_a.clicked.connect(self._add_rep_row)
        b_d = QPushButton("D"); b_d.setFixedWidth(30); b_d.setToolTip("Xoá dòng"); b_d.clicked.connect(self._del_rep_row)
        b_s = QPushButton("S"); b_s.setFixedWidth(30); b_s.setToolTip("Lưu bảng thay thế"); b_s.clicked.connect(self._save_all)
        for b in (b_q, b_a, b_d, b_s):
            v_side.addWidget(b)
        v_side.addStretch()
        r_tbl.addLayout(v_side)
        root.addLayout(r_tbl, 1)

        # Thanh đáy
        bot = QHBoxLayout()
        bot.addStretch()
        b_def = QPushButton("Mặc định"); b_def.clicked.connect(self._reset_defaults)
        b_ok = QPushButton("Lưu & Đóng"); b_ok.clicked.connect(self._save_and_close)
        bot.addWidget(b_def); bot.addWidget(b_ok)
        root.addLayout(bot)

    def _add_rep_row(self, old_val: str = "", new_val: str = ""):
        r = self.tbl_rep.rowCount()
        self.tbl_rep.insertRow(r)
        it_stt = QTableWidgetItem(str(r + 1))
        it_stt.setFlags(it_stt.flags() & ~Qt.ItemIsEditable)
        self.tbl_rep.setItem(r, 0, it_stt)
        self.tbl_rep.setItem(r, 1, QTableWidgetItem(old_val))
        self.tbl_rep.setItem(r, 2, QTableWidgetItem(new_val))

    def _del_rep_row(self):
        r = self.tbl_rep.currentRow()
        if r >= 0:
            self.tbl_rep.removeRow(r)
            for i in range(self.tbl_rep.rowCount()):
                self.tbl_rep.item(i, 0).setText(str(i + 1))

    def _save_mathpix(self):
        self.cfg.set("API", "mathpix_app_id", self.ed_mp_id.text().strip())
        self.cfg.set("API", "mathpix_app_key", self.ed_mp_key.text().strip())
        self.cfg.save()
        QMessageBox.information(self, "Mathpix API", "Đã lưu thông tin Mathpix API.")

    def _save_gemini(self):
        self.cfg.set("API", "gemini_api_key", self.ed_gem_key.text().strip())
        self.cfg.save()
        QMessageBox.information(self, "Gemini AI", "Đã lưu Gemini API Key.")

    def _load_settings(self):
        self.ed_mp_id.setText(self.cfg.get("API", "mathpix_app_id", ""))
        self.ed_mp_key.setText(self.cfg.get("API", "mathpix_app_key", ""))
        self.ed_gem_key.setText(self.cfg.get("API", "gemini_api_key", ""))

        mode = self.cfg.get("Word2TeX", "mode", "convert_eq")
        if mode == "toggle_tex":
            self.rb_toggle_tex.setChecked(True)
        elif mode == "mathpix":
            self.rb_mathpix.setChecked(True)
        elif mode == "gemini":
            self.rb_gemini.setChecked(True)
        else:
            self.rb_conv_eq.setChecked(True)

        self.chk_show_word.setChecked(self.cfg.get("Word2TeX", "show_word", "1") == "1")
        self.chk_img.setChecked(self.cfg.get("Word2TeX", "convert_img", "0") == "1")
        self.chk_table.setChecked(self.cfg.get("Word2TeX", "convert_table", "1") == "1")
        self.chk_ds.setChecked(self.cfg.get("Word2TeX", "convert_ds", "0") == "1")
        self.chk_chuyende.setChecked(self.cfg.get("Word2TeX", "chuyen_de", "0") == "1")
        self.chk_hoa.setChecked(self.cfg.get("Word2TeX", "mon_hoa", "0") == "1")
        self.chk_personal_rep.setChecked(self.cfg.get("Word2TeX", "use_personal_rep", "0") == "1")
        loai = self.cfg.get("Word2TeX", "loai_file", "")
        if loai:
            idx = self.cbo_loai_file.findText(loai)
            if idx >= 0:
                self.cbo_loai_file.setCurrentIndex(idx)

        raw_rules = self.cfg.get("Word2TeX", "personal_rules_json", "[]")
        try:
            rules = json.loads(raw_rules)
        except Exception:
            rules = []
        self.tbl_rep.setRowCount(0)
        for pair in rules:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                self._add_rep_row(str(pair[0]), str(pair[1]))

    def _collect_rules(self) -> list[list[str]]:
        rules: list[list[str]] = []
        for r in range(self.tbl_rep.rowCount()):
            k = self.tbl_rep.item(r, 1).text() if self.tbl_rep.item(r, 1) else ""
            v = self.tbl_rep.item(r, 2).text() if self.tbl_rep.item(r, 2) else ""
            if k:
                rules.append([k, v])
        return rules

    def _save_all(self):
        mode = "convert_eq"
        if self.rb_toggle_tex.isChecked():
            mode = "toggle_tex"
        elif self.rb_mathpix.isChecked():
            mode = "mathpix"
        elif self.rb_gemini.isChecked():
            mode = "gemini"

        self.cfg.set("Word2TeX", "mode", mode)
        self.cfg.set("Word2TeX", "show_word", "1" if self.chk_show_word.isChecked() else "0")
        self.cfg.set("Word2TeX", "convert_img", "1" if self.chk_img.isChecked() else "0")
        self.cfg.set("Word2TeX", "convert_table", "1" if self.chk_table.isChecked() else "0")
        self.cfg.set("Word2TeX", "convert_ds", "1" if self.chk_ds.isChecked() else "0")
        self.cfg.set("Word2TeX", "chuyen_de", "1" if self.chk_chuyende.isChecked() else "0")
        self.cfg.set("Word2TeX", "mon_hoa", "1" if self.chk_hoa.isChecked() else "0")
        self.cfg.set("Word2TeX", "loai_file", self.cbo_loai_file.currentText())
        self.cfg.set("Word2TeX", "use_personal_rep", "1" if self.chk_personal_rep.isChecked() else "0")
        self.cfg.set("Word2TeX", "personal_rules_json", json.dumps(self._collect_rules(), ensure_ascii=False))
        self.cfg.set("API", "mathpix_app_id", self.ed_mp_id.text().strip())
        self.cfg.set("API", "mathpix_app_key", self.ed_mp_key.text().strip())
        self.cfg.set("API", "gemini_api_key", self.ed_gem_key.text().strip())
        self.cfg.save()

    def _reset_defaults(self):
        self.rb_conv_eq.setChecked(True)
        self.chk_show_word.setChecked(True)
        self.chk_img.setChecked(False)
        self.chk_table.setChecked(True)
        self.chk_ds.setChecked(False)
        self.chk_chuyende.setChecked(False)
        self.chk_hoa.setChecked(False)
        self.chk_personal_rep.setChecked(False)
        self.cbo_loai_file.setCurrentIndex(0)

    def _save_and_close(self):
        self._save_all()
        self.accept()
