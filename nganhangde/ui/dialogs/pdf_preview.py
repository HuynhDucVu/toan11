"""Xem PDF ngay trong app (pypdfium2 vẽ từng trang thành ảnh) – không cần QtPdf."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSpinBox, QVBoxLayout)


def render_page(path: str, index: int, scale: float = 1.4) -> QImage | None:
    from ...pdfrender import render_file
    return render_file(path, index, scale)


def page_count(path: str) -> int:
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    try:
        return len(doc)
    finally:
        doc.close()


class PdfPreviewDialog(QDialog):
    def __init__(self, parent, path: str):
        super().__init__(parent)
        self.path, self.page, self.scale = path, 0, 1.4
        self.n = page_count(path)
        self.setWindowTitle("Xem PDF – " + os.path.basename(path))
        self.resize(900, 760)
        lay = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.b_prev, self.b_next = QPushButton("◀"), QPushButton("▶")
        self.sp = QSpinBox()
        self.sp.setRange(1, max(self.n, 1))
        self.b_in, self.b_out = QPushButton("＋"), QPushButton("－")
        self.b_ext = QPushButton("Mở bằng trình xem ngoài")
        for w in (self.b_prev, self.sp, QLabel(f"/ {self.n}"), self.b_next, self.b_out, self.b_in):
            bar.addWidget(w)
        bar.addStretch()
        bar.addWidget(self.b_ext)
        lay.addLayout(bar)
        self.lb = QLabel()
        self.lb.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        sc = QScrollArea()
        sc.setWidget(self.lb)
        sc.setWidgetResizable(True)
        lay.addWidget(sc)
        self.b_prev.clicked.connect(lambda: self.go(self.page - 1))
        self.b_next.clicked.connect(lambda: self.go(self.page + 1))
        self.sp.valueChanged.connect(lambda v: self.go(v - 1))
        self.b_in.clicked.connect(lambda: self.zoom(1.25))
        self.b_out.clicked.connect(lambda: self.zoom(0.8))
        self.b_ext.clicked.connect(self.ext)
        self.show_page()

    def go(self, i):
        if 0 <= i < self.n and i != self.page:
            self.page = i
            self.show_page()

    def zoom(self, f):
        self.scale = min(4.0, max(0.5, self.scale * f))
        self.show_page()

    def show_page(self):
        self.sp.blockSignals(True)
        self.sp.setValue(self.page + 1)
        self.sp.blockSignals(False)
        img = render_page(self.path, self.page, self.scale)
        self.lb.setPixmap(QPixmap.fromImage(img) if img else QPixmap())

    def ext(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.path))


_OPEN = {"dlg": None}


def show_pdf(parent, path: str):
    """Mở file PDF trong MỘT cửa sổ xem duy nhất trong phần mềm: cửa sổ cũ (nếu còn) được đóng trước."""
    old = _OPEN.get("dlg")
    if old is not None:
        try:
            old.close()
        except RuntimeError:          # cửa sổ đã bị huỷ
            pass
    dlg = PdfPreviewDialog(parent, path)
    _OPEN["dlg"] = dlg
    dlg.show()
    return dlg
