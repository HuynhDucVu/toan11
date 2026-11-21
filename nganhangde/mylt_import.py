"""Nhập ngân hàng câu hỏi của MyLT (file DATA\\BANK\\Bank.mylt – cơ sở dữ liệu Microsoft Access/Jet 4).

Bảng QUEST: id, NoiDung (mã LaTeX của câu), IDCauHoi, TuLuan (1 = tự luận), SoLan (số lần đã lấy ra đề).
Đọc bằng thư viện access-parser (Python thuần, chạy trên Windows không cần cài Access); nếu thiếu thì thử
mdb-export (mdbtools) hoặc ODBC (pyodbc + Microsoft Access Driver).
"""
from __future__ import annotations

import csv
import io
import re
import shutil
import subprocess

from .parser import parse_tex

USED_MARK = re.compile(r"%<MyLT>\s*")


class MyltError(RuntimeError):
    pass


def read_rows(path: str) -> list[dict]:
    """Các dòng của bảng QUEST."""
    errors = []
    try:
        from access_parser import AccessParser
        t = AccessParser(path).parse_table("QUEST")
        cols = list(t)
        n = len(t[cols[0]]) if cols else 0
        return [{c: t[c][i] for c in cols} for i in range(n)]
    except ImportError:
        errors.append("thiếu thư viện access-parser")
    except Exception as e:  # noqa: BLE001 – file hỏng / không phải kho MyLT
        errors.append(f"access-parser: {e}")
    exe = shutil.which("mdb-export")
    if exe:
        try:
            out = subprocess.run([exe, path, "QUEST"], capture_output=True, text=True, timeout=120, check=True).stdout
            return list(csv.DictReader(io.StringIO(out)))
        except (OSError, subprocess.SubprocessError) as e:
            errors.append(f"mdb-export: {e}")
    try:
        import pyodbc
        con = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path)
        cur = con.cursor()
        cur.execute("SELECT * FROM QUEST")
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        con.close()
        return rows
    except Exception as e:  # noqa: BLE001
        errors.append(f"ODBC: {e}")
    raise MyltError("Không đọc được kho MyLT: " + "; ".join(errors))


def import_rows(bank, rows, source: str = "Bank.mylt") -> dict:
    """Thêm các câu vào kho. Trả về {'them', 'trung', 'loi', 'tong'}; câu lỗi ghi lí do."""
    res = {"them": 0, "trung": 0, "loi": [], "tong": len(rows)}
    for i, r in enumerate(rows, 1):
        text = USED_MARK.sub("", str(r.get("NoiDung") or "")).strip()
        if not text:
            res["loi"].append(f"Dòng {i}: nội dung trống")
            continue
        qs = parse_tex(text)
        if not qs:
            env = "bt" if str(r.get("TuLuan") or "0") not in ("0", "", "False") else "ex"
            qs = parse_tex(f"\\begin{{{env}}}\n{text}\n\\end{{{env}}}")
        if not qs:
            res["loi"].append(f"Dòng {i}: không nhận ra câu hỏi")
            continue
        idc = str(r.get("IDCauHoi") or "").strip().upper()
        try:
            used = int(float(r.get("SoLan") or 0))
        except (TypeError, ValueError):
            used = 0
        for q in qs:
            if idc and not q.id_code:
                q.set_id(idc)
            new_id = bank.add(q, source)
            if new_id is None:
                res["trung"] += 1
                continue
            res["them"] += 1
            if used:
                bank.con.execute("UPDATE questions SET used_count=? WHERE id=?", (used, new_id))
    bank.con.commit()
    return res


def import_mylt(bank, path: str) -> dict:
    return import_rows(bank, read_rows(path), source=path)
