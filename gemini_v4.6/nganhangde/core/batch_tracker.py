import json
from typing import Sequence
from .db import QuestionBankDB
from .generator import ExamVariant
from .matrix_cv7991 import ExamMatrix


def record_exam_batch(
    db: QuestionBankDB, batch_name: str, seed: int, variants: Sequence[ExamVariant],
    matrix: ExamMatrix | None = None, online_url: str = "",
) -> int:
    m_payload = {"name": matrix.name, "part_points": matrix.part_points} if matrix else {}
    cur = db.conn.execute(
        "INSERT INTO exam_batches (name, seed, matrix_json, codes_json, online_url) VALUES (?,?,?,?,?)",
        (batch_name, seed, json.dumps(m_payload, ensure_ascii=False), json.dumps([v.code for v in variants]), online_url),
    )
    batch_id = cur.lastrowid
    for fp in {q.fingerprint() for v in variants for q in v.questions}:
        row = db.conn.execute("SELECT id FROM questions WHERE fingerprint = ?", (fp,)).fetchone()
        if row:
            db.conn.execute("INSERT OR IGNORE INTO exam_items (batch_id, question_id) VALUES (?,?)", (batch_id, row["id"]))
            db.conn.execute("UPDATE questions SET used_count = used_count + 1 WHERE id = ?", (row["id"],))
    db.conn.commit()
    return batch_id


def list_exam_batches(db: QuestionBankDB, limit: int = 50) -> list[dict]:
    rows = db.conn.execute(
        "SELECT b.id, b.name, b.seed, b.codes_json, b.online_url, b.created_at, COUNT(i.question_id) AS qcnt "
        "FROM exam_batches b LEFT JOIN exam_items i ON i.batch_id=b.id GROUP BY b.id ORDER BY b.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [{"id": r["id"], "name": r["name"], "seed": r["seed"], "codes": json.loads(r["codes_json"] or "[]"), "question_count": r["qcnt"]} for r in rows]
