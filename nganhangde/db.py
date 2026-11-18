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
-- Giải nghĩa ID (MapID): '0D2' → 'Chương 2. Bất phương trình', '0D21' → 'Bài 1 ...', '0D21-2' → 'Dạng 2 ...'
-- Lịch sử sửa/xoá câu: lưu khối LaTeX trước khi đổi để khôi phục
CREATE TABLE IF NOT EXISTS history (
    hid         INTEGER PRIMARY KEY AUTOINCREMENT,
    question_id INTEGER,
    at          TEXT,
    action      TEXT,            -- sửa / xoá / thay thế / gán ID
    old_raw     TEXT
);
CREATE INDEX IF NOT EXISTS ix_hist_q ON history(question_id);
CREATE TABLE IF NOT EXISTS idmap (
    key  TEXT PRIMARY KEY,
    name TEXT NOT NULL
);
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

    def _log(self, db_id: int, action: str):
        r = self.con.execute("SELECT raw FROM questions WHERE id=?", (db_id,)).fetchone()
        if r:
            self.con.execute("INSERT INTO history(question_id, at, action, old_raw) VALUES (?,?,?,?)",
                             (db_id, datetime.now().isoformat(timespec="seconds"), action, r["raw"]))

    def history(self, db_id: int):
        return self.con.execute("SELECT hid, at, action, old_raw FROM history WHERE question_id=? "
                                "ORDER BY hid DESC", (db_id,)).fetchall()

    def restore(self, hid: int) -> int | None:
        """Khôi phục câu về bản đã lưu trong lịch sử (kể cả câu đã xoá). Trả về id câu."""
        from .parser import parse_tex
        r = self.con.execute("SELECT question_id, old_raw FROM history WHERE hid=?", (hid,)).fetchone()
        if not r:
            return None
        qs = parse_tex(r["old_raw"])
        if not qs:
            return None
        q = qs[0]
        q.raw = r["old_raw"]
        if self.get(r["question_id"]):
            self.update(r["question_id"], q, action="khôi phục")
            return r["question_id"]
        return self.add(q, "khoi-phuc") or self.find_duplicate(q)

    def update(self, db_id: int, q: Question, action: str = "sửa"):
        self._log(db_id, action)
        v = self._row_values(q)
        sets = ",".join(f"{k}=?" for k in v)
        self.con.execute(f"UPDATE questions SET {sets} WHERE id=?", [*v.values(), db_id])
        self.con.commit()

    def delete(self, ids):
        for i in ids:
            self._log(i, "xoá")
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

    def replace_text(self, find: str, repl: str, ids=None, regex: bool = False,
                     fields=("stem", "choices", "solution")) -> int:
        """Tìm và thay thế trong đề bài / phương án / lời giải. Trả về số câu đã đổi."""
        import re as _re
        pat = _re.compile(find) if regex else None

        def sub(t):
            return pat.sub(repl, t) if pat else t.replace(find, repl)
        n = 0
        targets = [self.get(i) for i in ids] if ids is not None else self.search()
        for q in targets:
            if q is None:
                continue
            new_stem = sub(q.stem) if "stem" in fields else q.stem
            new_ch = [sub(c) for c in q.choices] if "choices" in fields else q.choices
            new_sol = sub(q.solution) if "solution" in fields else q.solution
            new_kq = sub(q.short_answer) if "choices" in fields else q.short_answer
            if (new_stem, new_ch, new_sol, new_kq) != (q.stem, q.choices, q.solution, q.short_answer):
                q.stem, q.choices, q.solution, q.short_answer = new_stem, new_ch, new_sol, new_kq
                q.raw = q.to_latex()
                self.update(q.db_id, q, action="thay thế")
                n += 1
        return n

    def search(self, qtype=None, lop=None, mon=None, chuong=None, muc_do=None,
               bai=None, dang=None, id_like=None, text=None, limit=None, tag=None):
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
        if tag:
            sql += " AND tags LIKE ?"
            args.append(f"%{tag}%")
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

    # ---------- câu tương tự ----------
    def similar(self, q: Question, same_level: bool = True) -> list[Question]:
        """Câu cùng dạng (cùng ID bỏ qua mức độ nếu same_level=False), cùng loại câu."""
        idc = parse_id(q.id_code) if q.id_code else None
        if not idc:
            return []
        pat = idc.lop + idc.mon + idc.chuong + ("?" if not same_level else q.id_code[3]) + idc.bai
        pat += ("-" + idc.dang) if idc.dang else "*"
        return [x for x in self.search(qtype=q.qtype, id_like=pat) if x.db_id != q.db_id]

    # ---------- giải nghĩa ID ----------
    def idmap(self) -> dict[str, str]:
        return dict(self.con.execute("SELECT key, name FROM idmap ORDER BY key").fetchall())

    def set_idmap(self, mapping: dict[str, str], replace: bool = False):
        if replace:
            self.con.execute("DELETE FROM idmap")
        self.con.executemany("INSERT OR REPLACE INTO idmap(key, name) VALUES (?, ?)",
                             [(k.upper(), v) for k, v in mapping.items() if k.strip() and v.strip()])
        self.con.commit()

    def id_names(self, code: str) -> list[str]:
        """Các tên giải nghĩa từ khái quát đến chi tiết cho một ID, vd ['Chương 2 ...', 'Bài 1 ...']."""
        idc = parse_id(code) if code else None
        if not idc:
            return []
        m = self.idmap()
        keys = [idc.lop, idc.lop + idc.mon, idc.lop + idc.mon + idc.chuong,
                idc.lop + idc.mon + idc.chuong + idc.bai]
        if idc.dang:
            keys.append(keys[-1] + "-" + idc.dang)
        return [m[k] for k in keys if k in m]

    # ---------- sao lưu / gộp / tách ----------
    def backup(self, dest: str):
        """Sao lưu toàn bộ kho sang file .db khác (an toàn cả khi đang mở)."""
        out = sqlite3.connect(dest)
        with out:
            self.con.backup(out)
        out.close()

    def merge_from(self, other_path: str) -> tuple[int, int]:
        """Gộp câu hỏi (và giải nghĩa ID) từ kho khác; trả về (thêm, trùng)."""
        other = Bank(other_path)
        added = dup = 0
        try:
            for r in other.con.execute("SELECT * FROM questions"):
                if self.add(other.row_to_question(r), r["source_file"]):
                    added += 1
                else:
                    dup += 1
            self.set_idmap(other.idmap())
        finally:
            other.close()
        return added, dup

    def export_subset(self, ids, dest: str) -> int:
        """Tách các câu đã chọn ra một kho mới."""
        out = Bank(dest)
        n = sum(1 for i in ids if (q := self.get(i)) and out.add(q, "tach-kho"))
        out.set_idmap(self.idmap())
        out.close()
        return n

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
