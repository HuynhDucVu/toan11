"""Lưu ngân hàng câu hỏi trong SQLite (1 file .db, không cần cài server)."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from .idcode import parse_id
from .parser import Question

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    qtype       TEXT NOT NULL,           -- TN / DS / KQ / TL
    id_code     TEXT DEFAULT '',         -- 0D2N1-2
    lop         TEXT DEFAULT '',
    mon         TEXT DEFAULT '',
    chuong      TEXT DEFAULT '',
    muc_do      TEXT DEFAULT '',         -- N/H/V/C
    bai         TEXT DEFAULT '',
    dang        TEXT DEFAULT '',
    env         TEXT DEFAULT 'ex',
    stem        TEXT NOT NULL,
    choices     TEXT DEFAULT '[]',       -- JSON
    correct     TEXT DEFAULT '[]',       -- JSON
    short_answer TEXT DEFAULT '',
    choice_opt  TEXT DEFAULT '',
    solution    TEXT DEFAULT '',
    tags        TEXT DEFAULT '[]',       -- JSON: nguồn, tác giả...
    raw         TEXT DEFAULT '',
    fingerprint TEXT UNIQUE,
    source_file TEXT DEFAULT '',
    used_count  INTEGER DEFAULT 0,       -- số lần đã đưa vào đề
    created_at  TEXT
);
CREATE INDEX IF NOT EXISTS ix_q_code ON questions(id_code);
CREATE INDEX IF NOT EXISTS ix_q_filter ON questions(qtype, lop, chuong, muc_do);
"""


class Bank:
    def __init__(self, path: str = "nganhang.db"):
        self.path = path
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)

    def close(self):
        self.con.close()

    # ---------- ghi ----------
    def _row_values(self, q: Question):
        idc = parse_id(q.id_code) if q.id_code else None
        return dict(
            qtype=q.qtype, id_code=q.id_code,
            lop=idc.lop if idc else "", mon=idc.mon if idc else "",
            chuong=idc.chuong if idc else "", muc_do=idc.muc_do if idc else "",
            bai=idc.bai if idc else "", dang=idc.dang if idc else "",
            env=q.env, stem=q.stem,
            choices=json.dumps(q.choices, ensure_ascii=False),
            correct=json.dumps(q.correct), short_answer=q.short_answer,
            choice_opt=q.choice_opt, solution=q.solution,
            tags=json.dumps(q.tags, ensure_ascii=False), raw=q.raw or q.to_latex(),
            fingerprint=q.fingerprint,
        )

    def add(self, q: Question, source_file: str = "") -> int | None:
        """Thêm câu; trả về id mới, hoặc None nếu câu đã tồn tại (trùng)."""
        v = self._row_values(q)
        v["source_file"] = source_file
        v["created_at"] = datetime.now().isoformat(timespec="seconds")
        cols = ",".join(v)
        try:
            cur = self.con.execute(
                f"INSERT INTO questions ({cols}) VALUES ({','.join('?' * len(v))})",
                list(v.values()))
        except sqlite3.IntegrityError:
            return None
        self.con.commit()
        return cur.lastrowid

    def update(self, db_id: int, q: Question):
        v = self._row_values(q)
        sets = ",".join(f"{k}=?" for k in v)
        self.con.execute(f"UPDATE questions SET {sets} WHERE id=?", [*v.values(), db_id])
        self.con.commit()

    def delete(self, ids):
        self.con.executemany("DELETE FROM questions WHERE id=?", [(i,) for i in ids])
        self.con.commit()

    def mark_used(self, ids):
        self.con.executemany("UPDATE questions SET used_count=used_count+1 WHERE id=?",
                             [(i,) for i in ids])
        self.con.commit()

    def find_duplicate(self, q: Question):
        r = self.con.execute("SELECT id FROM questions WHERE fingerprint=?",
                             (q.fingerprint,)).fetchone()
        return r["id"] if r else None

    # ---------- đọc ----------
    @staticmethod
    def row_to_question(r) -> Question:
        q = Question(
            qtype=r["qtype"], stem=r["stem"], choices=json.loads(r["choices"]),
            correct=json.loads(r["correct"]), short_answer=r["short_answer"],
            choice_opt=r["choice_opt"], solution=r["solution"], id_code=r["id_code"],
            tags=json.loads(r["tags"]), env=r["env"], raw=r["raw"])
        q.db_id = r["id"]
        return q

    def get(self, db_id: int) -> Question | None:
        r = self.con.execute("SELECT * FROM questions WHERE id=?", (db_id,)).fetchone()
        return self.row_to_question(r) if r else None

    def search(self, qtype=None, lop=None, mon=None, chuong=None, muc_do=None,
               bai=None, dang=None, id_like=None, text=None, limit=None):
        """Lọc câu hỏi. id_like hỗ trợ kí tự đại diện * và ? (vd 0D2?1-*)."""
        sql, args = "SELECT * FROM questions WHERE 1=1", []
        for col, val in (("qtype", qtype), ("lop", lop), ("mon", mon), ("chuong", chuong),
                         ("muc_do", muc_do), ("bai", bai), ("dang", dang)):
            if val:
                sql += f" AND {col}=?"
                args.append(val)
        if id_like:
            sql += " AND id_code GLOB ?"
            args.append(id_like.upper())
        if text:
            sql += " AND (stem LIKE ? OR solution LIKE ? OR tags LIKE ?)"
            args += [f"%{text}%"] * 3
        sql += " ORDER BY id_code, id"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [self.row_to_question(r) for r in self.con.execute(sql, args)]

    def stats(self):
        """Thống kê số câu theo (lớp, chương, loại, mức độ)."""
        return self.con.execute(
            "SELECT lop, mon, chuong, qtype, muc_do, COUNT(*) AS n FROM questions "
            "GROUP BY lop, mon, chuong, qtype, muc_do ORDER BY lop, mon, chuong, qtype, muc_do"
        ).fetchall()

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
