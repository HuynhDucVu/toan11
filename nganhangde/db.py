"""Lưu ngân hàng câu hỏi trong SQLite (1 file .db, không cần cài server)."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime

from .idcode import parse_id
from .parser import Question
from .textnorm import search_text

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


SCHEMA_VERSION = 2


def _migrate_v2(con, fts_ok: bool):
    """v1 (≤ 0.10) → v2: tên lệnh gốc, câu chùm, chỉ mục tìm kiếm không dấu (FTS5), tài sản, lịch sử ra đề."""
    cols = {r[1] for r in con.execute("PRAGMA table_info(questions)")}
    for col, decl in (("choice_cmd", "TEXT DEFAULT ''"), ("group_id", "TEXT DEFAULT ''"),
                      ("search_text", "TEXT DEFAULT ''")):
        if col not in cols:
            con.execute(f"ALTER TABLE questions ADD COLUMN {col} {decl}")
    con.executescript("""
        CREATE INDEX IF NOT EXISTS ix_q_group ON questions(group_id);
        -- ảnh/hình đi kèm câu hỏi (đường dẫn tương đối, mã băm) – chép theo khi xuất đề
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER, path TEXT, sha1 TEXT, data BLOB
        );
        CREATE INDEX IF NOT EXISTS ix_assets_q ON assets(question_id);
        -- lịch sử các đợt ra đề: tái lập được bộ đề cũ, tránh lặp câu giữa các bài kiểm tra
        CREATE TABLE IF NOT EXISTS exam_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, ten_de TEXT, seed TEXT, matrix TEXT,
            codes TEXT, out_dir TEXT, note TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS exam_items (
            batch_id INTEGER, code TEXT, part TEXT, pos INTEGER, question_id INTEGER
        );
        CREATE INDEX IF NOT EXISTS ix_items_batch ON exam_items(batch_id);
        CREATE INDEX IF NOT EXISTS ix_items_q ON exam_items(question_id);
    """)
    rows = con.execute("SELECT id, stem, choices, solution, tags, short_answer FROM questions").fetchall()
    con.executemany("UPDATE questions SET search_text=? WHERE id=?",
                    [(search_text(r[1], " ".join(json.loads(r[2] or "[]")), r[3], " ".join(json.loads(r[4] or "[]")),
                                  r[5]), r[0]) for r in rows])
    con.executemany("UPDATE questions SET group_id=? WHERE id=?",
                    [(_group_of(json.loads(r[4] or "[]")), r[0]) for r in rows])
    if fts_ok:
        con.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS questions_fts USING fts5(
                search_text, content='questions', content_rowid='id', tokenize='unicode61');
            CREATE TRIGGER IF NOT EXISTS q_ai AFTER INSERT ON questions BEGIN
                INSERT INTO questions_fts(rowid, search_text) VALUES (new.id, new.search_text);
            END;
            CREATE TRIGGER IF NOT EXISTS q_ad AFTER DELETE ON questions BEGIN
                INSERT INTO questions_fts(questions_fts, rowid, search_text) VALUES ('delete', old.id, old.search_text);
            END;
            CREATE TRIGGER IF NOT EXISTS q_au AFTER UPDATE ON questions BEGIN
                INSERT INTO questions_fts(questions_fts, rowid, search_text) VALUES ('delete', old.id, old.search_text);
                INSERT INTO questions_fts(rowid, search_text) VALUES (new.id, new.search_text);
            END;
            INSERT INTO questions_fts(questions_fts) VALUES ('rebuild');
        """)


def _group_of(tags) -> str:
    """Câu chùm: nhãn %[chum:TEN] (các câu cùng TEN đi liền khối khi trộn)."""
    for t in tags:
        if t.lower().startswith("chum:"):
            return t.split(":", 1)[1].strip()
    return ""


def _fts5_available(con) -> bool:
    try:
        con.execute("CREATE VIRTUAL TABLE temp.__fts_probe USING fts5(x)")
        con.execute("DROP TABLE temp.__fts_probe")
        return True
    except sqlite3.OperationalError:
        return False


class Bank:
    def __init__(self, path: str = "nganhang.db"):
        self.path = path
        self.con = sqlite3.connect(path, check_same_thread=False)   # luồng nền (nhập/quét kho lớn) dùng khi hộp thoại chờ
        self.con.row_factory = sqlite3.Row
        self.migrated_from = None
        self._migrate()

    def _migrate(self):
        """Nâng cấp lược đồ theo PRAGMA user_version; kho cũ có dữ liệu ⇒ sao lưu .bak trước khi nâng cấp."""
        ver = self.con.execute("PRAGMA user_version").fetchone()[0]
        had_table = self.con.execute("SELECT 1 FROM sqlite_master WHERE name='questions'").fetchone() is not None
        self.con.executescript(SCHEMA)
        self.fts = _fts5_available(self.con)
        if ver >= SCHEMA_VERSION:
            self.fts = self.fts and self.con.execute(
                "SELECT 1 FROM sqlite_master WHERE name='questions_fts'").fetchone() is not None
            return
        if had_table and self.path != ":memory:" and os.path.exists(self.path):
            n = self.con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            if n:
                self.con.commit()
                bak = self.path + ".bak"
                out = sqlite3.connect(bak)
                with out:
                    self.con.backup(out)
                out.close()
                self.migrated_from = ver or 1
        with self.con:
            _migrate_v2(self.con, self.fts)
            self.con.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

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
            choice_opt=q.choice_opt, choice_cmd=q.choice_cmd, solution=q.solution,
            group_id=_group_of(q.tags),
            search_text=search_text(
                q.stem, " ".join(q.choices), q.solution, " ".join(q.tags), q.short_answer),
            tags=json.dumps(q.tags, ensure_ascii=False), raw=q.raw or q.to_latex(),
            fingerprint=q.fingerprint,
        )

    def add(self, q: Question, source_file: str = "", commit: bool = True) -> int | None:
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
        if commit:
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

    def reclassify(self, progress=None, should_stop=None) -> dict:
        """Đọc lại khối LaTeX gốc (raw) của mọi câu bằng bộ nhận dạng mới nhất; câu nào đổi LOẠI (vd tự luận/trắc nghiệm → Đúng/Sai
        do viết «\\TF\\choice») thì cập nhật loại, đề bài, phương án, đáp án. Trả về {'xet', 'doi', 'theo_loai': {«TN→DS»: n}}."""
        from .parser import parse_tex
        rows = self.con.execute("SELECT id, qtype, raw FROM questions").fetchall()
        res = {"xet": len(rows), "doi": 0, "theo_loai": {}}
        for k, r in enumerate(rows):
            if k % 2000 == 0:
                self.con.commit()
                if progress:
                    progress(k, len(rows))
                if should_stop and should_stop():
                    break
            try:
                qs = parse_tex(r["raw"])
            except Exception:  # noqa: BLE001 – khối LaTeX hỏng: giữ nguyên
                continue
            if len(qs) != 1 or qs[0].qtype == r["qtype"]:
                continue
            q = qs[0]
            v = self._row_values(q)
            v["raw"] = r["raw"]                           # giữ nguyên khối gốc
            for col in ("id_code", "lop", "mon", "chuong", "muc_do", "bai", "dang", "tags", "group_id"):
                v.pop(col, None)                          # không đụng ID/nguồn đã gán
            sets = ",".join(f"{c}=?" for c in v)
            try:
                self.con.execute(f"UPDATE questions SET {sets} WHERE id=?", [*v.values(), r["id"]])
            except sqlite3.IntegrityError:                # trùng nội dung với câu khác sau khi đổi: để nguyên
                continue
            res["doi"] += 1
            key = f"{r['qtype']}→{q.qtype}"
            res["theo_loai"][key] = res["theo_loai"].get(key, 0) + 1
        self.con.commit()
        if progress:
            progress(len(rows), len(rows))
        return res

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
            choice_cmd=r["choice_cmd"] if "choice_cmd" in r.keys() else "",
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
            from .textnorm import fts_query
            fq = fts_query(text)
            if self.fts and fq:          # tìm toàn văn, gõ có dấu hay không dấu đều được
                sql += " AND id IN (SELECT rowid FROM questions_fts WHERE questions_fts MATCH ?)"
                args.append(fq)
            else:
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

    def id_level_stats(self):
        """Số câu theo (lớp, môn, chương, bài, dạng, loại, mức độ) – cho bảng «Chọn theo ID»."""
        return self.con.execute(
            "SELECT lop, mon, chuong, bai, dang, qtype, muc_do, COUNT(*) AS n FROM questions WHERE id_code != '' "
            "GROUP BY lop, mon, chuong, bai, dang, qtype, muc_do ORDER BY lop, mon, chuong, bai, dang, qtype").fetchall()

    def tree_stats(self):
        """Số câu theo (lớp, môn, chương, bài, dạng) – cho cây dữ liệu."""
        return self.con.execute(
            "SELECT lop, mon, chuong, bai, dang, COUNT(*) AS n FROM questions "
            "GROUP BY lop, mon, chuong, bai, dang ORDER BY lop, mon, chuong, bai, dang").fetchall()

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

    # ---------- lịch sử ra đề ----------
    def log_batch(self, versions, *, ten_de="", seed=None, matrix=None, out_dir="") -> int:
        cur = self.con.execute(
            "INSERT INTO exam_batches(at, ten_de, seed, matrix, codes, out_dir) VALUES (?,?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), ten_de, "" if seed is None else str(seed),
             json.dumps(matrix or [], ensure_ascii=False), ",".join(v.code for v in versions), out_dir))
        bid = cur.lastrowid
        rows = [(bid, v.code, part, i, q.db_id) for v in versions for part, qs in v.sections.items()
                for i, q in enumerate(qs, 1) if q.db_id is not None]
        self.con.executemany("INSERT INTO exam_items VALUES (?,?,?,?,?)", rows)
        self.con.commit()
        return bid

    def batches(self, limit: int = 200):
        return self.con.execute("SELECT b.*, (SELECT COUNT(DISTINCT question_id) FROM exam_items i "
                                "WHERE i.batch_id=b.id) AS n FROM exam_batches b ORDER BY id DESC LIMIT ?",
                                (limit,)).fetchall()

    def recent_question_ids(self, last_batches: int = 3) -> set[int]:
        """Câu đã dùng trong N đợt ra đề gần nhất (để tránh lặp câu giữa các bài kiểm tra gần nhau)."""
        return {r[0] for r in self.con.execute(
            "SELECT DISTINCT question_id FROM exam_items WHERE batch_id IN "
            "(SELECT id FROM exam_batches ORDER BY id DESC LIMIT ?)", (last_batches,))}

    # ---------- tài sản (ảnh/hình) ----------
    def add_asset(self, question_id: int, path: str, data: bytes) -> int:
        import hashlib
        cur = self.con.execute("INSERT INTO assets(question_id, path, sha1, data) VALUES (?,?,?,?)",
                               (question_id, path, hashlib.sha1(data).hexdigest(), data))
        self.con.commit()
        return cur.lastrowid

    def assets(self, question_id: int):
        return self.con.execute("SELECT id, path, sha1, data FROM assets WHERE question_id=?",
                                (question_id,)).fetchall()

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
