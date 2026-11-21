"""«Tuỳ chọn chuyển Word/PDF sang TeX» – bố cục giống MyLT 2026 – và luồng chuyển file Word/PDF sang ex_test.

Cách đọc (chọn một):
  * Đọc trực tiếp      – app tự đọc file Word (công thức Word, bảng, hình, đáp án gạch chân/tô màu); không cần Word;
  * Convert Equations  – Word + MathType đổi công thức MathType → công thức Word, rồi đọc;
  * Toggle TeX         – Word + MathType đổi công thức MathType → mã LaTeX trong văn bản, rồi đọc;
  * Mathpix API        – Word → PDF → Mathpix (hoặc PDF → Mathpix);
  * Gemini             – Word → PDF → Gemini (hoặc PDF → Gemini).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDialog, QGroupBox, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QRadioButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout)

from ...docxnative import DocxOptions

if TYPE_CHECKING:
    from ..main_window import MainWindow

ENGINES = (("direct", "Đọc trực tiếp"), ("convert", "Dùng Convert Equations"), ("toggle", "Dùng Toggle TeX"),
           ("mathpix", "Dùng Mathpix API"), ("gemini", "Dùng Gemini"))
CHECKS = (("images", "Chuyển hình", True), ("tables", "Chuyển bảng", True), ("ds", "Chuyển câu ĐS", True),
          ("theory", "Chuyên đề", False), ("chem", "Môn Hoá", False))

HELP_MATHPIX = ("Mathpix API (đọc công thức từ ảnh/PDF):\n1. Vào https://accounts.mathpix.com → đăng ký → mục API → "
                "tạo app.\n2. Chép «app_id» vào ô ID và «app_key» vào ô Key, bấm «Lưu».\n3. Chọn «Dùng Mathpix API», OK.\n"
                "File Word được Word xuất ra PDF rồi gửi từng trang cho Mathpix (cần Word trên máy); file PDF gửi thẳng.")
HELP_GEMINI = ("Gemini (AI của Google):\n1. Vào https://aistudio.google.com/app/apikey → tạo khoá API.\n2. Dán khoá vào ô "
               "API, bấm «Lưu».\n3. Chọn «Dùng Gemini», OK.\nFile Word được Word xuất ra PDF rồi gửi cho Gemini (cần Word "
               "trên máy); file PDF gửi thẳng. Câu hình vẽ được đánh dấu %[HINH: …] để vẽ lại.")
HELP_REPLACE = ("Thay thế cá nhân: mỗi dòng một cặp «Thay → Bởi», áp dụng cho mọi đoạn văn trước khi chuyển (vd Δ → \\Delta).\n"
                "Nút A: thêm dòng · D: xoá dòng đang chọn · S: lưu bảng (lần sau mở lại vẫn còn).")


class Word2TexDialog(QDialog):
    def __init__(self, win: MainWindow):
        super().__init__(win)
        self.win, self.st = win, win.settings
        self.setWindowTitle("Tuỳ chọn chuyển Word/PDF sang TeX")
        self.resize(760, 640)
        lay = QVBoxLayout(self)

        # --- hàng 1: Hiện Word + cách đọc
        row = QHBoxLayout()
        self.c_show = QCheckBox("Hiện Word")
        self.c_show.setChecked(str(self.st.value("w2t/show_word", False)).lower() == "true")
        self.c_show.setToolTip("Hiện cửa sổ Word khi dùng Convert Equations / Toggle TeX / xuất PDF")
        row.addWidget(self.c_show)
        self.grp = QButtonGroup(self)
        self.radios = {}
        cur = str(self.st.value("w2t/engine2", "direct"))
        for key, text in ENGINES:
            rb = QRadioButton(text)
            rb.setChecked(key == cur)
            self.grp.addButton(rb)
            self.radios[key] = rb
            row.addWidget(rb)
        if not any(r.isChecked() for r in self.radios.values()):
            self.radios["direct"].setChecked(True)
        row.addStretch()
        lay.addLayout(row)

        # --- hàng 2: tuỳ chọn + loại file
        row = QHBoxLayout()
        self.boxes = {}
        for key, text, d in CHECKS:
            c = QCheckBox(text)
            v = self.st.value(f"w2t/{key}", d)
            c.setChecked(v if isinstance(v, bool) else str(v).lower() == "true")
            self.boxes[key] = c
            row.addWidget(c)
        row.addStretch()
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(QLabel("Loại file"))
        self.cb_type = QComboBox()
        self.cb_type.addItem("Tự nhận theo đuôi file (.docx / .pdf)")
        self.cb_type.setEnabled(False)
        row.addWidget(self.cb_type, 1)
        lay.addLayout(row)

        # --- Mathpix / Gemini
        g = QGroupBox("Thông tin Mathpix API")
        h = QHBoxLayout(g)
        self.e_mid = QLineEdit(str(self.st.value("mathpix/app_id", "")))
        self.e_mkey = QLineEdit(str(self.st.value("mathpix/app_key", "")))
        self.e_mkey.setEchoMode(QLineEdit.EchoMode.Password)
        b1, b2 = QPushButton("HDSD"), QPushButton("Lưu")
        for w_ in (QLabel("ID"), self.e_mid, QLabel("Key"), self.e_mkey, b1, b2):
            h.addWidget(w_)
        b1.clicked.connect(lambda: self._help("Mathpix API", HELP_MATHPIX, "https://accounts.mathpix.com"))
        b2.clicked.connect(self.save_mathpix)
        lay.addWidget(g)
        g = QGroupBox("Thông tin Gemini AI")
        h = QHBoxLayout(g)
        self.e_gkey = QLineEdit(str(self.st.value("ai/key", "")))
        self.e_gkey.setEchoMode(QLineEdit.EchoMode.Password)
        b1, b2 = QPushButton("HDSD"), QPushButton("Lưu")
        for w_ in (QLabel("API"), self.e_gkey, b1, b2):
            h.addWidget(w_)
        b1.clicked.connect(lambda: self._help("Gemini AI", HELP_GEMINI, "https://aistudio.google.com/app/apikey"))
        b2.clicked.connect(self.save_gemini)
        lay.addWidget(g)

        # --- thay thế cá nhân
        self.g_rep = QGroupBox("Thay thế cá nhân")
        self.g_rep.setCheckable(True)
        self.g_rep.setChecked(str(self.st.value("w2t/rep_on", True)).lower() == "true")
        h = QHBoxLayout(self.g_rep)
        self.t = QTableWidget(0, 3)
        self.t.setHorizontalHeaderLabels(["STT", "Thay", "Bởi"])
        self.t.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.t.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.t.verticalHeader().setVisible(False)
        h.addWidget(self.t, 1)
        col = QVBoxLayout()
        self.load_rep(str(self.st.value("w2t/rep", "")))
        for text, fn in (("?", lambda: self._help("Thay thế cá nhân", HELP_REPLACE)), ("A", self.rep_add),
                         ("D", self.rep_del), ("S", self.rep_save)):
            b = QPushButton(text)
            b.setFixedWidth(36)
            b.clicked.connect(fn)
            col.addWidget(b)
        col.addStretch()
        h.addLayout(col)
        lay.addWidget(self.g_rep, 1)

        # --- dưới cùng
        row = QHBoxLayout()
        self.b_name = QPushButton("Đổi tên")
        self.b_name.setToolTip("Đổi mẫu tên file .tex kết quả ({ten} = tên file gốc)")
        self.b_name.clicked.connect(self.rename)
        row.addWidget(self.b_name)
        row.addStretch()
        ok, cancel = QPushButton("OK"), QPushButton("Cancel")
        ok.setDefault(True)
        ok.clicked.connect(self._ok)
        cancel.clicked.connect(self.reject)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)

    # ------------------------------------------------------------ bảng thay thế
    def load_rep(self, text: str):
        self.t.setRowCount(0)
        for ln in text.splitlines():
            if "=" in ln:
                a, b = ln.split("=", 1)
                if a.strip():
                    self.rep_add(a.strip(), b.strip())

    def rep_add(self, a="", b=""):
        a = a if isinstance(a, str) else ""
        r = self.t.rowCount()
        self.t.insertRow(r)
        it = QTableWidgetItem(str(r + 1))
        it.setFlags(Qt.ItemFlag.ItemIsEnabled)
        self.t.setItem(r, 0, it)
        self.t.setItem(r, 1, QTableWidgetItem(a))
        self.t.setItem(r, 2, QTableWidgetItem(b))

    def rep_del(self):
        for r in sorted({i.row() for i in self.t.selectedIndexes()}, reverse=True):
            self.t.removeRow(r)
        for r in range(self.t.rowCount()):
            self.t.item(r, 0).setText(str(r + 1))

    def rep_text(self) -> str:
        out = []
        for r in range(self.t.rowCount()):
            a = (self.t.item(r, 1).text() if self.t.item(r, 1) else "").strip()
            b = (self.t.item(r, 2).text() if self.t.item(r, 2) else "").strip()
            if a:
                out.append(f"{a} = {b}")
        return "\n".join(out)

    def rep_save(self):
        self.st.setValue("w2t/rep", self.rep_text())
        QMessageBox.information(self, "Thay thế cá nhân", "Đã lưu bảng thay thế.")

    def replacements(self) -> list[tuple[str, str]]:
        if not self.g_rep.isChecked():
            return []
        out = []
        for ln in self.rep_text().splitlines():
            a, b = ln.split(" = ", 1)
            out.append((a.strip(), b.strip()))
        return out

    # ------------------------------------------------------------ khoá, trợ giúp, đổi tên
    def _help(self, title, text, url=""):
        box = QMessageBox(QMessageBox.Icon.Information, title, text, parent=self)
        btn = box.addButton("Mở trang web", QMessageBox.ButtonRole.ActionRole) if url else None
        box.addButton("Đóng", QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if btn is not None and box.clickedButton() is btn:
            QDesktopServices.openUrl(QUrl(url))

    def save_mathpix(self):
        self.st.setValue("mathpix/app_id", self.e_mid.text().strip())
        self.st.setValue("mathpix/app_key", self.e_mkey.text().strip())
        QMessageBox.information(self, "Mathpix", "Đã lưu ID và Key.")

    def save_gemini(self):
        self.st.setValue("ai/key", self.e_gkey.text().strip())
        QMessageBox.information(self, "Gemini", "Đã lưu khoá API Gemini.")

    def rename(self):
        cur = str(self.st.value("w2t/outname", "{ten}_tuWord"))
        t, ok = QInputDialog.getText(self, "Đổi tên", "Mẫu tên file .tex kết quả ({ten} = tên file gốc):", text=cur)
        if ok and t.strip():
            self.st.setValue("w2t/outname", t.strip().replace("\\", "").replace("/", ""))

    # ------------------------------------------------------------ kết quả
    def engine(self) -> str:
        for k, rb in self.radios.items():
            if rb.isChecked():
                return k
        return "direct"

    def _ok(self):
        for k, c in self.boxes.items():
            self.st.setValue(f"w2t/{k}", c.isChecked())
        self.st.setValue("w2t/engine2", self.engine())
        self.st.setValue("w2t/show_word", self.c_show.isChecked())
        self.st.setValue("w2t/rep_on", self.g_rep.isChecked())
        self.st.setValue("w2t/rep", self.rep_text())
        # khoá nhập dở dang (chưa bấm «Lưu») vẫn được ghi nhận
        if self.e_mid.text().strip() or self.e_mkey.text().strip():
            self.st.setValue("mathpix/app_id", self.e_mid.text().strip())
            self.st.setValue("mathpix/app_key", self.e_mkey.text().strip())
        if self.e_gkey.text().strip():
            self.st.setValue("ai/key", self.e_gkey.text().strip())
        self.accept()

    def options(self) -> DocxOptions:
        b = self.boxes
        return DocxOptions(tables=b["tables"].isChecked(), images=b["images"].isChecked(), chem=b["chem"].isChecked(),
                           theory=b["theory"].isChecked(), ds=b["ds"].isChecked(), replacements=self.replacements())


# ====================================================================== luồng chuyển
def output_paths(src_path: str, win_settings=None) -> tuple[str, str]:
    """(file .tex, thư mục hình) trong DATA\\WORD2EXTEST; tên theo mẫu «Đổi tên» (mặc định <tên>_tuWord)."""
    from ...appdirs import folder
    d = folder("word2extest")
    os.makedirs(d, exist_ok=True)
    stem = os.path.splitext(os.path.basename(src_path))[0]
    tpl = "{ten}_tuWord"
    if win_settings is not None:
        tpl = str(win_settings.value("w2t/outname", tpl)) or tpl
    name = tpl.replace("{ten}", stem)
    return os.path.join(d, name + ".tex"), os.path.join(d, name + "_hinh")


def _client_gemini(dlg: Word2TexDialog):
    from ... import ai
    key = str(dlg.st.value("ai/key", ""))
    if not key:
        return None
    return ai.make_client("gemini", key, str(dlg.st.value("ai/model", "")) or ai.default_model("gemini"))


def convert_word_file(win, path: str, dlg: Word2TexDialog, tag: str = "") -> tuple[str, list[str]]:
    """Một file Word → nội dung .tex theo cách đọc «trực tiếp / Convert Equations / Toggle TeX»; trả về (tex, ghi chú)."""
    from ... import wordcom
    from ...docxnative import docx_to_ex, triage
    notes = []
    src = path
    rep = triage(path)
    eng = dlg.engine()
    if eng in ("convert", "toggle"):
        ok, out, msg = wordcom.convert_mathtype(path, "convert" if eng == "convert" else "toggle_tex", dlg.c_show.isChecked())
        if ok:
            src = out
            notes.append(f"Đã đổi công thức MathType qua Word ({msg}).")
        else:
            notes.append(f"Chưa đổi được MathType qua Word: {msg}")
    opts = dlg.options()
    opts.image_dir = output_paths(path, dlg.st)[1]
    tex, rep2 = docx_to_ex(src, opts, tag)
    notes += rep2.warnings if src == path else []
    from ...parser import parse_tex
    n = len(parse_tex(tex)) if tex.strip() else 0
    if n == 0 or rep.mathtype_ole:
        # kết quả rỗng/thiếu: ghi báo cáo «phần mềm nhìn thấy gì trong file» để dễ tìm nguyên nhân
        from ...docxnative import diagnose_docx
        rp = os.path.join(os.path.dirname(output_paths(path, dlg.st)[0]),
                          "chan_doan_" + os.path.splitext(os.path.basename(path))[0] + ".txt")
        try:
            with open(rp, "w", encoding="utf-8") as f:
                f.write(diagnose_docx(path, opts))
            notes.append(("Không nhận dạng được câu hỏi nào. " if n == 0 else "") +
                         f"Đã ghi báo cáo chẩn đoán: {rp} (gửi file này cho người hỗ trợ).")
        except OSError:
            pass
    return tex, notes


def run_word_to_tex(win, paths: list[str], dlg: Word2TexDialog, tag: str = "") -> list[dict]:
    """Chuyển các file Word/PDF theo cách đã chọn. Mỗi file trả về
    {'src', 'out', 'tex', 'n', 'notes', 'error'}; .tex ghi vào DATA\\WORD2EXTEST (hoặc DATA\\PDF2TEX nếu đi qua PDF)."""
    import re

    from PySide6.QtWidgets import QApplication

    from ... import wordcom
    from ...appdirs import folder
    from ...parser import parse_tex
    from .pdf2tex import convert_pdfs
    eng = dlg.engine()
    res = []
    for p in paths:
        item = {"src": p, "out": "", "tex": "", "n": 0, "notes": [], "error": ""}
        res.append(item)
        is_pdf = p.lower().endswith(".pdf")
        pdf_engine = {"mathpix": "mathpix", "gemini": "ai"}.get(eng, "text" if is_pdf else "")
        if pdf_engine:
            pdf = p
            if not is_pdf:
                pdf = os.path.join(folder("pdf2tex"), os.path.splitext(os.path.basename(p))[0] + ".pdf")
                QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
                try:
                    ok, msg = wordcom.export_pdf(p, pdf)
                finally:
                    QApplication.restoreOverrideCursor()
                if not ok:
                    item["notes"].append(f"Word không xuất được PDF ({msg}) – chuyển sang đọc trực tiếp file Word.")
                    pdf = ""
            if pdf:
                outs, lines = convert_pdfs(win, [pdf], pdf_engine, tag, client=_client_gemini(dlg) if eng == "gemini" else None)
                item["notes"] += [re.sub("<[^>]+>", "", x) for x in lines]
                if outs:
                    item["out"] = outs[0]
                    item["tex"] = open(outs[0], encoding="utf-8").read()
                    item["n"] = len(parse_tex(item["tex"]))
                    continue
            if is_pdf:
                continue
        try:
            tex, notes = convert_word_file(win, p, dlg, tag)
        except Exception as e:  # noqa: BLE001 – file hỏng, đang mở, không phải .docx…
            item["error"] = f"{type(e).__name__}: {e}"
            continue
        item["notes"] += notes
        out = output_paths(p, dlg.st)[0]
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write(tex)
        except OSError as e:
            item["error"] = f"Không ghi được {out}: {e}"
            continue
        item.update(out=out, tex=tex, n=len(parse_tex(tex)))
    return res


def summary_html(res: list[dict]) -> str:
    rows = []
    for it in res:
        name = os.path.basename(it["src"])
        if it["error"]:
            rows.append(f"<p style='color:#c00000'>✘ <b>{name}</b>: {it['error']}</p>")
            continue
        colour = "#2e7d32" if it["n"] else "#c00000"
        rows.append(f"<p style='color:{colour}'>{'✔' if it['n'] else '✘'} <b>{name}</b> → <b>{it['n']}</b> câu"
                    + (f"<br>Lưu tại: <code>{it['out']}</code>" if it["out"] else "") + "</p>")
        rows += [f"<p style='color:#b36b00;margin-left:1em'>• {n}</p>" for n in it["notes"]]
    return "".join(rows)
