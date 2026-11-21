"""Hộp thoại PDF → LaTeX: chọn cách đọc (chữ trong PDF / Mathpix / AI), nguồn; chạy nền có tiến trình."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QLabel, QLineEdit,
                               QMessageBox, QProgressDialog)
from ... import pdf2tex
from ...appdirs import folder
from ..workers import TaskWorker


class Pdf2TexDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win, self.st = win, win.settings
        self.setWindowTitle("PDF → LaTeX (ex_test)")
        f = QFormLayout(self)
        self.cb = QComboBox()
        for t, d in (("Chữ trong PDF – miễn phí, không cần mạng (đề ít công thức)", "text"),
                     ("Mathpix – chữ + công thức, cả bản chụp (cần khoá Mathpix)", "mathpix"),
                     ("AI Gemini/Claude – hiểu cả hình, bản chụp (cần khoá AI)", "ai")):
            self.cb.addItem(t, d)
        self.cb.setCurrentIndex(max(0, self.cb.findData(self.st.value("p2t/engine", "text"))))
        self.e_tag = QLineEdit(str(self.st.value("p2t/tag", "")))
        self.e_tag.setPlaceholderText("nguồn gắn vào mọi câu, vd Đề HK1 THPT A (có thể để trống)")
        f.addRow(QLabel("Nhận dạng «PHẦN I/II/III», «Câu N», phương án A–D, ý a–d, bảng đáp án cuối đề. "
                        "Câu chưa có đáp án được ghi chú để điền sau."))
        f.addRow("Cách đọc", self.cb)
        f.addRow("Nguồn", self.e_tag)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def _ok(self):
        self.st.setValue("p2t/engine", self.cb.currentData())
        self.st.setValue("p2t/tag", self.e_tag.text().strip())
        self.accept()


def convert_pdf_files(win, paths=None) -> list[str]:
    """Hỏi file + cách đọc, chuyển từng PDF, ghi <tên>_tuPDF.tex vào DATA\\PDF2TEX. Trả về các file .tex tạo được."""
    if paths is None:
        paths, _ = QFileDialog.getOpenFileNames(win, "Chọn file PDF đề thi", folder("pdf2tex"), "PDF (*.pdf)")
    if not paths:
        return []
    dlg = Pdf2TexDialog(win)
    if not dlg.exec():
        return []
    engine, tag = dlg.cb.currentData(), dlg.e_tag.text().strip()
    client = None
    if engine == "ai":
        from .ai_settings import ensure_client
        client = ensure_client(win)
        if client is None:
            return []
    elif engine == "mathpix" and not (str(win.settings.value("mathpix/app_id", "")) and
                                      str(win.settings.value("mathpix/app_key", ""))):
        win.appearance()
        if not (str(win.settings.value("mathpix/app_id", "")) and str(win.settings.value("mathpix/app_key", ""))):
            return []
    outs, lines = [], []
    for p in paths:
        def job(progress, should_stop, p=p):
            return pdf2tex.pdf_to_tex(p, engine, tag=tag, settings=win.settings, client=client,
                                      progress=progress, should_stop=should_stop)
        w = TaskWorker(job, with_progress=True)
        pd = QProgressDialog(f"Đang đọc {os.path.basename(p)}…", "Dừng", 0, 0, win)
        pd.setWindowModality(Qt.WindowModality.WindowModal)
        pd.setMinimumDuration(0)
        w.progress.connect(lambda i, n: (pd.setMaximum(n), pd.setValue(i)))
        pd.canceled.connect(w.requestInterruption)
        w.finished.connect(pd.close)
        w.start()
        pd.exec()
        w.wait()
        if w.error:
            lines.append(f"<p style='color:#c00000'>✘ {os.path.basename(p)}: {w.error}</p>")
            continue
        tex, notes = w.result
        lines.extend(f"<p style='color:#b36b00'>{os.path.basename(p)}: {n}</p>" for n in notes)
        if not tex.strip():
            continue
        out = os.path.join(folder("pdf2tex"), os.path.splitext(os.path.basename(p))[0] + "_tuPDF.tex")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(tex)
        outs.append(out)
        lines.append(f"<p>{os.path.basename(p)} → <b>{out}</b></p>")
    box = QMessageBox(QMessageBox.Icon.Information, "PDF → LaTeX", "Kết quả", parent=win)
    box.setText("".join(lines) or "Không có kết quả.")
    btn = box.addButton("Nhập vào kho (3 bước)…", QMessageBox.ButtonRole.AcceptRole) if outs else None
    box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if btn is not None and box.clickedButton() is btn:
        from .import_wizard import ImportWizard
        ImportWizard(win, outs).exec()
    return outs
