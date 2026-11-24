import os
import re
from dataclasses import dataclass
from .parser import Question
from .texutil import normalize_short_ans

HARDCODED_CHOICE_RE = re.compile(r"(Chọn\s*(?:đáp\s*án\s*)?(?:\\textbf\{)?[A-D]\}?|Đáp\s*án\s+[A-D]\b)")
INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")


@dataclass
class AuditIssue:
    level: str
    code: str
    message: str


def validate_cv1239_shortans(raw_ans: str) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    norm = normalize_short_ans(raw_ans)
    if not norm:
        return [AuditIssue("ERROR", "KQ_EMPTY", "Thiếu đáp số trong \\shortans{...}.")]
    if "." in norm:
        issues.append(AuditIssue("ERROR", "KQ_DOT_DECIMAL", f"Đáp số '{norm}' dùng dấu '.'; theo CV 1239 phải dùng dấu ','."))
    if not re.fullmatch(r"-?[0-9]+(,[0-9]+)?", norm):
        issues.append(AuditIssue("ERROR", "KQ_INVALID_CHAR", f"Đáp số '{norm}' chứa ký tự ngoài '-', ',', '0-9'."))
    if len(norm) > 4:
        issues.append(AuditIssue("ERROR", "KQ_TOO_LONG", f"Đáp số '{norm}' dài {len(norm)} > 4 cột theo CV 1239."))
    return issues


def audit_question(q: Question, base_dir: str | None = None) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    if not q.ids:
        issues.append(AuditIssue("WARNING", "NO_ID", "Chưa gắn mã ID chuẩn."))
    raw_check = q.raw or q.to_latex(include_solution=True)
    cb = re.sub(r"\\[{}]", "", raw_check)
    if cb.count("{") != cb.count("}"):
        issues.append(AuditIssue("ERROR", "UNBALANCED_BRACE", "Lệch ngoặc nhọn { }."))
    if re.sub(r"\\\$", "", raw_check).count("$") % 2 != 0:
        issues.append(AuditIssue("ERROR", "ODD_DOLLAR", "Số dấu '$' bị lẻ."))
    if len(re.findall(r"\\left(?![a-zA-Z])", raw_check)) != len(re.findall(r"\\right(?![a-zA-Z])", raw_check)):
        issues.append(AuditIssue("ERROR", "LEFT_RIGHT_MISMATCH", "Lệch cặp \\left và \\right."))
    if len(re.findall(r"\\begin\{[^}]+\}", raw_check)) != len(re.findall(r"\\end\{[^}]+\}", raw_check)):
        issues.append(AuditIssue("ERROR", "ENV_MISMATCH", "Lệch cặp môi trường \\begin{...} / \\end{...}."))
    if q.qtype == "TN":
        if sum(q.correct) != 1:
            issues.append(AuditIssue("ERROR", "TN_TRUE_COUNT", f"Câu TN phải có đúng 1 \\True (hiện có {sum(q.correct)})."))
        if q.solution and HARDCODED_CHOICE_RE.search(q.solution):
            issues.append(AuditIssue("WARNING", "HARDCODED_LETTER", "Lời giải có 'Chọn A/B/C/D' cứng."))
    elif q.qtype == "DS":
        if len(q.choices) != 4:
            issues.append(AuditIssue("ERROR", "DS_NOT4", "Câu Đ/S phải có đủ 4 phát biểu."))
        if len(q.choices) == 4 and sum(q.correct) in (0, 4):
            issues.append(AuditIssue("WARNING", "DS_ALL_SAME", "Cả 4 ý Đ/S giống nhau — cần rà soát."))
        if q.solution and len(re.findall(r"\\itemch(?![a-zA-Z])", q.solution)) not in (0, 4):
            issues.append(AuditIssue("WARNING", "DS_ITEMCH_MISMATCH", "Số mục \\itemch trong lời giải khác 4."))
    elif q.qtype == "KQ":
        issues.extend(validate_cv1239_shortans(q.short_ans))
    if not q.solution.strip():
        issues.append(AuditIssue("WARNING", "NO_SOLUTION", "Chưa có \\loigiai{...}."))
    if base_dir:
        for img in INCLUDEGRAPHICS_RE.findall(raw_check):
            fp = img if os.path.isabs(img) else os.path.join(base_dir, img)
            if not os.path.exists(fp):
                issues.append(AuditIssue("ERROR", "MISSING_IMAGE", f"Thiếu tệp ảnh: {img}"))
    return issues
