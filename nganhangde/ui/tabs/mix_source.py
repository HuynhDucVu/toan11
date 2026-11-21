"""Thanh nguồn câu hỏi của tab «Trộn đề» (như MyLT 2026): ⦿ Từ ngân hàng câu hỏi / ○ Từ Files (chọn một hoặc nhiều file
nguồn chứa câu hỏi), nút «Mở ngân hàng», «Nhập câu hỏi». Chế độ «Từ Files» nạp câu từ các file vào một kho tạm trong bộ nhớ;
mọi trang con (Tạo đề theo ID, Tự chọn, Tương tự, Tuỳ chọn đề…) lấy câu từ kho tạm đó thay vì kho chính."""
from __future__ import annotations

import os

from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QRadioButton, QVBoxLayout,
                               QWidget)

from ...db import Bank
from ...parser import parse_file


class MixSourceBar(QWidget):
    def __init__(self, win):
        super().__init__()
        self.win = win
        win.mix_source = "bank"
        win.file_pool = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.r_bank = QRadioButton("Từ ngân hàng câu hỏi")
        self.r_files = QRadioButton("Từ Files. Chọn một hoặc nhiều file nguồn chứa câu hỏi")
        self.r_bank.setChecked(True)
        row.addWidget(self.r_bank)
        row.addWidget(self.r_files)
        row.addStretch()
        lay.addLayout(row)
        row = QHBoxLayout()
        self.b_open = QPushButton("Mở ngân hàng")
        self.b_import = QPushButton("Nhập câu hỏi")
        self.b_files = QPushButton("Chọn files…")
        self.l_info = QLabel("")
        for w in (self.b_open, self.b_import, self.b_files, self.l_info):
            row.addWidget(w)
        row.addStretch()
        lay.addLayout(row)
        self.r_bank.toggled.connect(self._mode)
        self.b_open.clicked.connect(win.choose_bank)
        self.b_import.clicked.connect(win.import_files)
        self.b_files.clicked.connect(self.choose_files)
        self._mode()

    def info_text(self) -> str:
        w = self.win
        if w.mix_source == "files":
            n = w.file_pool.count() if w.file_pool is not None else 0
            return f"Nguồn: {n:,} câu từ file"
        return f"Nguồn: kho {w.bank.count():,} câu" if w.bank else ""

    def _mode(self, *_):
        files = self.r_files.isChecked()
        self.win.mix_source = "files" if files else "bank"
        self.b_files.setEnabled(files)
        self.b_open.setEnabled(not files)
        self.b_import.setEnabled(not files)
        if files and self.win.file_pool is None:
            self.choose_files()
        self.refresh()

    def refresh(self):
        self.l_info.setText(self.info_text())
        w = self.win
        for name in ("idgrid_panel", "pick_panel"):
            p = getattr(w, name, None)
            if p is not None and hasattr(p, "reload"):
                try:
                    p.reload()
                except Exception:  # noqa: BLE001 – panel chưa dựng xong
                    pass
        gp = getattr(w, "gen_panel", None)
        if gp is not None:
            gp.update_avail()

    def choose_files(self):
        ps, _ = QFileDialog.getOpenFileNames(self.win, "Chọn một hoặc nhiều file nguồn chứa câu hỏi",
                                             self.win.settings.value("last_dir", ""), "LaTeX (*.tex);;Tất cả (*.*)")
        if ps:
            self.load_files(ps)
        elif self.win.file_pool is None:
            self.r_bank.setChecked(True)               # chưa chọn file nào: quay lại ngân hàng

    def load_files(self, paths: list[str]) -> int:
        """Nạp các file vào kho tạm (bộ nhớ); trả về số câu nạp được."""
        pool = Bank(":memory:")
        added, errs = 0, []
        for p in paths:
            try:
                for q in parse_file(p):
                    if pool.add(q, p):
                        added += 1
            except Exception as e:  # noqa: BLE001
                errs.append(f"{os.path.basename(p)}: {e}")
        if self.win.file_pool is not None:
            self.win.file_pool.close()
        self.win.file_pool = pool
        self.win.mix_files = list(paths)
        if paths:
            self.win.settings.setValue("last_dir", os.path.dirname(paths[0]))
            fm = getattr(self.win, "filemix_panel", None)
            if fm is not None and not fm.e_file.text().strip():
                fm.e_file.setText(" ; ".join(paths))               # «Tạo đề theo file» dùng luôn các file vừa chọn
        if errs:
            QMessageBox.warning(self.win, "Nạp file", "Một số file lỗi:\n" + "\n".join(errs))
        self.refresh()
        return added
