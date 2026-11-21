import hashlib
import json
import os
import re
import sqlite3
from typing import Iterable
from .migrations import migrate
from .parser import Question
from .texutil import strip_accents_vi

INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")


class QuestionBankDB:
    def __init__(self, db_path: str = "nganhang.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        migrate(self.conn, db_path)

    def close(self) -> None:
        self.conn.close()

    def add_question(self, q: Question, asset_base_dir: str | None = None) -> tuple[int | None, bool]:
        info = q.id_info()
        fp = q.fingerprint()
        stem_plain = strip_accents_vi(f"{q.stem} {' '.join(q.choices)}").lower()
        raw_tex = q.raw or q.to_latex(True)
        try:
            cur = self.conn.execute(
                """INSERT INTO questions (
                    qid, ids_json, tags_json, lop, mon, chuong, muc_do, bai, dang,
                    qtype, stem, stem_plain, choices_json, correct_json, short_ans,
                    solution, cmd_name, cmd_opt, lock_shuffle, group_id, raw, fingerprint
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    q.primary_id, json.dumps(q.ids, ensure_ascii=False), json.dumps(q.tags, ensure_ascii=False),
                    info.lop if info else "", info.mon if info else "", info.chuong if info else "",
                    info.muc_do if info else "", info.bai if info else "", info.dang if info else "",
                    q.qtype, q.stem, stem_plain, json.dumps(q.choices, ensure_ascii=False),
                    json.dumps(q.correct), q.short_ans, q.solution, q.cmd_name, q.cmd_opt,
                    1 if q.lock_shuffle else 0, q.group_id, raw_tex, fp,
                ),
            )
            qid_row = cur.lastrowid
            for rel_img in INCLUDEGRAPHICS_RE.findall(raw_tex):
                sha = ""
                if asset_base_dir:
                    full = rel_img if os.path.isabs(rel_img) else os.path.join(asset_base_dir, rel_img)
                    if os.path.exists(full):
                        sha = hashlib.sha1(open(full, "rb").read()).hexdigest()
                self.conn.execute(
                    "INSERT INTO assets (question_id, rel_path, sha1, kind) VALUES (?, ?, ?, ?)",
                    (qid_row, rel_img, sha, "image"),
                )
            self.conn.commit()
            return qid_row, True
        except sqlite3.IntegrityError:
            return None, False

    def bulk_import(self, questions: Iterable[Question], asset_base_dir: str | None = None) -> dict[str, int]:
        added = skipped = 0
        for q in questions:
            _, ok = self.add_question(q, asset_base_dir=asset_base_dir)
            if ok:
                added += 1
            else:
                skipped += 1
        return {"added": added, "duplicates": skipped}

    def list_assets(self, question_id: int) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM assets WHERE question_id = ?", (question_id,)).fetchall()]

    def search(self, keyword: str = "", id_glob: str = "", qtype: str = "", muc_do: str = "", limit: int = 200) -> list[sqlite3.Row]:
        clauses, params = [], []
        if keyword.strip():
            tokens = [f'"{tok}"*' for tok in strip_accents_vi(keyword.strip()).lower().split() if tok]
            if tokens:
                sql_base = "SELECT q.* FROM questions_fts f JOIN questions q ON q.id = f.rowid"
                clauses.append("questions_fts MATCH ?")
                params.append(" AND ".join(tokens))
            else:
                sql_base = "SELECT q.* FROM questions q"
        else:
            sql_base = "SELECT q.* FROM questions q"
        if id_glob.strip():
            clauses.append("q.qid GLOB ?")
            params.append(id_glob.strip())
        if qtype.strip():
            clauses.append("q.qtype = ?")
            params.append(qtype.strip())
        if muc_do.strip():
            clauses.append("q.muc_do = ?")
            params.append(muc_do.strip())
        where_sql = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        return self.conn.execute(f"{sql_base}{where_sql} ORDER BY q.used_count ASC, q.id DESC LIMIT ?", params).fetchall()

    def update_question_stem(self, row_id: int, new_stem: str) -> None:
        new_plain = strip_accents_vi(new_stem).lower()
        self.conn.execute("UPDATE questions SET stem = ?, stem_plain = ? WHERE id = ?", (new_stem, new_plain, row_id))
        self.conn.commit()

    def delete_question(self, row_id: int) -> None:
        self.conn.execute("DELETE FROM questions WHERE id = ?", (row_id,))
        self.conn.commit()

    def add_workspace_node(self, name: str, parent_id: int | None = None, node_type: str = "folder", ref_batch_id: int | None = None) -> int:
        cur = self.conn.execute(
            "INSERT INTO workspace_nodes (parent_id, name, node_type, ref_batch_id) VALUES (?, ?, ?, ?)",
            (parent_id, name, node_type, ref_batch_id),
        )
        self.conn.commit()
        return cur.lastrowid

    def list_workspace_nodes(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT id, parent_id, name, node_type, ref_batch_id FROM workspace_nodes ORDER BY id ASC").fetchall()]

    def delete_workspace_node(self, node_id: int) -> None:
        self.conn.execute("DELETE FROM workspace_nodes WHERE id = ?", (node_id,))
        self.conn.commit()
