"""Xuất đề trắc nghiệm chuẩn Aiken format để nhập nhanh vào Moodle (như MyLT v1.0.2.54)."""
from pathlib import Path
from typing import Sequence
from ..core.parser import Question


def export_aiken_txt(questions: Sequence[Question], out_txt: str) -> str:
    blocks: list[str] = []
    for q in questions:
        if q.qtype != "TN" or len(q.choices) < 2 or True not in q.correct:
            continue
        stem_1line = " ".join(q.stem.split())
        lines = [stem_1line]
        for idx, ch in enumerate(q.choices[:5]):
            lines.append(f"{'ABCDE'[idx]}. {' '.join(ch.split())}")
        ans_letter = "ABCDE"[q.correct.index(True)]
        lines.append(f"ANSWER: {ans_letter}")
        blocks.append("\n".join(lines))
    content = "\n\n".join(blocks) + "\n"
    Path(out_txt).write_text(content, encoding="utf-8")
    return out_txt
