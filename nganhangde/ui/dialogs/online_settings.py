"""Cài đặt bài online / Blogger: màu sắc và Google Form nhận kết quả học sinh."""
from __future__ import annotations

import json

from PySide6.QtWidgets import (QColorDialog, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget)

from ...online import GFORM_FIELDS, parse_prefill_link

COLORS = [("khung", "Màu khung, tiêu đề", "#1f4e79"), ("nen", "Màu nền trang", "#f5f7fa"), ("the", "Màu nền câu", "#ffffff"),
          ("chu_cau", "Màu chữ «Câu 1.»", ""), ("chu_loigiai", "Màu chữ lời giải", ""), ("dung", "Màu đúng", "#0b7a0b"),
          ("sai", "Màu sai", "#c00000")]


def load(settings) -> tuple[dict, dict]:
    def j(k):
        try:
            return json.loads(settings.value(k, "") or "{}")
        except ValueError:
            return {}
    return j("online/style"), j("online/gform")


class OnlineSettingsDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Cài đặt bài online / Blogger")
        self.resize(640, 640)
        style, gform = load(win.settings)
        lay = QVBoxLayout(self)
        g = QGroupBox("Màu sắc (để trống = mặc định)")
        f = QFormLayout(g)
        self.colors = {}
        for k, name, default in COLORS:
            e = QLineEdit(style.get(k, ""))
            e.setPlaceholderText(default or "mặc định")
            b = QPushButton("Chọn…")
            b.clicked.connect(lambda _=False, e=e: self._pick(e))
            row = QWidget()
            h = QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(e)
            h.addWidget(b)
            f.addRow(name, row)
            self.colors[k] = e
        lay.addWidget(g)
        g = QGroupBox("Gửi kết quả về Google Form (xem kết quả trong Google Trang tính)")
        f = QFormLayout(g)
        f.addRow(QLabel("1) Tạo Google Form có các câu hỏi dạng «Trả lời ngắn»: Tên đề, Họ tên, Lớp, Số báo danh, Điểm, "
                        "Bài làm, Thời gian, Mã đề (không cần đủ).<br>2) Bấm ⋮ → <b>Lấy đường liên kết điền sẵn</b>, gõ vào "
                        "mỗi ô đúng từ khoá: <code>TENDE, TEN, LOP, SBD, DIEM, BAILAM, THOIGIAN, MADE</code> → Lấy liên kết → "
                        "Sao chép.<br>3) Dán liên kết vào ô dưới, bấm <b>Đọc link</b>."))
        self.e_link = QLineEdit()
        self.e_link.setPlaceholderText("https://docs.google.com/forms/d/e/…/viewform?usp=pp_url&entry.…=TEN…")
        b = QPushButton("Đọc link")
        b.clicked.connect(self.read_link)
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.e_link)
        h.addWidget(b)
        f.addRow("Link điền sẵn", row)
        self.e_id = QLineEdit(gform.get("id", ""))
        f.addRow("Mã form", self.e_id)
        self.entries = {}
        for k, _kw, name in GFORM_FIELDS:
            e = QLineEdit(str((gform.get("entries") or {}).get(k, "")))
            e.setPlaceholderText("số entry (vd 865367135)")
            f.addRow(name, e)
            self.entries[k] = e
        lay.addWidget(g)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Xoá Google Form")
        b.clicked.connect(lambda: [x.clear() for x in [self.e_id, *self.entries.values()]])
        row.addWidget(b)
        b = QPushButton("Lưu")
        b.setObjectName("primary")
        b.clicked.connect(self.save)
        row.addWidget(b)
        lay.addLayout(row)

    def _pick(self, e):
        c = QColorDialog.getColor(parent=self)
        if c.isValid():
            e.setText(c.name())

    def read_link(self):
        try:
            g = parse_prefill_link(self.e_link.text())
        except ValueError as ex:
            QMessageBox.warning(self, "Google Form", str(ex))
            return
        self.e_id.setText(g["id"])
        for k, e in self.entries.items():
            e.setText(g["entries"].get(k, ""))
        QMessageBox.information(self, "Google Form", f"Đã đọc {len(g['entries'])} trường. Bấm Lưu.")

    def save(self):
        st = self.win.settings
        st.setValue("online/style", json.dumps({k: e.text().strip() for k, e in self.colors.items() if e.text().strip()}))
        gid = self.e_id.text().strip()
        ent = {k: e.text().strip() for k, e in self.entries.items() if e.text().strip().isdigit()}
        st.setValue("online/gform", json.dumps({"id": gid, "entries": ent} if gid and ent else {}))
        self.accept()
