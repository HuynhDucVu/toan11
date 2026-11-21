"""Hộp thoại sửa bảng giải nghĩa ID (Map ID)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPlainTextEdit, QPushButton,
    QVBoxLayout)
from ...idmap import dash_duplicates, parse_map_text, save_map, to_dash_text

if TYPE_CHECKING:
    from ..main_window import MainWindow


class IdMapDialog(QDialog):
    """Sửa bảng giải nghĩa ID theo định dạng Map ID phân cấp bằng gạch ngang (dùng chung với file Map_ID.tex)."""

    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Giải nghĩa ID (Map ID)")
        self.resize(820, 640)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Định dạng phân cấp: <code>-[0] Lớp 10</code>, <code>----[D] Môn</code>, "
                             "<code>-------[1] Chương</code>, <code>----------[1] Bài</code>, "
                             "<code>-------------[1] Dạng</code> (1/4/7/10/13 gạch). Dòng bắt đầu bằng % là chú thích.<br>"
                             "Có thể nạp thẳng file <b>Map_ID.tex</b> đang dùng với các phần mềm khác."))
        self.ed = QPlainTextEdit()
        self.ed.setFont(QFont("Consolas", 11))
        self.ed.setPlainText(to_dash_text(win.bank.idmap()))
        lay.addWidget(self.ed)
        self.info = QLabel()
        lay.addWidget(self.info)
        self.ed.textChanged.connect(self.update_info)
        row = QHBoxLayout()
        for text, fn in (("Nạp file Map ID (.tex/.txt)…", self.load), ("Nạp danh mục có sẵn (Toán 6–12)", self.load_builtin),
                         ("Xuất file Map ID…", self.export), ("Xuất trang tra cứu HTML…", self.export_html)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        quick = QPushButton("Map ID trong thư mục map_id ▾")
        quick.setToolTip("Chuyển nhanh giữa các Map ID (chép các file Map ID của MyLT vào thư mục map_id)")
        quick.clicked.connect(lambda: self.quick_menu(quick))
        row.addWidget(quick)
        row.addStretch()
        ok = QPushButton("Lưu")
        ok.setObjectName("primary")
        ok.clicked.connect(self.save)
        cancel = QPushButton("Huỷ")
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)
        self.update_info()

    def update_info(self):
        m = parse_map_text(self.ed.toPlainText())
        n = {lv: 0 for lv in range(1, 6)}
        for k in m:
            if not k.startswith("#"):
                n[len(k.split("-")[0]) + ("-" in k)] += 1
        dups = dash_duplicates(self.ed.toPlainText())
        txt = (f"{n[1]} lớp · {n[2]} môn · {n[3]} chương · {n[4]} bài · {n[5]} dạng")
        if dups:
            txt += (f" — <span style='color:#c00000'>{len(dups)} mã bị khai báo trùng (giữ mục đầu): "
                    + "; ".join(f"{k} «{a}» / «{b}»" for k, a, b in dups[:5]) + "</span>")
        self.info.setText(txt)

    def load(self):
        p, _ = QFileDialog.getOpenFileName(self, "Chọn file Map ID", "",
                                           "Map ID (*.tex *.txt);;Tất cả (*.*)")
        if not p:
            return
        with open(p, encoding="utf-8-sig") as f:
            text = f.read()
        new = parse_map_text(text)
        if not new:
            QMessageBox.warning(self, "Map ID", "Không đọc được mục nào trong file này.")
            return
        cur = parse_map_text(self.ed.toPlainText())
        if cur and QMessageBox.question(self, "Map ID", f"File có {len(new)} mục. Thay toàn bộ bảng hiện tại?\n"
                                        "(Chọn No để gộp thêm vào bảng hiện tại)") != QMessageBox.StandardButton.Yes:
            cur.update(new)
            new = cur
        self.ed.setPlainText(to_dash_text(new))
        dups = dash_duplicates(text)
        if dups:
            QMessageBox.warning(self, "Map ID có mã trùng", "Các mã sau được khai báo 2 lần, phần mềm giữ mục đầu:\n\n"
                                + "\n".join(f"{k}: «{a}» / «{b}»" for k, a, b in dups))

    def quick_menu(self, btn):
        import glob
        import os
        from PySide6.QtWidgets import QMenu
        from ...appdirs import path as app_path
        from ...idmap import load_map
        mn = QMenu(btn)
        files = sorted(glob.glob(app_path("map_id", "*.tex")) + glob.glob(app_path("map_id", "*.txt")))
        for f in files:
            mn.addAction(os.path.basename(f), lambda f=f: self.ed.setPlainText(to_dash_text(load_map(f))))
        if not files:
            mn.addAction("(thư mục map_id trống)").setEnabled(False)
        mn.addSeparator()
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        mn.addAction("Mở thư mục map_id", lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(app_path("map_id"))))
        mn.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def load_builtin(self):
        from ...idmap import builtin_map
        cur = parse_map_text(self.ed.toPlainText())
        m = builtin_map()
        if cur and QMessageBox.question(self, "Map ID", f"Danh mục có sẵn có {len(m)} mục. Thay toàn bộ bảng hiện tại?\n"
                                        "(Chọn No để gộp thêm)") != QMessageBox.StandardButton.Yes:
            cur.update({k: v for k, v in m.items() if k not in cur})
            m = cur
        self.ed.setPlainText(to_dash_text(m))

    def export_html(self):
        from ...idmap import to_html
        p, _ = QFileDialog.getSaveFileName(self, "Xuất trang tra cứu ID", "tra_cuu_ID.html", "HTML (*.html)")
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write(to_html(parse_map_text(self.ed.toPlainText())))
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def export(self):
        p, _ = QFileDialog.getSaveFileName(self, "Xuất file Map ID", "Map_ID.tex", "Map ID (*.tex);;Văn bản (*.txt)")
        if p:
            save_map(parse_map_text(self.ed.toPlainText()), p)

    def save(self):
        self.win.bank.set_idmap(parse_map_text(self.ed.toPlainText()), replace=True)
        self.accept()
