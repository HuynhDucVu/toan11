"""Gợi ý ID cho câu chưa có ID bằng cách tìm các câu giống nội dung nhất trong kho (TF-IDF + cosine).

Chỉ gợi ý – giáo viên duyệt rồi mới gán. Kho càng nhiều câu có ID thì gợi ý càng đúng.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from .idcode import parse_id
from .parser import Question

WORD_RE = re.compile(r"\\[A-Za-z]+|[A-Za-zÀ-ỹà-ỹĐđ]+", re.UNICODE)
STOP = {"của", "và", "là", "có", "cho", "các", "một", "những", "trong", "với", "được", "ta", "thì", "này",
        "đó", "bằng", "khi", "để", "theo", "tại", "trên", "sau", "đây", "nào", "bao", "nhiêu", "nếu",
        "\\left", "\\right", "\\dfrac", "\\frac", "\\cdot", "\\displaystyle", "\\colon", "\\in", "\\mathrm"}


# chuẩn hoá cách bỏ dấu cũ/mới và vài từ đồng nghĩa hay gặp
_TONE = {"oà": "òa", "oá": "óa", "oả": "ỏa", "oã": "õa", "oạ": "ọa", "oè": "òe", "oé": "óe", "oẻ": "ỏe",
         "oẽ": "õe", "oẹ": "ọe", "uỳ": "ùy", "uý": "úy", "uỷ": "ủy", "uỹ": "ũy", "uỵ": "ụy"}
_SYN = {"niu": "newton", "tơn": "", "vectơ": "vecto", "véc": "vecto", "tơ": "", "véctơ": "vecto",
        "ellipse": "elip", "elíp": "elip", "parabol": "parabol", "hypebol": "hypebol", "hyperbol": "hypebol",
        "xúc": "xúc", "súc": "xúc"}


def _norm_word(w: str) -> str:
    w = w.lower()
    for a, b in _TONE.items():
        w = w.replace(a, b)
    return _SYN.get(w, w)


def tokens(text: str) -> Counter:
    words = [_norm_word(w) for w in WORD_RE.findall(text)]
    words = [w for w in words if w and w not in STOP and len(w) > 1]
    c = Counter(words)
    c.update(f"{a}_{b}" for a, b in zip(words, words[1:]))      # cụm 2 từ: «tập_nghiệm», «tiêu_cự»
    return c


def question_text(q: Question) -> str:
    return q.stem + " " + " ".join(q.choices)


@dataclass
class Suggestion:
    id_code: str
    score: float          # 0..1
    db_id: int | None     # câu mẫu giống nhất
    sample: str           # đoạn đề của câu mẫu


class Suggester:
    def __init__(self, questions: list[Question]):
        self.items = [q for q in questions if q.id_code and parse_id(q.id_code)]
        df = Counter()
        vecs = []
        for q in self.items:
            t = tokens(question_text(q))
            vecs.append(t)
            df.update(t.keys())
        n = max(len(self.items), 1)
        self.idf = {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}
        self.default_idf = math.log(n + 1)
        self.index = defaultdict(list)          # từ → [(chỉ số câu, trọng số)]
        self.norms = []
        for i, t in enumerate(vecs):
            w = {k: v * self.idf[k] for k, v in t.items()}
            norm = math.sqrt(sum(x * x for x in w.values())) or 1.0
            self.norms.append(norm)
            for k, x in w.items():
                self.index[k].append((i, x))

    def __len__(self):
        return len(self.items)

    def suggest(self, q: Question, k: int = 3, exclude_db_id: int | None = None) -> list[Suggestion]:
        t = tokens(question_text(q))
        qw = {w: c * self.idf.get(w, self.default_idf) for w, c in t.items()}
        qn = math.sqrt(sum(x * x for x in qw.values())) or 1.0
        scores = defaultdict(float)
        for w, x in qw.items():
            for i, y in self.index.get(w, ()):
                scores[i] += x * y
        ranked = sorted(((s / (qn * self.norms[i]), i) for i, s in scores.items()), reverse=True)
        out, seen = [], set()
        for sc, i in ranked:
            cand = self.items[i]
            if exclude_db_id is not None and cand.db_id == exclude_db_id:
                continue
            if cand.qtype != q.qtype and len(out) == 0 and any(self.items[j].qtype == q.qtype for _, j in ranked[:10]):
                continue                                  # ưu tiên câu cùng loại ở vị trí đầu
            code = cand.id_code
            if code in seen:
                continue
            seen.add(code)
            out.append(Suggestion(code, round(min(sc, 1.0), 3), cand.db_id, " ".join(cand.stem.split())[:120]))
            if len(out) >= k:
                break
        return out


class MapSuggester:
    """Gợi ý theo tên chương/bài/dạng trong Map ID – dùng được cả khi kho chưa có câu nào.

    Mỗi dạng (khoá có '-') là một «tài liệu» gồm tên chương + tên bài + tên dạng.
    prefix: giới hạn phạm vi, vd '0' (lớp 10), '2D' (Giải tích 12).
    """

    def __init__(self, mapping: dict[str, str], prefix: str = ""):
        from .idmap import split_key
        self.docs = []
        for k, name in mapping.items():
            if k.startswith("#") or "-" not in k or not k.upper().startswith(prefix.upper()):
                continue
            parts = split_key(k)
            ch = mapping.get("".join(parts[:3]), "")
            bai = mapping.get("".join(parts[:4]), "")
            t = tokens(f"{ch} {bai} {bai} {name} {name} {name}")
            self.docs.append((parts, t, f"{ch} › {bai} › {name}"))
        df = Counter()
        for _, t, _ in self.docs:
            df.update(t.keys())
        n = max(len(self.docs), 1)
        self.idf = {w: math.log((n + 1) / (c + 0.5)) for w, c in df.items()}
        self.vecs = []
        for parts, t, label in self.docs:
            w = {k: v * self.idf[k] for k, v in t.items()}
            self.vecs.append((parts, w, math.sqrt(sum(x * x for x in w.values())) or 1.0, label))

    def __len__(self):
        return len(self.docs)

    def suggest(self, q: Question, level: str = "N", k: int = 3) -> list[Suggestion]:
        t = tokens(question_text(q) + " " + q.solution[:300])
        qw = {w: c * self.idf[w] for w, c in t.items() if w in self.idf and not w.startswith("\\")}
        qn = math.sqrt(sum(x * x for x in qw.values())) or 1.0
        res = []
        for parts, w, norm, label in self.vecs:
            s = sum(x * w.get(t_, 0.0) for t_, x in qw.items())
            if s > 0:
                res.append((s / (qn * norm), parts, label))
        res.sort(key=lambda r: -r[0])
        out = []
        for sc, parts, label in res[:k]:
            code = "".join(parts[:3]) + level + parts[3] + "-" + parts[4]
            out.append(Suggestion(code, round(min(sc, 1.0), 3), None, label))
        return out


def combine(bank_sugs: list[Suggestion], map_sugs: list[Suggestion], k: int = 3) -> list[Suggestion]:
    """Gộp 2 nguồn: câu giống trong kho có độ tin cao hơn khi điểm cao; còn lại xếp theo điểm."""
    pool = [(s.score * 1.0, s) for s in bank_sugs] + [(s.score * 0.8, s) for s in map_sugs]
    pool.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for _, s in pool:
        key = s.id_code[:3] + s.id_code[4:]          # bỏ mức độ khi so trùng
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= k:
            break
    return out
