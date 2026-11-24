from pathlib import Path
import hashlib
import re
from dataclasses import dataclass, field
from .idcode import extract_ids_and_tags, parse_id
from .texutil import normalize_math_symbols, normalize_short_ans, read_group, read_opt_and_args

LOCK_RE = re.compile(
    r"(cả\s+(hai|ba|a|b|c|2|3)|a\s*,\s*b\s*đều|tất\s+cả\s+(các\s+)?(đáp\s+án|phương\s+án)?\s*(trên\s+)?(đều\s+)?(đúng|sai)|đáp\s+án\s+khác|%no-shuffle|\\choice\*)",
    re.IGNORECASE,
)
ENV_BLOCK_RE = re.compile(r"(?P<header>(?:%\[[^\]]+\][ \t]*\r?\n?)*)\\begin\{(?P<env>ex|bt|vd)\}(?P<body>.*?)\\end\{(?P=env)\}", re.DOTALL)
CMD_CHOICE_TF_RE = re.compile(r"\\(choiceTFt|choiceTF)(?![a-zA-Z])")
CMD_CHOICE_RE = re.compile(r"\\(choice\*?)(?![a-zA-Z])")
CMD_SHORTANS_RE = re.compile(r"\\(shortans|dapso)(?![a-zA-Z])")
CMD_MATCH_RE = re.compile(r"\\(match)(?![a-zA-Z])")


@dataclass
class Question:
    qtype: str
    stem: str
    choices: list[str] = field(default_factory=list)
    correct: list[bool] = field(default_factory=list)
    short_ans: str = ""
    solution: str = ""
    ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    env_name: str = "ex"
    cmd_name: str = ""
    cmd_opt: str = ""
    lock_shuffle: bool = False
    group_id: str | None = None
    raw: str = ""

    @property
    def primary_id(self) -> str:
        return self.ids[0] if self.ids else ""

    def id_info(self):
        return parse_id(self.primary_id) if self.primary_id else None

    def fingerprint(self) -> str:
        s = self.stem + "".join(self.choices) + normalize_short_ans(self.short_ans)
        s = re.sub(r"\\(left|right)", "", s)
        s = s.replace(r"\dfrac", "frac").replace(r"\tfrac", "frac").replace(r"\frac", "frac")
        s = re.sub(r"[\s\$\{\}]", "", s).lower()
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def to_latex(self, include_solution: bool = True) -> str:
        header_parts = [f"%[{qid}]" for qid in self.ids] + [f"%[{t}]" for t in self.tags]
        if self.group_id:
            header_parts.append(f"%[group:{self.group_id}]")
        lines = ["".join(header_parts)] if header_parts else []
        lines.append(f"\\begin{{{self.env_name}}}")
        lines.append(self.stem.strip())
        opt_str = f"[{self.cmd_opt}]" if self.cmd_opt else ""
        if self.qtype in ("TN", "DS"):
            default_cmd = "choice" if self.qtype == "TN" else "choiceTF"
            lines.append(f"\\{self.cmd_name or default_cmd}{opt_str}")
            for ch, is_ok in zip(self.choices, self.correct):
                prefix = "\\True " if is_ok else ""
                lines.append(f"\t{{{prefix}{ch}}}")
        elif self.qtype == "KQ":
            lines.append(f"\\{self.cmd_name or 'shortans'}{opt_str}{{{self.short_ans}}}")
        elif self.qtype == "GN":
            lines.append(f"\\{self.cmd_name or 'match'}{opt_str}" + "".join(f"{{{ch}}}" for ch in self.choices))
        if include_solution and self.solution.strip():
            lines.append(f"\\loigiai{{\n{self.solution.strip()}\n}}")
        lines.append(f"\\end{{{self.env_name}}}")
        return "\n".join(lines)


def _strip_true(option_text: str) -> tuple[str, bool]:
    is_true = bool(re.search(r"\\True(?![a-zA-Z])", option_text))
    return re.sub(r"\\True\s*", "", option_text, count=1).strip(), is_true


def _extract_loigiai(body: str) -> tuple[str, str]:
    idx = body.find(r"\loigiai")
    if idx == -1:
        return body, ""
    brace = body.find("{", idx + len(r"\loigiai"))
    if brace == -1:
        return body, ""
    sol, end_pos = read_group(body, brace)
    if sol is None:
        return body, ""
    return body[:idx] + body[end_pos:], sol.strip()


def parse_tex_questions(tex_text: str, auto_normalize: bool = False) -> list[Question]:
    if auto_normalize:
        tex_text = normalize_math_symbols(tex_text)
    questions: list[Question] = []
    for m in ENV_BLOCK_RE.finditer(tex_text):
        header, env, body, raw = m.group("header") or "", m.group("env"), m.group("body"), m.group(0)
        ids, tags = extract_ids_and_tags(header + "\n" + "\n".join(body.splitlines()[:3]))
        group_id, clean_tags = None, []
        for t in tags:
            if t.lower().startswith("group:"):
                group_id = t.split(":", 1)[1].strip()
            else:
                clean_tags.append(t)
        body_wo_sol, solution = _extract_loigiai(body)
        body_clean = re.sub(r"^\s*(?:%\[[^\]]+\][ \t]*\r?\n)+", "", body_wo_sol)
        lock = bool(LOCK_RE.search(body_clean))

        m_tf, m_ch = CMD_CHOICE_TF_RE.search(body_clean), CMD_CHOICE_RE.search(body_clean)
        m_sa, m_mt = CMD_SHORTANS_RE.search(body_clean), CMD_MATCH_RE.search(body_clean)
        if m_tf:
            opt, args, _ = read_opt_and_args(body_clean, m_tf.end(), max_args=4)
            pairs = [_strip_true(a) for a in args]
            questions.append(Question("DS", body_clean[: m_tf.start()].strip(), [p[0] for p in pairs], [p[1] for p in pairs], "", solution, ids, clean_tags, env, m_tf.group(1), opt, lock, group_id, raw))
        elif m_ch:
            opt, args, _ = read_opt_and_args(body_clean, m_ch.end(), max_args=5)
            pairs = [_strip_true(a) for a in args]
            questions.append(Question("TN", body_clean[: m_ch.start()].strip(), [p[0] for p in pairs], [p[1] for p in pairs], "", solution, ids, clean_tags, env, m_ch.group(1), opt, lock, group_id, raw))
        elif m_sa:
            opt, args, _ = read_opt_and_args(body_clean, m_sa.end(), max_args=1)
            questions.append(Question("KQ", body_clean[: m_sa.start()].strip(), [], [], args[0].strip() if args else "", solution, ids, clean_tags, env, m_sa.group(1), opt, True, group_id, raw))
        elif m_mt:
            opt, args, _ = read_opt_and_args(body_clean, m_mt.end(), max_args=8)
            questions.append(Question("GN", body_clean[: m_mt.start()].strip(), args, [], "", solution, ids, clean_tags, env, m_mt.group(1), opt, True, group_id, raw))
        else:
            questions.append(Question("TL", body_clean.strip(), [], [], "", solution, ids, clean_tags, env, "", "", True, group_id, raw))
    return questions


INPUT_CMD_RE = re.compile(r"\\(?:input|include)\s*\{([^}]+)\}")


def read_tex_with_inputs(tex_path: str | Path, _visited: set[Path] | None = None) -> str:
    """Đọc tệp .tex và tự động nạp đệ quy các tệp con trong \\input{...} / \\include{...} (hỗ trợ main.tex)."""
    p = Path(tex_path).resolve()
    if _visited is None:
        _visited = set()
    if p in _visited or not p.exists():
        return ""
    _visited.add(p)
    text = p.read_text(encoding="utf-8", errors="replace")

    def _repl(m: re.Match) -> str:
        rel = m.group(1).strip()
        cand = (p.parent / rel)
        if not cand.exists() and cand.suffix.lower() != ".tex":
            cand = cand.with_suffix(".tex")
        if cand.exists() and cand.is_file():
            return "\n" + read_tex_with_inputs(cand, _visited) + "\n"
        return m.group(0)

    return INPUT_CMD_RE.sub(_repl, text)
