"""Mục «Tuỳ chọn trộn đề» (mã đề · trộn · trình bày · phiếu chấm · online/Word)."""
from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QFormLayout, QLabel, QSpinBox, QTabWidget, QVBoxLayout, QWidget
from ...exporter import ExportOptions
from ...generator import MixOptions, make_codes


class MixOptionsBox(QWidget):
    """Nhóm ô tick tuỳ chọn trộn đề (dùng chung cho tab Tạo đề và Trộn đề từ file)."""
    ITEMS = (("shuffle_q", "Trộn thứ tự câu trong từng phần", True),
             ("shuffle_tn", "Trộn phương án A, B, C, D", True),
             ("shuffle_ds", "Trộn thứ tự ý a, b, c, d câu Đúng/Sai", True),
             ("balance", "Cân bằng số đáp án A/B/C/D trong mỗi đề", True),
             ("first_original", "Mã đề đầu tiên giữ nguyên thứ tự (đề gốc)", False),
             ("sort_by_level", "Trong mỗi phần xếp câu từ dễ đến khó (Nhận biết → Vận dụng cao)", False))

    def __init__(self, settings, prefix):
        super().__init__()
        self.st, self.prefix = settings, prefix
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.boxes = {}
        for key, text, default in self.ITEMS:
            c = QCheckBox(text)
            v = self.st.value(f"{prefix}/mix_{key}", default)
            c.setChecked(v if isinstance(v, bool) else str(v).lower() == "true")
            lay.addWidget(c)
            self.boxes[key] = c

    def options(self) -> MixOptions:
        return MixOptions(**{k: c.isChecked() for k, c in self.boxes.items()})

    def save(self):
        for k, c in self.boxes.items():
            self.st.setValue(f"{self.prefix}/mix_{k}", c.isChecked())


class ExamOptionsBox(QTabWidget):
    """Mục «Tuỳ chọn trộn đề»: mã đề · trộn · trình bày · phiếu chấm (đáp án Excel cho TNMaker)."""

    def __init__(self, settings, prefix, show_codes=True):
        super().__init__()
        self.st, self.prefix = settings, prefix

        def val(key, default):
            v = self.st.value(f"{prefix}/opt_{key}", default)
            if isinstance(default, bool):
                return v if isinstance(v, bool) else str(v).lower() == "true"
            return type(default)(v)

        def combo(items, key, default):
            cb = QComboBox()
            for text, data in items:
                cb.addItem(text, data)
            cb.setCurrentIndex(max(0, cb.findData(val(key, default))))
            return cb

        # Mã đề
        self.w_codes = QWidget()
        f = QFormLayout(self.w_codes)
        self.cb_codemode = combo([("Liên tiếp (101, 102, …)", "seq"), ("Ngẫu nhiên, không trùng", "rand")],
                                 "codemode", "seq")
        self.sp_start = QSpinBox()
        self.sp_start.setRange(0, 9999)
        self.sp_start.setValue(val("start", 101))
        self.cb_digits = combo([("3 chữ số (101)", 3), ("4 chữ số (0101)", 4)], "digits", 3)
        f.addRow("Cách đánh mã", self.cb_codemode)
        f.addRow("Bắt đầu từ", self.sp_start)
        f.addRow("Độ dài mã", self.cb_digits)
        self.l_preview = QLabel()
        f.addRow("Ví dụ", self.l_preview)
        for w_ in (self.cb_codemode, self.cb_digits):
            w_.currentIndexChanged.connect(self._preview)
        self.sp_start.valueChanged.connect(self._preview)
        if show_codes:
            self.addTab(self.w_codes, "Mã đề")

        # Trộn
        self.mix = MixOptionsBox(settings, prefix)
        self.addTab(self.mix, "Trộn")

        # Trình bày
        w = QWidget()
        v = QVBoxLayout(w)
        self.c_renum = QCheckBox("Đánh số lại từ Câu 1 ở mỗi phần (như đề thi tốt nghiệp)")
        self.c_official = QCheckBox("Tiêu đề và lời dẫn từng phần theo mẫu đề thi tốt nghiệp")
        self.c_scoring = QCheckBox("In thang điểm (Phần I 0,25 · Phần II 0,1/0,25/0,5/1 · Phần III 0,5) trong file lời giải")
        self.c_showid = QCheckBox("In ID nhỏ sau mỗi câu trong file lời giải (bản giáo viên)")
        self.c_zip = QCheckBox("Nén toàn bộ kết quả thành 1 file .zip")
        for c, k in ((self.c_renum, "renumber"), (self.c_official, "official"), (self.c_scoring, "scoring"),
                     (self.c_showid, "showid"), (self.c_zip, "zip")):
            c.setChecked(val(k, False))
            v.addWidget(c)
        v.addStretch()
        self.addTab(w, "Trình bày")

        # Phiếu chấm TNMaker
        w = QWidget()
        f = QFormLayout(w)
        self.c_xlsx = QCheckBox("Xuất file đáp án Excel dap_an_TNMaker.xlsx")
        self.c_xlsx.setChecked(val("xlsx", True))
        self.cb_layout = combo([("Mỗi dòng 1 câu, mỗi cột 1 mã đề", "doc"), ("Mỗi dòng 1 mã đề, mỗi cột 1 câu", "ngang")],
                               "layout", "doc")
        self.cb_ds = combo([("Gộp 1 ô / câu (ĐSĐS)", "gop"), ("Tách 4 ô a, b, c, d", "tach")], "ds", "gop")
        self.cb_sym = combo([("Đ / S", "ĐS"), ("T / F", "TF"), ("1 / 0", "10")], "sym", "ĐS")
        self.cb_dec = combo([("Dấu phẩy (0,5)", ","), ("Dấu chấm (0.5)", ".")], "dec", ",")
        f.addRow(self.c_xlsx)
        f.addRow("Bố cục", self.cb_layout)
        f.addRow("Phần II Đúng/Sai", self.cb_ds)
        f.addRow("Kí hiệu Đúng/Sai", self.cb_sym)
        f.addRow("Phần III – thập phân", self.cb_dec)
        note = QLabel("Trong TNMaker: tạo bài thi theo mẫu phiếu tốt nghiệp (3 phần) → nhập đáp án từ file Excel → "
                      "chọn <code>dap_an_TNMaker.xlsx</code>. Nếu mẫu đáp án của TNMaker khác, đổi bố cục/kí hiệu ở trên. "
                      "File còn có sheet <i>Mã đề – câu gốc</i> để đối chiếu.")
        note.setWordWrap(True)
        f.addRow(note)
        self.addTab(w, "Phiếu chấm TNMaker")

        w = QWidget()
        v = QVBoxLayout(w)
        self.c_online = QCheckBox("Bài làm online: mỗi mã đề 1 file HTML (mở trên máy tính/điện thoại, nộp là có điểm)")
        self.c_online_sol = QCheckBox("   Hiện lời giải sau khi học sinh nộp bài")
        self.c_moodle = QCheckBox("File Moodle XML (nhập vào ngân hàng câu hỏi Moodle/LMS)")
        self.c_word = QCheckBox("File Word .docx mỗi mã đề (công thức Word gốc – cần cài pandoc)")
        from ...wordconv import PandocMissing, pandoc_path
        try:
            pandoc_path()
        except PandocMissing:
            self.c_word.setEnabled(False)
            self.c_word.setToolTip("Chưa cài pandoc: tải tại pandoc.org/installing.html")
        for c, k, d in ((self.c_online, "online", False), (self.c_online_sol, "online_sol", True),
                        (self.c_moodle, "moodle", False), (self.c_word, "word", False)):
            c.setChecked(val(k, d))
            v.addWidget(c)
        note = QLabel("<i>Bài online dùng MathJax để hiện công thức (cần mạng khi mở). Đáp án nằm trong file "
                      "(đã mã hoá nhẹ) – phù hợp ôn tập, không dùng cho kì thi chính thức.</i>")
        note.setWordWrap(True)
        v.addWidget(note)
        v.addStretch()
        self.addTab(w, "Online / Word")
        self._preview()

    def _preview(self):
        self.l_preview.setText(", ".join(self.codes(3, preview=True)) + ", …")

    def codes(self, n, preview=False):
        rnd = self.cb_codemode.currentData() == "rand"
        if rnd and preview:
            return ["(ngẫu nhiên)"]
        return make_codes(n, self.sp_start.value(), self.cb_digits.currentData(), rnd)

    def mix_options(self) -> MixOptions:
        return self.mix.options()

    def export_options(self) -> ExportOptions:
        return ExportOptions(renumber=self.c_renum.isChecked(), official_titles=self.c_official.isChecked(),
                             scoring=self.c_scoring.isChecked(), answers_xlsx=self.c_xlsx.isChecked(),
                             tnmaker_layout=self.cb_layout.currentData(), ds_style=self.cb_ds.currentData(),
                             ds_symbols=self.cb_sym.currentData(), kq_decimal=self.cb_dec.currentData(),
                             show_id=self.c_showid.isChecked(), make_zip=self.c_zip.isChecked(),
                             online_html=self.c_online.isChecked(), online_solution=self.c_online_sol.isChecked(),
                             moodle=self.c_moodle.isChecked(), word=self.c_word.isChecked() and self.c_word.isEnabled())

    def apply_thpt2026(self):
        self.cb_codemode.setCurrentIndex(self.cb_codemode.findData("seq"))
        self.sp_start.setValue(101)
        self.cb_digits.setCurrentIndex(self.cb_digits.findData(4))
        for k, on in (("shuffle_q", True), ("shuffle_tn", True), ("shuffle_ds", False), ("balance", True),
                      ("first_original", False)):
            self.mix.boxes[k].setChecked(on)
        for c in (self.c_renum, self.c_official, self.c_scoring, self.c_xlsx):
            c.setChecked(True)

    def save(self):
        self.mix.save()
        for k, w_ in (("codemode", self.cb_codemode), ("digits", self.cb_digits), ("layout", self.cb_layout),
                      ("ds", self.cb_ds), ("sym", self.cb_sym), ("dec", self.cb_dec)):
            self.st.setValue(f"{self.prefix}/opt_{k}", w_.currentData())
        self.st.setValue(f"{self.prefix}/opt_start", self.sp_start.value())
        for k, c in (("renumber", self.c_renum), ("official", self.c_official), ("scoring", self.c_scoring),
                     ("xlsx", self.c_xlsx), ("showid", self.c_showid), ("zip", self.c_zip),
                     ("online", self.c_online), ("online_sol", self.c_online_sol), ("moodle", self.c_moodle),
                     ("word", self.c_word)):
            self.st.setValue(f"{self.prefix}/opt_{k}", c.isChecked())
