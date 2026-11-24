"""Rà soát toán học và tự động giải lại câu hỏi bằng AI (Gemini hoặc Claude) trước khi nhập ngân hàng."""
from __future__ import annotations
from dataclasses import dataclass, field
import json
import os
import re
import time
import urllib.error
import urllib.request
from ..core.parser import Question
from ..core.review import audit_question

SYSTEM_PROMPT_MATH_AUDIT = (
    "Bạn là giáo sư Toán học THPT Việt Nam (chương trình GDPT 2018). "
    "Nhiệm vụ của bạn là đọc câu hỏi Toán học dạng LaTeX (gói ex_test), "
    "tự giải độc lập từng bước một cách chính xác tuyệt đối (giữ giá trị chính xác ở mọi bước trung gian, "
    "chỉ làm tròn ở kết quả cuối cùng nếu đề yêu cầu), sau đó đối chiếu với đáp án và lời giải gốc.\n"
    "Quy chuẩn LaTeX bắt buộc cho lời giải:\n"
    "- Dùng \\dfrac thay cho \\frac.\n"
    "- Vector 2 điểm dùng \\overrightarrow{AB}, vector chữ thường/đơn vị dùng \\mathbf{a}.\n"
    "- Toán tử lớn dùng \\displaystyle\\int\\limits, \\lim\\limits.\n"
    "- Dùng \\Leftrightarrow cho phép biến đổi tương đương; tránh dùng \\arcsin, \\arccos, \\operatorname{arccot}.\n"
    "- Không viết 'Chọn A/B/C/D' cứng trong lời giải trắc nghiệm (vì đề sẽ trộn phương án).\n"
    "- Với câu Trả lời ngắn (KQ), đáp số chỉ gồm chữ số, dấu '-' và dấu phẩy ',' (tối đa 4 ký tự theo CV 1239).\n"
    "- CHỈ trả về duy nhất 1 đối tượng JSON hợp lệ, không kèm văn bản giải thích bên ngoài."
)


@dataclass
class VerificationResult:
    is_original_answer_correct: bool = False
    has_valid_solution: bool = False
    correct_indices: list[int] = field(default_factory=list)
    short_ans: str = ""
    solution_latex: str = ""
    audit_note: str = ""
    raw_response: str = ""


def _extract_json_object(text: str) -> dict:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\s*```$", "", s)
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        s = s[start : end + 1]
    return json.loads(s)


def _http_post_json(url: str, payload: dict, headers: dict[str, str], retries: int = 3, timeout: int = 90) -> dict:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    delay = 2.0
    last_exc: Exception | None = None
    for attempt in range(retries):
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            last_exc = RuntimeError(f"HTTP {exc.code}: {err_body or exc.reason}")
            if exc.code not in (429, 500, 502, 503, 529) or attempt == retries - 1:
                raise last_exc from exc
        except Exception as exc:
            last_exc = exc
            if attempt == retries - 1:
                raise
        time.sleep(delay)
        delay *= 2.0
    raise last_exc or RuntimeError("Lỗi gọi API AI.")


def _call_gemini_json(prompt: str, api_key: str, model: str) -> str:
    key = api_key.strip() or os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError("Chưa nhập Gemini API Key.")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT_MATH_AUDIT}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }
    data = _http_post_json(url, payload, {"Content-Type": "application/json"})
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError(f"Gemini không trả về nội dung: {str(data)[:300]}")
    parts = (cands[0].get("content") or {}).get("parts") or []
    return "".join(str(p.get("text", "")) for p in parts)


def _call_claude_json(prompt: str, api_key: str, model: str) -> str:
    key = api_key.strip() or os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise ValueError("Chưa nhập Claude (Anthropic) API Key.")
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": 4096,
        "temperature": 0.1,
        "system": SYSTEM_PROMPT_MATH_AUDIT,
        "messages": [{"role": "user", "content": prompt}],
    }
    headers = {
        "Content-Type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    data = _http_post_json(url, payload, headers)
    blocks = data.get("content") or []
    return "".join(str(b.get("text", "")) for b in blocks if b.get("type") == "text")


def build_verification_prompt(q: Question) -> str:
    lines = [
        f"Loại câu hỏi: {q.qtype} (TN=Trắc nghiệm 4 phương án, DS=Đúng/Sai 4 ý, KQ=Trả lời ngắn, TL=Tự luận).",
        "Đề bài (LaTeX):",
        q.stem.strip(),
    ]
    if q.qtype in ("TN", "DS") and q.choices:
        lines.append("\nCác phương án (đánh chỉ số từ 0):")
        for idx, ch in enumerate(q.choices):
            mark = " [ĐANG ĐÁNH DẤU \\True]" if (idx < len(q.correct) and q.correct[idx]) else ""
            lines.append(f"  [{idx}]{mark}: {ch}")
    elif q.qtype == "KQ":
        lines.append(f"\nĐáp số hiện tại: {q.short_ans!r}")

    lines.append("\nLời giải hiện tại:")
    lines.append(q.solution.strip() if q.solution.strip() else "(TRỐNG - CHƯA CÓ LỜI GIẢI)")

    lines.append(
        "\nHãy tự giải lại câu hỏi trên, kiểm tra đáp án & lời giải hiện tại và trả về JSON theo đúng cấu trúc:\n"
        "{\n"
        '  "is_original_answer_correct": true/false,\n'
        '  "has_valid_solution": true/false,\n'
        '  "correct_indices": [chỉ số 0-based của phương án đúng; TN có đúng 1 phần tử, DS có các phần tử đúng, KQ/TL để []],\n'
        '  "short_ans": "đáp số ngắn cho câu KQ (dùng dấu phẩy thập phân, rỗng nếu không phải KQ)",\n'
        '  "solution_latex": "lời giải chi tiết chuẩn LaTeX (chỉ nội dung bên trong \\loigiai{...}, không ghi lệnh \\loigiai)",\n'
        '  "audit_note": "nhận xét ngắn gọn tiếng Việt: Đáp án cũ đúng hay sai, đã sửa gì"\n'
        "}"
    )
    return "\n".join(lines)


def verify_and_solve_question(
    q: Question,
    provider: str = "gemini",
    api_key: str = "",
    model: str = "",
) -> VerificationResult:
    prov = provider.strip().lower()
    prompt = build_verification_prompt(q)
    if prov == "claude":
        mdl = model.strip() or "claude-sonnet-4-20250514"
        raw = _call_claude_json(prompt, api_key, mdl)
    else:
        mdl = model.strip() or "gemini-2.5-flash"
        raw = _call_gemini_json(prompt, api_key, mdl)

    obj = _extract_json_object(raw)
    c_idx = obj.get("correct_indices") or []
    if not isinstance(c_idx, list):
        c_idx = []
    clean_idx: list[int] = []
    for x in c_idx:
        try:
            clean_idx.append(int(x))
        except (TypeError, ValueError):
            pass

    sol = str(obj.get("solution_latex") or "").strip()
    # Bỏ vỏ \loigiai{...} nếu AI lỡ bọc thêm
    if sol.startswith(r"\loigiai{") and sol.endswith("}"):
        sol = sol[len(r"\loigiai{") : -1].strip()

    return VerificationResult(
        is_original_answer_correct=bool(obj.get("is_original_answer_correct", False)),
        has_valid_solution=bool(obj.get("has_valid_solution", False)),
        correct_indices=clean_idx,
        short_ans=str(obj.get("short_ans") or "").strip(),
        solution_latex=sol,
        audit_note=str(obj.get("audit_note") or "").strip(),
        raw_response=raw,
    )


def apply_verification_to_question(q: Question, vr: VerificationResult) -> Question:
    """Cập nhật đáp án đúng và lời giải từ kết quả AI vào đối tượng Question."""
    if q.qtype == "TN" and q.choices:
        valid = [i for i in vr.correct_indices if 0 <= i < len(q.choices)]
        if len(valid) == 1:
            q.correct = [i == valid[0] for i in range(len(q.choices))]
    elif q.qtype == "DS" and q.choices:
        valid_set = {i for i in vr.correct_indices if 0 <= i < len(q.choices)}
        if not vr.is_original_answer_correct or len(q.correct) != len(q.choices):
            q.correct = [i in valid_set for i in range(len(q.choices))]
    elif q.qtype == "KQ" and vr.short_ans:
        if not vr.is_original_answer_correct or not q.short_ans.strip():
            q.short_ans = vr.short_ans

    if vr.solution_latex and (not q.solution.strip() or not vr.is_original_answer_correct or not vr.has_valid_solution):
        q.solution = vr.solution_latex

    q.raw = q.to_latex(include_solution=True)
    return q


def check_question_import_ready(q: Question, require_solution_and_answer: bool = True) -> tuple[bool, str]:
    """Kiểm tra cục bộ câu hỏi đã đủ điều kiện (có lời giải + đáp án hợp lệ + không lỗi cú pháp) trước khi nhập."""
    issues = audit_question(q)
    errors = [iss for iss in issues if iss.level == "ERROR"]
    has_sol = bool(q.solution.strip())

    reasons: list[str] = []
    for err in errors:
        reasons.append(err.message)
    if require_solution_and_answer and not has_sol:
        reasons.append("Thiếu lời giải (\\loigiai).")
    if require_solution_and_answer:
        if q.qtype == "TN" and sum(q.correct) != 1:
            if not any("TN_TRUE_COUNT" == e.code for e in errors):
                reasons.append("Câu TN chưa có đúng 1 đáp án \\True.")
        elif q.qtype == "DS" and len(q.choices) != 4:
            if not any("DS_NOT4" == e.code for e in errors):
                reasons.append("Câu ĐS chưa đủ 4 phát biểu.")
        elif q.qtype == "KQ" and not q.short_ans.strip():
            if not any("KQ_EMPTY" == e.code for e in errors):
                reasons.append("Câu KQ chưa có đáp số.")

    if reasons:
        return False, " | ".join(reasons)
    return True, "Đủ lời giải & đáp án hợp lệ"
