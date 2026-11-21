import re
from typing import Sequence
from .texutil import strip_accents_vi


def _shingles(text: str, k: int = 3) -> set[str]:
    norm = strip_accents_vi(text or "").lower()
    norm = norm.replace(r"\dfrac", "frac").replace(r"\frac", "frac")
    norm = re.sub(r"[^a-z0-9]+", " ", norm).strip()
    words = norm.split()
    if len(words) < k:
        return set(words)
    return {" ".join(words[i : i + k]) for i in range(len(words) - k + 1)}


def jaccard_similarity(text_a: str, text_b: str) -> float:
    sa, sb = _shingles(text_a), _shingles(text_b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def find_similar_questions(
    query_stem: str,
    candidates: Sequence[dict],
    threshold: float = 0.35,
    top_k: int = 10,
) -> list[tuple[float, dict]]:
    """Tìm câu hỏi tương tự/gần trùng trong ngân hàng dựa trên Jaccard trigram không dấu."""
    scored: list[tuple[float, dict]] = []
    for item in candidates:
        sim = jaccard_similarity(query_stem, item.get("stem", ""))
        if sim >= threshold:
            scored.append((round(sim, 4), item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]
