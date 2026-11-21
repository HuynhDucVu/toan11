import copy
import random
import re
from dataclasses import dataclass, field
from .db import QuestionBankDB
from .matrix_cv7991 import ExamMatrix
from .parser import Question, parse_tex_questions
from .texutil import normalize_short_ans

LEVEL_RANK = {"N": 0, "H": 1, "V": 2, "C": 3, "": 4}
CHOOSE_LETTER_RE = re.compile(r"((?:Chọn\s*(?:đáp\s*án\s*)?|Đáp\s*án\s+)(?:\\textbf\{|\\mathrm\{)?)[A-D](\}?)")


@dataclass
class ExamVariant:
    code: str
    seed: int
    questions: list[Question]
    key_tn: list[tuple[int, str]] = field(default_factory=list)
    key_ds: list[tuple[int, str]] = field(default_factory=list)
    key_kq: list[tuple[int, str]] = field(default_factory=list)


def _balanced_target_letters(n: int, rng: random.Random) -> list[int]:
    if n <= 0:
        return []
    base, rem = divmod(n, 4)
    extras = [0, 1, 2, 3]
    rng.shuffle(extras)
    pool = [0] * base + [1] * base + [2] * base + [3] * base + extras[:rem]
    best = list(pool)
    for _ in range(40):
        rng.shuffle(pool)
        ok, run = True, 1
        for i in range(1, len(pool)):
            if pool[i] == pool[i - 1]:
                run += 1
                if run > 3:
                    ok = False
                    break
            else:
                run = 1
        if ok:
            return pool
        best = list(pool)
    return best


def _sync_tn_solution_letter(solution: str, new_letter: str) -> str:
    if not solution or new_letter not in "ABCD":
        return solution
    return CHOOSE_LETTER_RE.sub(rf"\g<1>{new_letter}\g<2>", solution)


def _reorder_itemchoice(solution: str, perm: list[int]) -> tuple[str, bool]:
    if not solution.strip():
        return solution, True
    env_m = re.search(r"(\\begin\{itemchoice\})(.*?)(\\end\{itemchoice\})", solution, flags=re.DOTALL)
    if env_m:
        body = env_m.group(2)
        parts = re.split(r"(?=\\itemch(?![a-zA-Z]))", body)
        prefix = parts[0] if parts and not parts[0].lstrip().startswith(r"\itemch") else ""
        items = [p for p in parts if p.lstrip().startswith(r"\itemch")]
        if len(items) != 4:
            return solution, False
        return solution[: env_m.start(2)] + prefix + "".join(items[i] for i in perm) + solution[env_m.end(2) :], True
    if r"\itemch" in solution:
        parts = re.split(r"(?=\\itemch(?![a-zA-Z]))", solution)
        prefix = parts[0] if parts and not parts[0].lstrip().startswith(r"\itemch") else ""
        items = [p for p in parts if p.lstrip().startswith(r"\itemch")]
        if len(items) != 4:
            return solution, False
        return prefix + "".join(items[i] for i in perm), True
    return solution, False


def _shuffle_preserving_groups(items: list[Question], rng: random.Random) -> list[Question]:
    blocks, group_map = [], {}
    for q in items:
        if q.group_id:
            if q.group_id not in group_map:
                grp: list[Question] = []
                group_map[q.group_id] = grp
                blocks.append(grp)
            group_map[q.group_id].append(q)
        else:
            blocks.append([q])
    rng.shuffle(blocks)
    return [q for blk in blocks for q in blk]


def shuffle_variant(
    base_questions: list[Question], exam_code: str, seed: int,
    shuffle_q: bool = True, shuffle_opt: bool = True, balance_abcd: bool = True, sort_by_level: bool = False,
) -> ExamVariant:
    rng = random.Random(seed)
    qs = [copy.deepcopy(q) for q in base_questions]
    by_type = {k: [q for q in qs if q.qtype == k] for k in ("TN", "DS", "KQ", "TL")}

    def order_sec(items):
        if not shuffle_q:
            return list(items)
        if sort_by_level:
            buckets: dict[int, list[Question]] = {}
            for q in items:
                info = q.id_info()
                buckets.setdefault(LEVEL_RANK.get(info.muc_do if info else "", 4), []).append(q)
            return [q for rk in sorted(buckets) for q in _shuffle_preserving_groups(buckets[rk], rng)]
        return _shuffle_preserving_groups(items, rng)

    tn_list, ds_list, kq_list, tl_list = order_sec(by_type["TN"]), order_sec(by_type["DS"]), order_sec(by_type["KQ"]), order_sec(by_type["TL"])
    variant = ExamVariant(code=exam_code, seed=seed, questions=[])
    unlocked = [i for i, q in enumerate(tn_list) if shuffle_opt and not q.lock_shuffle and len(q.choices) == 4 and sum(q.correct) == 1]
    target_map = dict(zip(unlocked, _balanced_target_letters(len(unlocked), rng))) if balance_abcd else {}

    for idx, q in enumerate(tn_list):
        if idx in target_map:
            true_old = q.correct.index(True)
            distractors = [i for i in range(4) if i != true_old]
            rng.shuffle(distractors)
            tpos = target_map[idx]
            perm = [0] * 4
            perm[tpos] = true_old
            d_it = iter(distractors)
            for pos in range(4):
                if pos != tpos:
                    perm[pos] = next(d_it)
            q.choices = [q.choices[i] for i in perm]
            q.correct = [q.correct[i] for i in perm]
        elif shuffle_opt and not q.lock_shuffle and len(q.choices) >= 2:
            perm = list(range(len(q.choices)))
            rng.shuffle(perm)
            q.choices = [q.choices[i] for i in perm]
            q.correct = [q.correct[i] for i in perm]
        ans = "ABCDE"[q.correct.index(True)] if True in q.correct else "?"
        if ans in "ABCD":
            q.solution = _sync_tn_solution_letter(q.solution, ans)
        variant.key_tn.append((idx + 1, ans))
        variant.questions.append(q)

    for idx, q in enumerate(ds_list):
        if shuffle_opt and not q.lock_shuffle and len(q.choices) == 4:
            perm = [0, 1, 2, 3]
            rng.shuffle(perm)
            new_sol, ok_re = _reorder_itemchoice(q.solution, perm)
            if ok_re:
                q.choices = [q.choices[i] for i in perm]
                q.correct = [q.correct[i] for i in perm]
                q.solution = new_sol
        variant.key_ds.append((idx + 1, "".join("Đ" if ok else "S" for ok in q.correct)))
        variant.questions.append(q)

    for idx, q in enumerate(kq_list):
        variant.key_kq.append((idx + 1, normalize_short_ans(q.short_ans)))
        variant.questions.append(q)

    variant.questions.extend(tl_list)
    return variant


def draw_questions_by_matrix(db: QuestionBankDB, matrix: ExamMatrix, seed: int, prefer_least_used: bool = True) -> list[Question]:
    rng = random.Random(seed)
    chosen_ids: set[int] = set()
    selected: list[Question] = []
    for idx, rule in enumerate(matrix.rules, 1):
        rows = db.search(id_glob=rule.id_glob, qtype=rule.qtype, muc_do=rule.muc_do, limit=5000)
        candidates = [r for r in rows if r["id"] not in chosen_ids]
        if len(candidates) < rule.count:
            raise ValueError(f"Dòng ma trận #{idx} ({rule.qtype}, ID='{rule.id_glob}') cần {rule.count} nhưng chỉ có {len(candidates)} câu.")
        rng.shuffle(candidates)
        if prefer_least_used:
            candidates.sort(key=lambda r: r["used_count"])
        for row in candidates[: rule.count]:
            chosen_ids.add(row["id"])
            parsed = parse_tex_questions(row["raw"])
            if parsed:
                selected.append(parsed[0])
    return selected


def generate_exam_codes(num_codes: int, digits: int = 4, start_code: int = 1001) -> list[str]:
    if digits == 3 and start_code >= 1000:
        start_code = 101
    return [str(start_code + i).zfill(digits) for i in range(num_codes)]


def generate_exam_batch(
    num_codes: int, seed: int = 2026, base_questions: list[Question] | None = None,
    db: QuestionBankDB | None = None, matrix: ExamMatrix | None = None, same_questions: bool = True,
    code_digits: int = 4, start_code: int = 1001, balance_abcd: bool = True, sort_by_level: bool = False,
) -> list[ExamVariant]:
    codes = generate_exam_codes(num_codes, digits=code_digits, start_code=start_code)
    if base_questions is None:
        if db is None or matrix is None:
            raise ValueError("Cần truyền base_questions hoặc cặp (db, matrix).")
        if same_questions:
            base_questions = draw_questions_by_matrix(db, matrix, seed=seed)
    variants = []
    for idx, code in enumerate(codes):
        v_seed = seed + idx * 97
        pool = base_questions if (same_questions or base_questions is not None) else draw_questions_by_matrix(db, matrix, seed=v_seed)
        variants.append(shuffle_variant(pool, exam_code=code, seed=v_seed, balance_abcd=balance_abcd, sort_by_level=sort_by_level))
    return variants
