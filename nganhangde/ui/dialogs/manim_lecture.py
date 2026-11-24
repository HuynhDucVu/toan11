"""Hộp thoại «Bài giảng Manim»: 1) AI thiết kế, 2) xuất code, 3) xuất main, 4) biên dịch, 5) chạy video, 6) dung lượng."""
from __future__ import annotations

import os

from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QTextBrowser, QVBoxLayout)

from ... import manim_lecture as ml
from ..workers import TaskWorker


class ManimLectureDialog(QDialog):
    def __init__(self, win, source: str = ""):
        super().__init__(win)
        from ...appdirs import folder
        self.win, self.st = win, win.settings
        self.setWindowTitle("Bài giảng Manim (video) từ file")
        self.resize(820, 620)
        self.design, self.info, self.videos = None, None, []
        self.source = source
        self.out = os.path.join(folder("bai_giang"), os.path.splitext(os.path.basename(source or "bai_giang"))[0])
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.l_src = QLabel(f"File nguồn: {source or '(chưa chọn)'}")
        self.l_src.setWordWrap(True)
        b = QPushButton("Chọn file…")
        b.clicked.connect(self.pick)
        row.addWidget(self.l_src, 1)
        row.addWidget(b)
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Chất lượng video"))
        self.cb_q = QComboBox()
        for t, q in ml.QUALITIES.items():
            self.cb_q.addItem(t, q)
        self.cb_q.setCurrentIndex(0)
        row.addWidget(self.cb_q)
        row.addStretch()
        lay.addLayout(row)
        row = QHBoxLayout()
        for text, fn in (("① AI thiết kế bài giảng", self.step1), ("② Xuất code", self.step2),
                         ("③ Xuất main", self.step3), ("④ Biên dịch", self.step4),
                         ("⑤ Chạy video", self.step5), ("⑥ Dung lượng", self.step6)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self.log = QTextBrowser()
        lay.addWidget(self.log, 1)
        self.say("Các bước theo thứ tự ①→⑥. Bước ① cần khoá AI (Công cụ → Cài đặt AI). "
                 "Bước ④ cần cài manim, LaTeX và ffmpeg trên máy (lệnh: <code>pip install manim</code>).")

    def say(self, html: str):
        self.log.append(html)

    def pick(self):
        p, _ = QFileDialog.getOpenFileName(self, "File nguồn", self.st.value("last_dir", ""),
                                           "Tài liệu (*.tex *.docx *.txt);;Mọi file (*.*)")
        if p:
            self.source = p
            self.l_src.setText(f"File nguồn: {p}")
            from ...appdirs import folder
            self.out = os.path.join(folder("bai_giang"), os.path.splitext(os.path.basename(p))[0])
            self.st.setValue("last_dir", os.path.dirname(p))

    def step1(self):
        if not self.source:
            QMessageBox.information(self, "Bài giảng", "Chọn file nguồn trước.")
            return
        from ..dialogs.ai_settings import ensure_client
        client = ensure_client(self.win)
        if client is None:
            return
        src = ml.read_source(self.source)

        def job():                      # TaskWorker không truyền progress/should_stop khi with_progress=False
            return ml.design_lecture(client, src)
        w = TaskWorker(job)
        self.say("Đang để AI thiết kế bài giảng…")
        w.start()
        while not w.isFinished():
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            w.wait(50)
        if w.error:
            self.say(f"<span style='color:#c00000'>AI lỗi: {w.error}</span>")
            return
        self.design = w.result
        lines = [f"<b>{self.design['title']}</b> – {len(self.design['scenes'])} cảnh:"]
        lines += [f"{i}. {s['title']} ({len(s['blocks'])} khối)" for i, s in enumerate(self.design["scenes"], 1)]
        self.say("<br>".join(lines))

    def step2(self):
        if not self.design:
            self.say("<span style='color:#c00000'>Chưa có bản thiết kế – làm bước ① trước.</span>")
            return
        info = ml.write_code(self.design, self.out)
        self.info = info
        self.say(f"Đã xuất code: <code>{info['code']}</code> ({len(info['scenes'])} cảnh).")

    def step3(self):
        if not self.info:
            self.step2()
            if not self.info:
                return
        m = ml.write_main(self.out, self.info["scenes"], self.cb_q.currentData())
        self.say(f"Đã xuất main: <code>{m['main']}</code> (chất lượng: {self.cb_q.currentText()}).")

    def step4(self):
        if not self.info:
            self.step2()
            if not self.info:
                return
        self.step3()
        miss = ml.missing_tools()
        if miss:
            self.say("<span style='color:#c00000'>Còn thiếu để biên dịch:<br>• " + "<br>• ".join(miss) + "</span>")
            return
        self.say("Đang biên dịch – có thể lâu với bài dài…")
        from PySide6.QtWidgets import QApplication
        ok, videos, msg = ml.render(self.out, self.info["scenes"], self.cb_q.currentData())
        QApplication.processEvents()
        self.videos = videos
        colour = "#2e7d32" if ok else "#c00000"
        self.say(f"<span style='color:{colour}'>{msg.replace(chr(10), '<br>')}</span>")

    def step5(self):
        if not self.videos:
            self.say("Chưa có video – làm bước ④ trước.")
            return
        for v in self.videos:
            QDesktopServices.openUrl(QUrl.fromLocalFile(v))
        self.say(f"Mở {len(self.videos)} video trong trình xem mặc định.")

    def step6(self):
        if not self.videos:
            self.say("Chưa có video – làm bước ④ trước.")
            return
        r = ml.size_report(self.videos)
        lines = [f"• {name}: {ml._human(sz)}" for name, sz in r["files"].items()]
        lines.append(f"<b>Tổng {len(r['files'])} cảnh: {r['human']}</b>")
        lines.append(f"Trung bình {ml._human(r['avg'])}/cảnh. Ước tính cả đề có N cảnh ≈ N × {ml._human(r['avg'])}.")
        self.say("<br>".join(lines))
