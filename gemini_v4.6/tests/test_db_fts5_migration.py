import sqlite3
from nganhangde.core.db import QuestionBankDB
from nganhangde.core.parser import parse_tex_questions
from nganhangde.core.similarity import find_similar_questions


def test_legacy_migration_fts5_update_delete_and_assets(tmp_path):
    old_db = tmp_path / "nganhang.db"
    c = sqlite3.connect(str(old_db))
    c.execute(
        "CREATE TABLE questions (id INTEGER PRIMARY KEY AUTOINCREMENT, lop TEXT, mon TEXT, chuong TEXT, "
        "muc_do TEXT, bai TEXT, dang TEXT, qtype TEXT NOT NULL, stem TEXT NOT NULL, solution TEXT, "
        "raw TEXT NOT NULL, used_count INTEGER DEFAULT 0, fingerprint TEXT UNIQUE NOT NULL)"
    )
    c.execute(
        "INSERT INTO questions (lop, mon, chuong, muc_do, bai, dang, qtype, stem, raw, fingerprint) "
        "VALUES ('1','D','2','H','2','1','TN','Tìm giới hạn của cấp số cộng','\\begin{ex}Tìm giới hạn\\end{ex}','fp_legacy')"
    )
    c.commit()
    c.close()

    img = tmp_path / "do_thi.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\nFAKE")

    db = QuestionBankDB(str(old_db))
    assert (tmp_path / "nganhang.db.bak").exists()
    assert len(db.search(keyword="gioi han cap so cong")) == 1

    q_new = parse_tex_questions(r"%[1D2H2-2]\begin{ex}Cho hình \includegraphics{do_thi.png} và tích phân.\choice{\True 1}{2}{3}{4}\end{ex}")[0]
    rid, ok = db.add_question(q_new, asset_base_dir=str(tmp_path))
    assert ok and rid is not None
    assets = db.list_assets(rid)
    assert len(assets) == 1 and assets[0]["rel_path"] == "do_thi.png" and len(assets[0]["sha1"]) == 40

    # Cập nhật và xóa đồng bộ FTS5 sạch sẽ
    db.update_question_stem(rid, "Tính nguyên hàm hàm lượng giác")
    assert len(db.search(keyword="nguyen ham luong giac")) == 1
    db.delete_question(rid)
    assert len(db.search(keyword="nguyen ham luong giac")) == 0

    # Kiểm thử tìm câu gần trùng
    hits = find_similar_questions("Tìm giới hạn cấp số cộng lớp 11", [{"stem": "Tìm giới hạn của cấp số cộng"}], threshold=0.2)
    assert len(hits) == 1
    db.close()
