"""Dùng ngân hàng câu hỏi của MyLT (file DATA\\BANK\\Bank.mylt – cơ sở dữ liệu Microsoft Access/Jet 4).

* `read_rows(path)`: đọc mọi dòng câu hỏi. Tự nhận tên bảng/cột của nhiều phiên bản MyLT (mặc định bảng QUEST với
  id, NoiDung, IDCauHoi, TuLuan, SoLan). Đọc bằng access-parser (Python thuần, không cần cài Access); thiếu thì thử
  mdb-export (mdbtools) hoặc ODBC (pyodbc + Microsoft Access Driver).
* `import_mylt(bank, path)`: thêm vào kho hiện tại (bỏ câu trùng, giữ ID, tự luận, số lần đã lấy).
* `find_banks()`: tìm các file Bank.mylt có trên máy (thư mục MyLT thường nằm ở Desktop, D:\\, C:\\…).
* `extract_archive(path, password)`: giải nén Bank.rar/.zip/.7z có mật khẩu bằng WinRAR/7-Zip/UnRAR trên máy.
"""
from __future__ import annotations

import csv
import io
import os
import re
import shutil
import subprocess
import tempfile

from .parser import parse_tex
from .textnorm import unaccent

USED_MARK = re.compile(r"%<MyLT>\s*")
BANK_NAME = "bank.mylt"
DEFAULT_PASSWORD = "MyLT123"


class MyltError(RuntimeError):
    pass


# ---------------------------------------------------------------- nhận tên cột
def _k(s) -> str:
    return re.sub(r"[^a-z0-9]", "", unaccent(str(s)).lower())


def pick_columns(cols) -> dict:
    """Ánh xạ tên cột của file → {text, id, tuluan, solan}. Trả về {} nếu không có cột nội dung."""
    keys = {c: _k(c) for c in cols}
    out = {}

    def find(pred, prefer=()):
        for p in prefer:
            for c, k in keys.items():
                if k == p:
                    return c
        for c, k in keys.items():
            if pred(k):
                return c
        return None
    out["text"] = find(lambda k: any(x in k for x in ("noidung", "content", "cauhoi", "question")) and "id" not in k,
                       ("noidung", "content"))
    out["id"] = find(lambda k: k.startswith("id") and k != "id" and "cauhoi" in k or k in ("idcau", "id5", "id6", "idc"),
                     ("idcauhoi",))
    out["tuluan"] = find(lambda k: "tuluan" in k or k == "essay")
    out["solan"] = find(lambda k: k in ("solan", "used", "usedcount") or "solan" in k)
    return out if out["text"] else {}


def _text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray)):
        for enc in ("utf-16-le", "utf-8", "cp1258", "latin-1"):
            try:
                s = bytes(v).decode(enc)
                if enc != "utf-16-le" or "\x00" not in s:
                    return s
            except UnicodeDecodeError:
                continue
    return str(v)


def _normalize(rows: list[dict], colmap: dict) -> list[dict]:
    out = []
    for r in rows:
        out.append({"NoiDung": _text(r.get(colmap["text"])),
                    "IDCauHoi": _text(r.get(colmap["id"])) if colmap.get("id") else "",
                    "TuLuan": r.get(colmap["tuluan"]) if colmap.get("tuluan") else 0,
                    "SoLan": r.get(colmap["solan"]) if colmap.get("solan") else 0})
    return out


# ---------------------------------------------------------------- đọc file Access
def _read_access_parser(path):
    from access_parser import AccessParser
    db = AccessParser(path)
    names = [t for t in db.catalog if not str(t).startswith("MSys")]
    names.sort(key=lambda t: (str(t).upper() != "QUEST", str(t)))        # bảng QUEST (MyLT) trước
    for t in names:
        tb = db.parse_table(t)
        cols = list(tb)
        cm = pick_columns(cols)
        if not cm:
            continue
        n = len(tb[cols[0]]) if cols else 0
        rows = [{c: tb[c][i] for c in cols} for i in range(n)]
        return _normalize(rows, cm)
    raise MyltError("Không thấy bảng câu hỏi (cột NoiDung) trong file này")


def _read_mdbtools(path):
    exe = shutil.which("mdb-export")
    tables = shutil.which("mdb-tables")
    if not exe or not tables:
        raise MyltError("không có mdbtools")
    names = subprocess.run([tables, "-1", path], capture_output=True, text=True, timeout=60, check=True).stdout.split()
    for t in sorted(names, key=lambda x: (x.upper() != "QUEST", x)):
        out = subprocess.run([exe, path, t], capture_output=True, text=True, timeout=120, check=True).stdout
        rd = csv.DictReader(io.StringIO(out))
        cm = pick_columns(rd.fieldnames or [])
        if cm:
            return _normalize(list(rd), cm)
    raise MyltError("không thấy bảng câu hỏi")


def _read_odbc(path):
    import pyodbc
    con = pyodbc.connect(r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=" + path)
    cur = con.cursor()
    for t in [r.table_name for r in cur.tables(tableType="TABLE")]:
        cur.execute(f"SELECT * FROM [{t}]")
        cols = [d[0] for d in cur.description]
        cm = pick_columns(cols)
        if cm:
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
            con.close()
            return _normalize(rows, cm)
    con.close()
    raise MyltError("không thấy bảng câu hỏi")


def read_rows(path: str) -> list[dict]:
    """Các dòng {NoiDung, IDCauHoi, TuLuan, SoLan} của kho MyLT."""
    if not os.path.isfile(path):
        raise MyltError(f"Không thấy file {path}")
    errors = []
    for name, fn in (("access-parser", _read_access_parser), ("mdbtools", _read_mdbtools), ("ODBC", _read_odbc)):
        try:
            return fn(path)
        except ImportError:
            errors.append(f"{name}: chưa cài")
        except Exception as e:  # noqa: BLE001 – file hỏng / không phải kho MyLT / thiếu driver
            errors.append(f"{name}: {e}")
    raise MyltError("Không đọc được kho MyLT – " + "; ".join(errors))


def count_questions(path: str) -> int:
    try:
        return sum(1 for r in read_rows(path) if str(r["NoiDung"]).strip())
    except MyltError:
        return -1


# ---------------------------------------------------------------- tìm trên máy, giải nén
def find_banks(extra_dirs=(), max_dirs: int = 4000) -> list[str]:
    """Các file Bank.mylt có trên máy (lớn nhất trước). Tìm ở thư mục người dùng, Desktop, Downloads, ổ C:..H:."""
    roots = []
    home = os.path.expanduser("~")
    for sub in ("Desktop", "Documents", "Downloads", "OneDrive", ""):
        roots.append(os.path.join(home, sub) if sub else home)
    roots += [f"{d}:\\" for d in "CDEFGH"] + ["/mnt", "/media"]
    roots += list(extra_dirs)
    seen, found, visited = set(), [], 0
    skip = {"windows", "program files", "program files (x86)", "$recycle.bin", "system volume information",
            "appdata", "node_modules", ".git", "programdata"}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dp, dn, fn in os.walk(root):
            visited += 1
            if visited > max_dirs:
                break
            dn[:] = [d for d in dn if d.lower() not in skip and not d.startswith(".")]
            depth = dp[len(root):].count(os.sep)
            if depth > 5:
                dn[:] = []
            for f in fn:
                if f.lower() == BANK_NAME or f.lower().endswith(".mylt"):
                    p = os.path.abspath(os.path.join(dp, f))
                    if p.lower() not in seen:
                        seen.add(p.lower())
                        found.append(p)
    return sorted(found, key=lambda p: -os.path.getsize(p))


def _tools() -> list[tuple[str, str]]:
    pf = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)")]
    out = []
    for base in pf:
        if base:
            out += [("unrar", os.path.join(base, "WinRAR", "UnRAR.exe")), ("unrar", os.path.join(base, "WinRAR", "Rar.exe")),
                    ("7z", os.path.join(base, "7-Zip", "7z.exe"))]
    for name, kind in (("unrar", "unrar"), ("UnRAR", "unrar"), ("7z", "7z"), ("7za", "7z"), ("7zz", "7z")):
        p = shutil.which(name)
        if p:
            out.append((kind, p))
    return [(k, p) for k, p in out if os.path.isfile(p)]


def extract_archive(path: str, password: str = DEFAULT_PASSWORD, out_dir: str | None = None) -> str:
    """Giải nén Bank.rar (hoặc .zip/.7z) rồi trả về đường dẫn file .mylt bên trong. Cần WinRAR hoặc 7-Zip trên máy."""
    out_dir = out_dir or tempfile.mkdtemp(prefix="nhd_mylt_")
    tools = _tools()
    if not tools:
        raise MyltError("Máy chưa có WinRAR hoặc 7-Zip để giải nén. Hãy giải nén Bank.rar bằng WinRAR (nhập mật khẩu) "
                        "rồi chọn file Bank.mylt bên trong.")
    last = ""
    for kind, exe in tools:
        cmd = ([exe, "x", "-o+", f"-p{password}", "-y", path, out_dir + os.sep] if kind == "unrar"
               else [exe, "x", f"-p{password}", f"-o{out_dir}", "-y", path])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        found = [os.path.join(dp, f) for dp, _, fs in os.walk(out_dir) for f in fs if f.lower().endswith(".mylt")]
        if r.returncode == 0 and found:
            return found[0]
        last = (r.stdout + r.stderr).strip().splitlines()[-1:] or ["lỗi không rõ"]
        last = last[0]
    raise MyltError(f"Không giải nén được (sai mật khẩu hoặc file hỏng): {last}")


# ---------------------------------------------------------------- nhập vào kho
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
            env = "bt" if str(r.get("TuLuan") or "0") not in ("0", "", "False", "false", "0.0") else "ex"
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


def import_mylt(bank, path: str, password: str = DEFAULT_PASSWORD) -> dict:
    """Nhập từ Bank.mylt hoặc từ file nén (.rar/.zip/.7z) chứa Bank.mylt."""
    if path.lower().endswith((".rar", ".zip", ".7z")):
        path = extract_archive(path, password)
    return import_rows(bank, read_rows(path), source=path)
