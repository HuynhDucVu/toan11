import os
import shutil
import sqlite3

SCHEMA_VERSION = 2


def backup_database(db_path: str) -> str | None:
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        bak_path = f"{db_path}.bak"
        shutil.copy2(db_path, bak_path)
        return bak_path
    return None


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
    cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


def migrate(conn: sqlite3.Connection, db_path: str | None = None) -> int:
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    if current >= SCHEMA_VERSION:
        return current
    has_existing = bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='questions'").fetchone())
    if db_path and (current > 0 or has_existing):
        backup_database(db_path)

    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qid TEXT DEFAULT '', ids_json TEXT DEFAULT '[]', tags_json TEXT DEFAULT '[]',
            lop TEXT DEFAULT '', mon TEXT DEFAULT '', chuong TEXT DEFAULT '',
            muc_do TEXT DEFAULT '', bai TEXT DEFAULT '', dang TEXT DEFAULT '',
            qtype TEXT NOT NULL, stem TEXT NOT NULL, stem_plain TEXT DEFAULT '',
            choices_json TEXT DEFAULT '[]', correct_json TEXT DEFAULT '[]',
            short_ans TEXT DEFAULT '', solution TEXT DEFAULT '',
            cmd_name TEXT DEFAULT '', cmd_opt TEXT DEFAULT '',
            lock_shuffle INTEGER DEFAULT 0, group_id TEXT DEFAULT NULL,
            raw TEXT NOT NULL, used_count INTEGER DEFAULT 0,
            fingerprint TEXT UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    for col, col_def in [
        ("qid", "TEXT DEFAULT ''"), ("ids_json", "TEXT DEFAULT '[]'"), ("tags_json", "TEXT DEFAULT '[]'"),
        ("stem_plain", "TEXT DEFAULT ''"), ("choices_json", "TEXT DEFAULT '[]'"), ("correct_json", "TEXT DEFAULT '[]'"),
        ("short_ans", "TEXT DEFAULT ''"), ("cmd_name", "TEXT DEFAULT ''"), ("cmd_opt", "TEXT DEFAULT ''"),
        ("lock_shuffle", "INTEGER DEFAULT 0"), ("group_id", "TEXT DEFAULT NULL"),
    ]:
        _ensure_column(conn, "questions", col, col_def)

    conn.executescript("DROP TRIGGER IF EXISTS questions_ai; DROP TRIGGER IF EXISTS questions_ad; DROP TRIGGER IF EXISTS questions_au;")
    from .texutil import strip_accents_vi
    for rid, qid, lop, mon, chuong, md, bai, dang, st, st_plain in conn.execute(
        "SELECT id, qid, lop, mon, chuong, muc_do, bai, dang, stem, stem_plain FROM questions"
    ).fetchall():
        new_qid = qid or ""
        if not new_qid and lop and mon and chuong and md:
            new_qid = f"{lop}{mon}{chuong}{md}{bai or ''}" + (f"-{dang}" if dang else "")
        new_plain = st_plain or strip_accents_vi(st or "").lower()
        if new_qid != (qid or "") or new_plain != (st_plain or ""):
            conn.execute("UPDATE questions SET qid = ?, stem_plain = ? WHERE id = ?", (new_qid, new_plain, rid))

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            rel_path TEXT NOT NULL, sha1 TEXT DEFAULT '', kind TEXT DEFAULT 'image'
        );
        CREATE TABLE IF NOT EXISTS question_groups (group_id TEXT PRIMARY KEY, title TEXT DEFAULT '', shared_context TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS exam_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, seed INTEGER NOT NULL,
            matrix_json TEXT DEFAULT '{}', codes_json TEXT DEFAULT '[]',
            online_url TEXT DEFAULT '', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS exam_items (
            batch_id INTEGER NOT NULL REFERENCES exam_batches(id) ON DELETE CASCADE,
            question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
            PRIMARY KEY (batch_id, question_id)
        );
        CREATE TABLE IF NOT EXISTS workspace_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER REFERENCES workspace_nodes(id) ON DELETE CASCADE,
            name TEXT NOT NULL, node_type TEXT NOT NULL DEFAULT 'folder',
            ref_batch_id INTEGER REFERENCES exam_batches(id) ON DELETE SET NULL
        );
        DROP TABLE IF EXISTS questions_fts;
        CREATE VIRTUAL TABLE questions_fts USING fts5(qid, stem, stem_plain, content='questions', content_rowid='id');
        INSERT INTO questions_fts(questions_fts) VALUES('rebuild');
        CREATE TRIGGER questions_ai AFTER INSERT ON questions BEGIN
            INSERT INTO questions_fts(rowid, qid, stem, stem_plain) VALUES (new.id, new.qid, new.stem, new.stem_plain);
        END;
        CREATE TRIGGER questions_ad AFTER DELETE ON questions BEGIN
            INSERT INTO questions_fts(questions_fts, rowid, qid, stem, stem_plain) VALUES ('delete', old.id, old.qid, old.stem, old.stem_plain);
        END;
        CREATE TRIGGER questions_au AFTER UPDATE ON questions BEGIN
            INSERT INTO questions_fts(questions_fts, rowid, qid, stem, stem_plain) VALUES ('delete', old.id, old.qid, old.stem, old.stem_plain);
            INSERT INTO questions_fts(rowid, qid, stem, stem_plain) VALUES (new.id, new.qid, new.stem, new.stem_plain);
        END;
        """
    )
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
    conn.commit()
    return SCHEMA_VERSION
