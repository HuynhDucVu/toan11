"""Hộp «Tuỳ chọn Word → TeX» (như MyLT) và hàm chuyển file Word theo các tuỳ chọn đó."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QPlainTextEdit,
    QVBoxLayout)

from ...docxnative import DocxOptions

if TYPE_CHECKING:
    from ..main_window import MainWindow

KEYS = (("tables", "Chuyển bảng (thành tabular)", True), ("images", "Chuyển hình (xuất ảnh ra thư mục và chèn vào câu)", True),
        ("theory", "Chuyên đề / lý thuyết (giữ nguyên văn bản, không tách câu)", False),
        ("chem", "Môn Hoá (chỉ số trên/dưới trong chữ thường)", False),
        ("word", "Thử dùng Word + MathType tự đổi công thức MathType (thử nghiệm, hay báo lỗi – khuyên đổi tay, xem dưới)", False),
        ("show_word", "Hiện cửa sổ Word khi chuyển", False))


class Word2TexDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.st = win.settings
        self.setWindowTitle("Tuỳ chọn Word → TeX")
        self.resize(560, 520)
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Phần mềm đọc file Word trực tiếp (không cần pandoc): công thức Word, bảng, hình; đáp án đúng "
                             "nhận theo chữ <b>gạch chân hoặc tô màu</b>."))
        f = QFormLayout()
        lay.addLayout(f)
        self.boxes = {}
        for k, text, d in KEYS:
            c = QCheckBox(text)
            v = self.st.value(f"w2t/{k}", d)
            c.setChecked(v if isinstance(v, bool) else str(v).lower() == "true")
            self.boxes[k] = c
            lay.addWidget(c)
        from ... import wordcom
        if not wordcom.available():
            self.boxes["word"].setEnabled(False)
            self.boxes["word"].setChecked(False)
            self.boxes["show_word"].setEnabled(False)
        self.cb_mode = QComboBox()
        self.cb_mode.addItem("Convert Equations (MathType → công thức Word)", "convert")
        self.cb_mode.addItem("Toggle TeX (MathType → mã LaTeX trong văn bản)", "toggle_tex")
        self.cb_mode.setCurrentIndex(max(0, self.cb_mode.findData(self.st.value("w2t/mode", "convert"))))
        f.addRow("Cách đổi MathType", self.cb_mode)
        f.addRow(QLabel("<i>Công thức dạng MathType (đối tượng) cần đổi sang mã trước: trong Word chọn thẻ MathType → "
                        "Convert Equations… → «Equations to TeX» cho cả tài liệu, lưu file .docx rồi chuyển ở đây "
                        "(không tick ô Word + MathType). Công thức Word thường (Alt+=) đọc được luôn.</i>"))
        lay.addWidget(QLabel("<b>Thay thế cá nhân</b> – mỗi dòng một cặp <code>cũ = mới</code> (vd <code>Δ = \\Delta</code>):"))
        self.e_rep = QPlainTextEdit(str(self.st.value("w2t/rep", "")))
        self.e_rep.setMaximumHeight(110)
        lay.addWidget(self.e_rep)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _ok(self):
        for k, c in self.boxes.items():
            self.st.setValue(f"w2t/{k}", c.isChecked())
        self.st.setValue("w2t/mode", self.cb_mode.currentData())
        self.st.setValue("w2t/rep", self.e_rep.toPlainText())
        self.accept()

    def replacements(self):
        out = []
        for ln in self.e_rep.toPlainText().splitlines():
            if "=" in ln:
                a, b = ln.split("=", 1)
                if a.strip():
                    out.append((a.strip(), b.strip()))
        return out

    def options(self) -> DocxOptions:
        b = self.boxes
        return DocxOptions(tables=b["tables"].isChecked(), images=b["images"].isChecked(), chem=b["chem"].isChecked(),
                           theory=b["theory"].isChecked(), replacements=self.replacements())


def output_paths(docx_path: str) -> tuple[str, str]:
    """(file .tex, thư mục hình) – đều nằm trong DATA\\WORD2EXTEST: <tên>_tuWord.tex và <tên>_tuWord_hinh\\.
    (hình để cạnh file .tex nên \\includegraphics biên dịch được ngay)"""
    from ...appdirs import folder
    d = folder("word2extest")
    os.makedirs(d, exist_ok=True)
    stem = os.path.splitext(os.path.basename(docx_path))[0]
    return os.path.join(d, stem + "_tuWord.tex"), os.path.join(d, stem + "_tuWord_hinh")


def convert_word_file(win: MainWindow, path: str, dlg: Word2TexDialog, tag: str = "") -> tuple[str, list[str]]:
    """Một file Word → nội dung .tex theo tuỳ chọn; trả về (tex, các cảnh báo)."""
    from ... import wordcom
    from ...docxnative import docx_to_ex, triage
    notes = []
    src = path
    rep = triage(path)
    if rep.mathtype_ole and dlg.boxes["word"].isChecked():
        ok, out, msg = wordcom.convert_mathtype(path, dlg.cb_mode.currentData(), dlg.boxes["show_word"].isChecked())
        if ok:
            src = out
            notes.append(f"Đã đổi công thức MathType qua Word ({msg}).")
        else:
            notes.append(f"Chưa đổi được MathType qua Word: {msg}")
    opts = dlg.options()
    opts.image_dir = output_paths(path)[1]
    tex, rep2 = docx_to_ex(src, opts, tag)
    notes += rep2.warnings if src == path else []
    return tex, notes
