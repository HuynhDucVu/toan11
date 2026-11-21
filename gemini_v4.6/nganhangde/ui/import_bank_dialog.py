"""Hộp thoại Nhập câu hỏi vào ngân hàng chuẩn MyLT 2026 tích hợp Rà soát & AI Giải lại (Gemini / Claude)."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from ..ai.question_verifier import (
    apply_verification_to_question,
    check_question_import_ready,
    verify_and_solve_question,
)
from ..converters.mylt_bank_importer import read_mylt_bank_rows
from ..core.config_manager import ConfigManager
from ..core.parser import Question, parse_tex_questions, read_tex_with_inputs
from ..core.similarity import jaccard_similarity

ID5_RE = re.compile(r"^[0-9][A-Z][0-9][A-Z][0-9]$")


@dataclass
class ImportCandidate:
    question: Question
    source_file: str
    selected: bool = True
    status: str = "CHƯA RÀ SOÁT"  # OK | AI_FIXED | NEEDS_FIX | DUP | SKIP_ID5 | AI_ERR
    note: str = ""
    ai_verified: bool = False


class AISolveWorker(QThread):
    progress = Signal(int, int, str)
    item_done = Signal(int, object, str, bool)  # row_idx, Question, status_note, ok
    finished_all = Signal(int, int)

    def __init__(self, indices: list[int], candidates: list[ImportCandidate], provider: str, api_key: str, model: str):
        super().__init__()
        self.indices = indices
        self.candidates = candidates
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        ok_cnt = err_cnt = 0
        total = len(self.indices)
        for step, row_idx in enumerate(self.indices, 1):
            if self._cancelled:
                break
            cand = self.candidates[row_idx]
            self.progress.emit(step, total, f"Đang rà soát & giải câu #{row_idx + 1} bằng {self.provider.upper()}...")
            try:
                vr = verify_and_solve_question(
                    cand.question,
                    provider=self.provider,
                    api_key=self.api_key,
                    model=self.model,
                )
                apply_verification_to_question(cand.question, vr)
                ready, msg = check_question_import_ready(cand.question, require_solution_and_answer=True)
                note = vr.audit_note or msg
                if not vr.is_original_answer_correct:
                    note = f"[AI đã sửa đáp án/lời giải] {note}"
                elif not vr.has_valid_solution:
                    note = f"[AI đã bổ sung lời giải] {note}"
                else:
                    note = f"[AI xác nhận đúng] {note}"
                self.item_done.emit(row_idx, cand.question, note, ready)
                if ready:
                    ok_cnt += 1
                else:
                    err_cnt += 1
            except Exception as exc:
                self.item_done.emit(row_idx, cand.question, f"Lỗi AI: {exc}", False)
                err_cnt += 1
        self.finished_all.emit(ok_cnt, err_cnt)


class ImportBankDialog(QDialog):
    """Hộp thoại Nhập câu hỏi vào ngân hàng (MyLT 2026 + Rà soát & AI Giải lại Gemini/Claude)."""

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.cfg = ConfigManager()
        self.source_files: list[Path] = []
        self.candidates: list[ImportCandidate] = []
        self.worker: AISolveWorker | None = None
        self.imported_count: int = 0

        self.setWindowTitle("Nhập câu hỏi vào ngân hàng (Rà soát & AI Giải lại)")
        self.resize(1040, 700)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(6)

        lbl_warn = QLabel("Chú ý: Người dùng không nên xoá file gốc sau khi nhập câu hỏi.")
        lbl_warn.setStyleSheet("color: #334155; font-style: italic;")
        root.addWidget(lbl_warn)

        # 1. Chọn file nguồn
        g_files = QGroupBox("Chọn một hoặc nhiều file nguồn chứa câu hỏi (.tex / .mylt)")
        rf = QHBoxLayout(g_files)
        self.cbo_files = QComboBox()
        self.cbo_files.setEditable(True)
        self.cbo_files.lineEdit().setPlaceholderText("Chọn tệp .tex (hỗ trợ main.tex) hoặc Bank.mylt...")
        b_pick = QPushButton("Chọn"); b_pick.clicked.connect(lambda: self._pick_files(append=False))
        b_add = QPushButton("Thêm"); b_add.clicked.connect(lambda: self._pick_files(append=True))
        rf.addWidget(QLabel("Files")); rf.addWidget(self.cbo_files, 1); rf.addWidget(b_pick); rf.addWidget(b_add)
        root.addWidget(g_files)

        # 2. Tuỳ chọn (chuẩn MyLT 2026)
        g_opt = QGroupBox("Tuỳ chọn nhập & lọc trùng")
        ro = QHBoxLayout(g_opt)
        self.chk_no_id5 = QCheckBox("Không nhập câu ID5")
        self.chk_skip_dup = QCheckBox("Bỏ qua câu trùng"); self.chk_skip_dup.setChecked(True)
        self.chk_check_dup = QCheckBox("Kiểm tra câu trùng"); self.chk_check_dup.setChecked(True)
        self.chk_deep_dup = QCheckBox("Kiểm tra câu trùng sâu")
        self.cbo_dup_rate = QComboBox(); self.cbo_dup_rate.addItems(["70%", "75%", "80%", "85%", "90%", "95%"])
        self.cbo_dup_rate.setCurrentText("80%")
        for w in (self.chk_no_id5, self.chk_skip_dup, self.chk_check_dup, self.chk_deep_dup, QLabel("Tỉ lệ"), self.cbo_dup_rate):
            ro.addWidget(w)
        ro.addStretch()
        root.addWidget(g_opt)

        # 3. Rà soát & AI Giải lại (Gemini / Claude)
        g_ai = QGroupBox("Rà soát chất lượng & AI tự động giải lại trước khi nhập (Gemini / Claude)")
        vai = QVBoxLayout(g_ai)

        r_ai1 = QHBoxLayout()
        self.chk_strict_sol = QCheckBox("Bắt buộc có lời giải & đáp án đúng mới được nhập")
        self.chk_strict_sol.setChecked(True)
        self.chk_ai_verify_all = QCheckBox("AI kiểm tra & giải lại cả câu đã có đáp án (để phát hiện đáp án sai)")
        self.chk_ai_verify_all.setChecked(False)
        r_ai1.addWidget(self.chk_strict_sol)
        r_ai1.addWidget(self.chk_ai_verify_all)
        r_ai1.addStretch()
        vai.addLayout(r_ai1)

        r_ai2 = QHBoxLayout()
        self.cbo_provider = QComboBox()
        self.cbo_provider.addItem("Gemini (Google)", "gemini")
        self.cbo_provider.addItem("Claude (Anthropic)", "claude")
        saved_prov = self.cfg.get("API", "ai_provider", "gemini")
        idx_p = self.cbo_provider.findData(saved_prov)
        if idx_p >= 0:
            self.cbo_provider.setCurrentIndex(idx_p)
        self.cbo_provider.currentIndexChanged.connect(self._on_provider_changed)

        self.cbo_model = QComboBox(); self.cbo_model.setEditable(True); self.cbo_model.setMinimumWidth(210)
        self.ed_api_key = QLineEdit()
        self.ed_api_key.setEchoMode(QLineEdit.Password)
        self.ed_api_key.setPlaceholderText("Nhập API Key (tự động lưu vào config.ini)...")
        b_save_key = QPushButton("Lưu Key"); b_save_key.clicked.connect(self._save_api_config)

        self.btn_audit = QPushButton("1. Rà soát (Kiểm tra)")
        self.btn_audit.clicked.connect(self._run_local_audit)
        self.btn_ai_fix = QPushButton("2. AI Giải lại câu lỗi/thiếu")
        self.btn_ai_fix.setStyleSheet("font-weight: bold;")
        self.btn_ai_fix.clicked.connect(self._run_ai_solve)
        self.btn_cancel_ai = QPushButton("Dừng AI")
        self.btn_cancel_ai.setEnabled(False)
        self.btn_cancel_ai.clicked.connect(self._cancel_ai)

        for w in (
            QLabel("AI:"), self.cbo_provider,
            QLabel("Model:"), self.cbo_model,
            QLabel("API Key:"), self.ed_api_key, b_save_key,
            self.btn_audit, self.btn_ai_fix, self.btn_cancel_ai,
        ):
            r_ai2.addWidget(w, 1 if w is self.ed_api_key else 0)
        vai.addLayout(r_ai2)

        r_prog = QHBoxLayout()
        self.prog_bar = QProgressBar(); self.prog_bar.setRange(0, 100); self.prog_bar.setValue(0)
        self.lbl_prog = QLabel("Chọn tệp nguồn để rà soát trước khi nhập.")
        r_prog.addWidget(self.prog_bar, 1); r_prog.addWidget(self.lbl_prog, 2)
        vai.addLayout(r_prog)
        root.addWidget(g_ai)

        self._on_provider_changed()

        # 4. Bảng rà soát + Khung xem/sửa LaTeX
        splitter = QSplitter(Qt.Vertical)
        self.tbl = QTableWidget(0, 6)
        self.tbl.setHorizontalHeaderLabels(["STT", "ID", "Loại", "Trạng thái", "Nội dung đề", "Ghi chú rà soát / AI"])
        self.tbl.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        self.tbl.itemSelectionChanged.connect(self._on_row_selected)
        splitter.addWidget(self.tbl)

        w_prev = QWidget(); vp = QVBoxLayout(w_prev); vp.setContentsMargins(0, 0, 0, 0)
        rp_hdr = QHBoxLayout()
        rp_hdr.addWidget(QLabel("Xem / Chỉnh sửa nhanh mã LaTeX câu đang chọn:"))
        rp_hdr.addStretch()
        b_apply_edit = QPushButton("Cập nhật sửa câu này"); b_apply_edit.clicked.connect(self._apply_manual_edit)
        rp_hdr.addWidget(b_apply_edit)
        self.ed_preview = QPlainTextEdit()
        self.ed_preview.setPlaceholderText("Chọn một dòng trong bảng trên để xem hoặc chỉnh sửa mã LaTeX...")
        vp.addLayout(rp_hdr); vp.addWidget(self.ed_preview, 1)
        splitter.addWidget(w_prev)
        splitter.setSizes([310, 150])
        root.addWidget(splitter, 1)

        # 5. Hàng nút công cụ chuẩn MyLT 2026
        r_btn1 = QHBoxLayout()
        b_hd = QPushButton("Hướng dẫn"); b_hd.clicked.connect(self._show_help)
        b_bak = QPushButton("Sao lưu"); b_bak.clicked.connect(self._backup_db)
        b_res = QPushButton("Khôi phục"); b_res.clicked.connect(self._restore_db)
        b_del_err = QPushButton("Xoá lỗi"); b_del_err.clicked.connect(self._remove_error_rows)
        b_exp = QPushButton("Xuất .tex đã sửa"); b_exp.clicked.connect(self._export_fixed_tex)
        b_import = QPushButton("3. Nhập vào ngân hàng")
        b_import.setStyleSheet("font-weight: bold;")
        b_import.setMinimumWidth(155)
        b_import.clicked.connect(self._do_import)
        b_close = QPushButton("Đóng"); b_close.clicked.connect(self.accept)

        for b in (b_hd, b_bak, b_res, b_del_err, b_exp):
            r_btn1.addWidget(b)
        r_btn1.addStretch()
        r_btn1.addWidget(b_import)
        r_btn1.addWidget(b_close)
        root.addLayout(r_btn1)

    def _on_provider_changed(self):
        prov = str(self.cbo_provider.currentData() or "gemini")
        self.cbo_model.clear()
        if prov == "claude":
            self.cbo_model.addItems([
                "claude-sonnet-4-20250514",
                "claude-3-7-sonnet-20250219",
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
            ])
            saved_m = self.cfg.get("API", "claude_model", "claude-sonnet-4-20250514")
            self.cbo_model.setCurrentText(saved_m)
            self.ed_api_key.setText(self.cfg.get("API", "claude_api_key", ""))
        else:
            self.cbo_model.addItems([
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
            ])
            saved_m = self.cfg.get("API", "gemini_model", "gemini-2.5-flash")
            self.cbo_model.setCurrentText(saved_m)
            self.ed_api_key.setText(self.cfg.get("API", "gemini_api_key", ""))

    def _save_api_config(self):
        prov = str(self.cbo_provider.currentData() or "gemini")
        self.cfg.set("API", "ai_provider", prov)
        if prov == "claude":
            self.cfg.set("API", "claude_api_key", self.ed_api_key.text().strip())
            self.cfg.set("API", "claude_model", self.cbo_model.currentText().strip())
        else:
            self.cfg.set("API", "gemini_api_key", self.ed_api_key.text().strip())
            self.cfg.set("API", "gemini_model", self.cbo_model.currentText().strip())
        self.cfg.save()
        QMessageBox.information(self, "Đã lưu", f"Đã lưu cấu hình API {prov.upper()} vào config.ini.")

    def _pick_files(self, append: bool = False):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Chọn tệp nguồn chứa câu hỏi (.tex / .mylt)",
            "",
            "Nguồn câu hỏi (*.tex *.mylt *.mdb);;LaTeX (*.tex);;MyLT Bank (*.mylt *.mdb)",
        )
        if not paths:
            return
        if not append:
            self.source_files = []
        for p in paths:
            fp = Path(p)
            if fp not in self.source_files:
                self.source_files.append(fp)
        self.cbo_files.clear()
        for fp in self.source_files:
            self.cbo_files.addItem(str(fp))
        if self.source_files:
            self.cbo_files.setCurrentText(str(self.source_files[0]))
        self._load_and_audit()

    def _load_and_audit(self):
        self.candidates = []
        for fp in self.source_files:
            if not fp.exists():
                continue
            try:
                if fp.suffix.lower() in (".mylt", ".mdb"):
                    rows = read_mylt_bank_rows(fp)
                    blocks = []
                    for nd, cid in rows:
                        t = nd.strip()
                        if not t:
                            continue
                        if cid.strip() and f"%[{cid.strip()}]" not in t:
                            t = f"%[{cid.strip()}]\n{t}"
                        blocks.append(t)
                    qs = parse_tex_questions("\n\n".join(blocks), auto_normalize=True)
                else:
                    content = read_tex_with_inputs(fp)
                    qs = parse_tex_questions(content, auto_normalize=True)
                for q in qs:
                    self.candidates.append(ImportCandidate(question=q, source_file=str(fp)))
            except Exception as exc:
                QMessageBox.warning(self, "Lỗi đọc tệp", f"Không đọc được {fp.name}:\n{exc}")
        self._run_local_audit()

    def _existing_bank_fingerprints(self) -> tuple[set[str], list[str]]:
        if self.db is None:
            return set(), []
        rows = self.db.conn.execute("SELECT fingerprint, stem_plain FROM questions").fetchall()
        fps = {str(r["fingerprint"] or "") for r in rows}
        stems = [str(r["stem_plain"] or "") for r in rows] if self.chk_deep_dup.isChecked() else []
        return fps, stems

    def _run_local_audit(self):
        if not self.candidates:
            if self.source_files:
                self._load_and_audit()
                return
            self.tbl.setRowCount(0)
            self.lbl_prog.setText("Chưa có câu hỏi nào. Hãy bấm 'Chọn' tệp nguồn.")
            return

        existing_fps, existing_stems = self._existing_bank_fingerprints() if self.chk_check_dup.isChecked() else (set(), [])
        threshold = int(self.cbo_dup_rate.currentText().replace("%", "") or "80") / 100.0
        seen_fps: set[str] = set()
        strict = self.chk_strict_sol.isChecked()

        cnt_ok = cnt_need = cnt_dup = 0
        for cand in self.candidates:
            q = cand.question
            pid = q.primary_id.upper()
            if self.chk_no_id5.isChecked() and pid and ID5_RE.fullmatch(pid):
                cand.status = "SKIP_ID5"
                cand.note = f"Bỏ qua do mã ID5 ({pid})"
                cand.selected = False
                continue

            fp = q.fingerprint()
            is_dup = False
            if self.chk_check_dup.isChecked():
                if fp in existing_fps or fp in seen_fps:
                    is_dup = True
                    cand.note = "Trùng chính xác với câu đã có trong kho/tệp"
                elif self.chk_deep_dup.isChecked() and existing_stems:
                    stem_now = f"{q.stem} {' '.join(q.choices)}".lower()
                    for st in existing_stems[:1500]:
                        if jaccard_similarity(stem_now, st) >= threshold:
                            is_dup = True
                            cand.note = f"Trùng sâu (>= {int(threshold*100)}%) với kho"
                            break
            seen_fps.add(fp)

            if is_dup and self.chk_skip_dup.isChecked():
                cand.status = "DUP"
                cand.selected = False
                cnt_dup += 1
                continue

            ready, msg = check_question_import_ready(q, require_solution_and_answer=strict)
            if ready:
                if cand.ai_verified:
                    cand.status = "AI_FIXED"
                else:
                    cand.status = "OK"
                    cand.note = msg
                cand.selected = True
                cnt_ok += 1
            else:
                cand.status = "NEEDS_FIX"
                cand.note = msg
                cand.selected = False
                cnt_need += 1

        self._render_table()
        self.lbl_prog.setText(
            f"Tổng: {len(self.candidates)} câu | Đạt: {cnt_ok} | Thiếu/Lỗi cần AI giải: {cnt_need} | Trùng: {cnt_dup}"
        )

    def _render_table(self):
        self.tbl.setRowCount(len(self.candidates))
        status_labels = {
            "OK": ("Đạt", QColor("#dcfce7")),
            "AI_FIXED": ("AI đã giải/xác nhận", QColor("#bbf7d0")),
            "NEEDS_FIX": ("Cần AI giải lại", QColor("#fee2e2")),
            "AI_ERR": ("Lỗi AI", QColor("#fecaca")),
            "DUP": ("Trùng (bỏ qua)", QColor("#fef3c7")),
            "SKIP_ID5": ("Bỏ qua ID5", QColor("#e2e8f0")),
        }
        for r, cand in enumerate(self.candidates):
            q = cand.question
            lbl, bg = status_labels.get(cand.status, (cand.status, QColor("#ffffff")))
            preview = " ".join(q.stem.split())[:130]
            vals = [str(r + 1), q.primary_id, q.qtype, lbl, preview, cand.note]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setBackground(bg)
                self.tbl.setItem(r, c, it)

    def _on_row_selected(self):
        row = self.tbl.currentRow()
        if 0 <= row < len(self.candidates):
            self.ed_preview.setPlainText(self.candidates[row].question.to_latex(include_solution=True))

    def _apply_manual_edit(self):
        row = self.tbl.currentRow()
        if not (0 <= row < len(self.candidates)):
            return
        qs = parse_tex_questions(self.ed_preview.toPlainText(), auto_normalize=True)
        if not qs:
            QMessageBox.warning(self, "Lỗi cú pháp", "Không nhận diện được khối \\begin{ex}...\\end{ex} hợp lệ.")
            return
        self.candidates[row].question = qs[0]
        self._run_local_audit()
        self.tbl.selectRow(row)

    def _run_ai_solve(self):
        if not self.candidates:
            QMessageBox.warning(self, "Chưa có câu hỏi", "Hãy chọn tệp nguồn trước.")
            return
        prov = str(self.cbo_provider.currentData() or "gemini")
        api_key = self.ed_api_key.text().strip()
        model = self.cbo_model.currentText().strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", f"Hãy nhập API Key cho {prov.upper()} rồi bấm 'Lưu Key'.")
            return

        if self.chk_ai_verify_all.isChecked():
            target_indices = [i for i, c in enumerate(self.candidates) if c.status not in ("DUP", "SKIP_ID5")]
        else:
            target_indices = [i for i, c in enumerate(self.candidates) if c.status in ("NEEDS_FIX", "AI_ERR")]

        if not target_indices:
            QMessageBox.information(
                self,
                "Không có câu cần giải lại",
                "Tất cả câu hỏi hợp lệ đều đã có đủ lời giải và đáp án.\n"
                "(Nếu muốn AI kiểm tra lại toán học cả câu đã có đáp án, hãy tick 'AI kiểm tra & giải lại cả câu đã có đáp án'.)",
            )
            return

        self.btn_ai_fix.setEnabled(False)
        self.btn_audit.setEnabled(False)
        self.btn_cancel_ai.setEnabled(True)
        self.prog_bar.setRange(0, len(target_indices))
        self.prog_bar.setValue(0)

        self.worker = AISolveWorker(target_indices, self.candidates, prov, api_key, model)
        self.worker.progress.connect(self._on_ai_progress)
        self.worker.item_done.connect(self._on_ai_item_done)
        self.worker.finished_all.connect(self._on_ai_finished)
        self.worker.start()

    def _cancel_ai(self):
        if self.worker is not None:
            self.worker.cancel()
            self.lbl_prog.setText("Đang dừng AI...")

    def _on_ai_progress(self, step: int, total: int, msg: str):
        self.prog_bar.setValue(step)
        self.lbl_prog.setText(f"[{step}/{total}] {msg}")

    def _on_ai_item_done(self, row_idx: int, updated_q: Question, note: str, ok: bool):
        cand = self.candidates[row_idx]
        cand.question = updated_q
        cand.note = note
        cand.ai_verified = ok
        cand.status = "AI_FIXED" if ok else "AI_ERR"
        cand.selected = ok
        self._render_table()
        if self.tbl.currentRow() == row_idx:
            self.ed_preview.setPlainText(updated_q.to_latex(include_solution=True))

    def _on_ai_finished(self, ok_cnt: int, err_cnt: int):
        self.btn_ai_fix.setEnabled(True)
        self.btn_audit.setEnabled(True)
        self.btn_cancel_ai.setEnabled(False)
        self.lbl_prog.setText(f"AI hoàn tất: {ok_cnt} câu đạt chuẩn | {err_cnt} câu còn lỗi.")
        QMessageBox.information(
            self,
            "AI Rà soát & Giải lại xong",
            f"Đã xử lý xong bằng AI:\n- Đạt chuẩn (có lời giải & đáp án đúng): {ok_cnt} câu\n- Còn lỗi / chưa giải được: {err_cnt} câu",
        )

    def _remove_error_rows(self):
        before = len(self.candidates)
        self.candidates = [c for c in self.candidates if c.status in ("OK", "AI_FIXED")]
        self._render_table()
        self.lbl_prog.setText(f"Đã loại {before - len(self.candidates)} câu lỗi/trùng. Còn lại {len(self.candidates)} câu đạt.")

    def _export_fixed_tex(self):
        if not self.candidates:
            return
        out, _ = QFileDialog.getSaveFileName(self, "Xuất tệp .tex đã rà soát & AI giải lại", "cau_hoi_da_ra_soat.tex", "LaTeX (*.tex)")
        if not out:
            return
        body = "\n\n".join(c.question.to_latex(include_solution=True) for c in self.candidates)
        Path(out).write_text(body + "\n", encoding="utf-8")
        QMessageBox.information(self, "Xuất thành công", f"Đã lưu {len(self.candidates)} câu vào:\n{out}")

    def _backup_db(self):
        if self.db is None or not getattr(self.db, "db_path", ""):
            return
        out, _ = QFileDialog.getSaveFileName(self, "Sao lưu ngân hàng (.db)", "nganhang_backup.db", "SQLite DB (*.db)")
        if out:
            shutil.copy2(self.db.db_path, out)
            QMessageBox.information(self, "Sao lưu", f"Đã sao lưu ngân hàng tại:\n{out}")

    def _restore_db(self):
        if self.db is None or not getattr(self.db, "db_path", ""):
            return
        src, _ = QFileDialog.getOpenFileName(self, "Khôi phục ngân hàng (.db)", "", "SQLite DB (*.db)")
        if src:
            target = self.db.db_path
            self.db.close()
            shutil.copy2(src, target)
            from ..core.db import QuestionBankDB
            self.db.__init__(target)
            QMessageBox.information(self, "Khôi phục", "Đã khôi phục ngân hàng thành công.")

    def _show_help(self):
        QMessageBox.information(
            self,
            "Hướng dẫn — Nhập & Rà soát câu hỏi bằng AI",
            "Quy trình 3 bước chuẩn trước khi nhập ngân hàng:\n"
            "1. Bấm 'Chọn' (hoặc 'Thêm') tệp .tex / .mylt. Phần mềm tự động rà soát lỗi cú pháp, thiếu \\loigiai, thiếu/sai đáp án \\True hoặc \\shortans, và lọc trùng.\n"
            "2. Chọn AI (Gemini hoặc Claude), nhập API Key và bấm '2. AI Giải lại câu lỗi/thiếu'. AI sẽ tự giải lại từng bước theo chuẩn Toán THPT Việt Nam, cập nhật đáp án đúng và lời giải chi tiết.\n"
            "   (Tick thêm 'AI kiểm tra & giải lại cả câu đã có đáp án' nếu muốn AI thẩm định lại toàn bộ đề.)\n"
            "3. Bấm '3. Nhập vào ngân hàng'. Khi tick 'Bắt buộc có lời giải & đáp án đúng mới được nhập', chỉ các câu đạt chuẩn mới được đưa vào kho.",
        )

    def _do_import(self):
        if self.db is None:
            QMessageBox.warning(self, "Ngân hàng", "Chưa kết nối cơ sở dữ liệu.")
            return
        if not self.candidates:
            QMessageBox.warning(self, "Trống", "Chưa có câu hỏi nào để nhập.")
            return

        strict = self.chk_strict_sol.isChecked()
        ready_list: list[ImportCandidate] = []
        blocked_cnt = 0
        for cand in self.candidates:
            if cand.status in ("DUP", "SKIP_ID5"):
                continue
            ok, _ = check_question_import_ready(cand.question, require_solution_and_answer=strict)
            if ok:
                ready_list.append(cand)
            else:
                blocked_cnt += 1

        if not ready_list:
            QMessageBox.warning(
                self,
                "Không thể nhập",
                f"Có {blocked_cnt} câu chưa đủ lời giải hoặc đáp án đúng.\n"
                "Hãy bấm '2. AI Giải lại câu lỗi/thiếu' trước khi nhập (hoặc bỏ tick 'Bắt buộc có lời giải & đáp án đúng').",
            )
            return

        added = dup = 0
        for cand in ready_list:
            cand.question.raw = cand.question.to_latex(include_solution=True)
            _, ok = self.db.add_question(cand.question, asset_base_dir=str(Path(cand.source_file).parent))
            if ok:
                added += 1
            else:
                dup += 1

        self.imported_count += added
        QMessageBox.information(
            self,
            "Nhập ngân hàng hoàn tất",
            f"- Đã nhập mới: {added} câu\n"
            f"- Bỏ qua do trùng kho: {dup} câu\n"
            f"- Chặn lại do thiếu lời giải / sai đáp án: {blocked_cnt} câu",
        )
        if added > 0 and blocked_cnt == 0:
            self.accept()
