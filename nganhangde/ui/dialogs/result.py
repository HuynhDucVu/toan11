"""Hộp thoại kết quả tạo đề (phân bố đáp án, tỉ lệ trùng)."""
from __future__ import annotations

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextBrowser, QVBoxLayout
from ...generator import answer_distribution, overlap_report


def versions_report_html(vs, out_dir) -> str:
    """Báo cáo sau khi trộn: phân bố đáp án A/B/C/D từng mã đề và tỉ lệ trùng giữa các mã."""
    rows = "".join("<tr><td><b>{}</b></td>{}<td>{}</td></tr>".format(
        v.code, "".join(f"<td align=center>{n}</td>" for n in answer_distribution(v).values()),
        sum(len(v.sections.get(s) or []) for s in v.sections)) for v in vs)
    html = (f"<p>Đã tạo <b>{len(vs)}</b> mã đề trong thư mục:<br><code>{out_dir}</code></p>"
            "<p><b>Phân bố đáp án phần trắc nghiệm</b></p>"
            "<table border=1 cellspacing=0 cellpadding=4><tr><th>Mã đề</th><th>A</th><th>B</th><th>C</th><th>D</th>"
            "<th>Tổng số câu</th></tr>" + rows + "</table>")
    ov = overlap_report(vs)
    if ov:
        mx = max(r for _, _, r in ov)
        html += (f"<p><b>Tỉ lệ câu trùng giữa các mã đề:</b> cao nhất {mx:.0%}"
                 + (" (cùng bộ câu, chỉ hoán vị)" if mx == 1 else "") + "</p>")
    html += ("<p>File: <code>de_*.tex</code> (đề), <code>loigiai_*.tex</code> (lời giải + bảng đáp án), "
             "<code>dap_an.csv</code>, <code>dap_an_bang.csv</code> (mỗi mã đề một dòng).</p>")
    return html


class ResultDialog(QDialog):
    def __init__(self, parent, vs, out_dir, extra=""):
        super().__init__(parent)
        self.setWindowTitle("Kết quả tạo đề")
        self.resize(620, 480)
        lay = QVBoxLayout(self)
        tb = QTextBrowser()
        tb.setHtml(versions_report_html(vs, out_dir) + extra)
        lay.addWidget(tb)
        row = QHBoxLayout()
        row.addStretch()
        b = QPushButton("Mở thư mục kết quả")
        b.setObjectName("primary")
        b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(out_dir))))
        t = QPushButton("Mở đề đầu tiên trong TeXstudio")

        def open_first():
            from ...editor import open_in_texstudio
            f = os.path.join(out_dir, f"de_{vs[0].code}.tex") if vs else ""
            st = getattr(parent, "st", None) or getattr(getattr(parent, "win", None), "settings", None)
            if f and not open_in_texstudio(f, custom=st.value("pdf/texstudio", "") if st else ""):
                QDesktopServices.openUrl(QUrl.fromLocalFile(f))
        t.clicked.connect(open_first)
        row.addWidget(t)
        c = QPushButton("Đóng")
        c.clicked.connect(self.accept)
        row.addWidget(b)
        row.addWidget(c)
        lay.addLayout(row)
