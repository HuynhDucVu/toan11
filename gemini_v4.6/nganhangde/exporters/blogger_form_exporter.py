from __future__ import annotations
from dataclasses import dataclass
from html import escape
import json
from pathlib import Path


@dataclass
class GoogleFormConfig:
    form_action_url: str = ""
    entry_exam_name: str = ""
    entry_sbd: str = ""
    entry_student_name: str = ""
    entry_class: str = ""
    entry_score: str = ""
    entry_answers: str = ""
    entry_duration: str = ""


def export_blogger_form_html(
    exam_title: str,
    questions: list[dict],
    output_html: Path,
    duration_minutes: int = 45,
    form_cfg: GoogleFormConfig | None = None,
) -> Path:
    form_cfg = form_cfg or GoogleFormConfig()
    answer_key = [q.get("correct_index", 0) for q in questions]

    q_blocks: list[str] = []
    for idx, q in enumerate(questions, start=1):
        opts_html = []
        for opt_idx, opt_text in enumerate(q.get("options", [])):
            letter = "ABCD"[opt_idx] if opt_idx < 4 else str(opt_idx + 1)
            opts_html.append(
                f'<label style="display:block;margin:6px 0;cursor:pointer;">'
                f'<input type="radio" name="q_{idx}" value="{opt_idx}"> '
                f'<b>{letter}.</b> {escape(str(opt_text))}</label>'
            )
        q_blocks.append(
            f'<div class="mylt-q" style="border:1px solid #ddd;padding:12px;margin:12px 0;border-radius:8px;">'
            f'<div><b>Câu {idx}.</b> {escape(str(q.get("stem", "")))}</div>'
            f'<div style="margin-top:8px;">{"".join(opts_html)}</div>'
            f'</div>'
        )

    html_doc = f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <title>{escape(exam_title)}</title>
  <script>
    window.MathJax = {{ tex: {{ inlineMath: [['$', '$'], ['\\(', '\\)']] }} }};
  </script>
  <script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
</head>
<body style="font-family:Arial,sans-serif;max-width:860px;margin:auto;padding:16px;">
  <h2 style="color:#006666;">{escape(exam_title)}</h2>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-bottom:14px;">
    <input id="hs_sbd" placeholder="Số báo danh" style="padding:8px;">
    <input id="hs_ten" placeholder="Họ và tên học sinh" style="padding:8px;">
    <input id="hs_lop" placeholder="Lớp" style="padding:8px;">
  </div>
  <div style="font-weight:bold;color:#b00;margin-bottom:12px;">
    Thời gian còn lại: <span id="timer">{duration_minutes:02d}:00</span>
  </div>

  <div id="exam-container">
    {"".join(q_blocks)}
  </div>

  <button onclick="submitExam()" style="padding:10px 22px;background:#006666;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:15px;">
    Nộp bài &amp; Chấm điểm
  </button>
  <div id="result-box" style="margin-top:16px;font-size:16px;font-weight:bold;color:#006666;"></div>

  <script>
    const ANSWER_KEY = {json.dumps(answer_key)};
    const FORM_CFG = {json.dumps(form_cfg.__dict__, ensure_ascii=False)};
    const EXAM_TITLE = {json.dumps(exam_title, ensure_ascii=False)};
    let totalSec = {duration_minutes * 60};
    let elapsedSec = 0;

    const tick = setInterval(() => {{
      if (totalSec <= 0) {{ clearInterval(tick); submitExam(); return; }}
      totalSec--; elapsedSec++;
      const m = String(Math.floor(totalSec / 60)).padStart(2, '0');
      const s = String(totalSec % 60).padStart(2, '0');
      document.getElementById('timer').textContent = m + ':' + s;
    }}, 1000);

    function submitExam() {{
      clearInterval(tick);
      let correct = 0;
      let userAns = [];
      ANSWER_KEY.forEach((ans, i) => {{
        const checked = document.querySelector('input[name="q_' + (i + 1) + '"]:checked');
        const val = checked ? parseInt(checked.value, 10) : -1;
        userAns.push(val >= 0 ? "ABCD"[val] : "-");
        if (val === ans) correct++;
      }});
      const score = ((correct / Math.max(1, ANSWER_KEY.length)) * 10).toFixed(2);
      document.getElementById('result-box').textContent =
        "Kết quả: " + correct + "/" + ANSWER_KEY.length + " câu đúng — Điểm: " + score;

      if (FORM_CFG.form_action_url) {{
        const fd = new FormData();
        if (FORM_CFG.entry_exam_name) fd.append(FORM_CFG.entry_exam_name, EXAM_TITLE);
        if (FORM_CFG.entry_sbd) fd.append(FORM_CFG.entry_sbd, document.getElementById('hs_sbd').value);
        if (FORM_CFG.entry_student_name) fd.append(FORM_CFG.entry_student_name, document.getElementById('hs_ten').value);
        if (FORM_CFG.entry_class) fd.append(FORM_CFG.entry_class, document.getElementById('hs_lop').value);
        if (FORM_CFG.entry_score) fd.append(FORM_CFG.entry_score, score);
        if (FORM_CFG.entry_answers) fd.append(FORM_CFG.entry_answers, userAns.join(""));
        if (FORM_CFG.entry_duration) fd.append(FORM_CFG.entry_duration, Math.round(elapsedSec / 60) + " phút");
        fetch(FORM_CFG.form_action_url, {{ method: "POST", mode: "no-cors", body: fd }});
      }}
    }}
  </script>
</body>
</html>
"""
    output_html = Path(output_html)
    output_html.parent.mkdir(parents=True, exist_ok=True)
    output_html.write_text(html_doc, encoding="utf-8")
    return output_html
