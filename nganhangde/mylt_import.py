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


def _norm_one(r: dict, cm: dict) -> dict:
    return _normalize([r], cm)[0]


def _iter_mdbtools(path):
    """mdbtools: xuất bảng ra file CSV tạm rồi đọc từng dòng (kho thật hàng trăm MB, không nạp hết vào bộ nhớ)."""
    exe, tables = shutil.which("mdb-export"), shutil.which("mdb-tables")
    if not exe or not tables:
        raise MyltError("không có mdbtools")
    names = subprocess.run([tables, "-1", path], capture_output=True, text=True, timeout=300, check=True).stdout.split()
    d = tempfile.mkdtemp(prefix="nhd_mdb_")
    for t in sorted(names, key=lambda x: (x.upper() != "QUEST", x)):
        out = os.path.join(d, "t.csv")
        with open(out, "wb") as f:
            subprocess.run([exe, path, t], stdout=f, stderr=subprocess.DEVNULL, check=True)
        with open(out, encoding="utf-8", errors="replace", newline="") as f:
            head = f.readline()
        cm = pick_columns(next(csv.reader([head]), []))
        if cm:
            return _gen_csv(out, cm, d)
    shutil.rmtree(d, ignore_errors=True)
    raise MyltError("không thấy bảng câu hỏi")


def _gen_csv(out, cm, tmpdir):
    csv.field_size_limit(2 ** 31 - 1)
    try:
        with open(out, encoding="utf-8", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                yield _norm_one(r, cm)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _read_mdbtools(path):
    return list(_iter_mdbtools(path))


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


def _rc4(key: bytes, buf: bytes) -> bytes:
    sbox = list(range(256))
    j = 0
    for i in range(256):
        j = (j + sbox[i] + key[i % len(key)]) & 0xFF
        sbox[i], sbox[j] = sbox[j], sbox[i]
    i = j = 0
    out = bytearray()
    for b in buf:
        i = (i + 1) & 0xFF
        j = (j + sbox[i]) & 0xFF
        sbox[i], sbox[j] = sbox[j], sbox[i]
        out.append(b ^ sbox[(sbox[i] + sbox[j]) & 0xFF])
    return bytes(out)


def jet4_password(path: str) -> str:
    """Mật khẩu của file Access (Jet 4) ghi trong phần đầu file – MyLT đặt mật khẩu để Access không mở được.
    Chỉ dùng để mở chính file của người dùng bằng bộ máy Access của Windows; trả về '' nếu không đặt mật khẩu."""
    import struct
    try:
        with open(path, "rb") as f:
            data = f.read(0x98)
        if len(data) < 0x98 or data[0x14] != 1:
            return ""
        raw = _rc4(bytes([0xC7, 0xDA, 0x39, 0x6B]), data[0x18:0x98])[0x2A:0x52]
        mask = struct.unpack_from("<H", raw, 36)[0]
        chars = []
        for idx in range(20):
            v = struct.unpack_from("<H", raw, idx * 2)[0]
            if idx % 2 == 0:
                v ^= mask
            if v == 0:
                break
            chars.append(chr(v))
        pw = "".join(chars)
        return pw if pw.isprintable() else ""
    except (OSError, struct.error, ValueError):
        return ""


PS_SCRIPT = r"""param([string]$MdbPath, [string]$OutFile, [string]$PwFile)
$ErrorActionPreference = "Stop"
$pw = ""
if (Test-Path $PwFile) { $pw = [System.IO.File]::ReadAllText($PwFile, [System.Text.Encoding]::UTF8) }
$conn = $null; $last = ""
foreach ($prov in @("Microsoft.Jet.OLEDB.4.0", "Microsoft.ACE.OLEDB.12.0")) {
    try {
        $cs = "Provider=$prov;Data Source=$MdbPath;"
        if ($pw -ne "") { $cs += "Jet OLEDB:Database Password=$pw;" }
        $c = New-Object System.Data.OleDb.OleDbConnection($cs)
        $c.Open(); $conn = $c; break
    } catch { $last = $_.Exception.Message }
}
if ($null -eq $conn) { throw "Không mở được bằng OLEDB: $last" }
try {
    $names = @("QUEST")
    foreach ($r in $conn.GetSchema("Tables").Rows) {
        if ($r["TABLE_TYPE"] -eq "TABLE" -and $names -notcontains $r["TABLE_NAME"]) { $names += $r["TABLE_NAME"] }
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    foreach ($t in $names) {
        try {
            $cmd = $conn.CreateCommand(); $cmd.CommandText = "SELECT * FROM [" + $t + "]"
            $rd = $cmd.ExecuteReader()
        } catch { continue }
        $cols = @(); for ($i = 0; $i -lt $rd.FieldCount; $i++) { $cols += $rd.GetName($i) }
        if (-not ($cols | Where-Object { $_ -match "(?i)noidung|n.i dung|content" })) { $rd.Close(); continue }
        $sw = New-Object System.IO.StreamWriter($OutFile, $false, $utf8)
        try {
            while ($rd.Read()) {
                $o = [ordered]@{}
                for ($i = 0; $i -lt $cols.Count; $i++) {
                    $o[$cols[$i]] = if ($rd.IsDBNull($i)) { $null } else { [string]$rd.GetValue($i) }
                }
                $sw.WriteLine(($o | ConvertTo-Json -Compress))
            }
        } finally { $sw.Close(); $rd.Close() }
        return
    }
    throw "Không thấy bảng câu hỏi"
} finally { $conn.Close() }
"""


def _iter_oledb_ps(path: str):
    """Windows: đọc bằng Microsoft Jet OLEDB qua PowerShell 32-bit (Jet 4.0 chỉ có bản 32-bit); xuất ra file .jsonl
    rồi đọc từng dòng. Kho lớn (hàng trăm nghìn câu) có thể mất vài phút."""
    if os.name != "nt":
        raise MyltError("OLEDB chỉ có trên Windows")
    ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "SysWOW64", "WindowsPowerShell", "v1.0", "powershell.exe")
    if not os.path.isfile(ps):
        ps = shutil.which("powershell") or "powershell"
    d = tempfile.mkdtemp(prefix="nhd_oledb_")                   # thư mục tạm riêng – không ghi cạnh file kho
    try:
        script, pwf, out = (os.path.join(d, n) for n in ("read.ps1", "pw.txt", "out.jsonl"))
        with open(script, "w", encoding="utf-8-sig") as f:
            f.write(PS_SCRIPT)
        with open(pwf, "w", encoding="utf-8") as f:
            f.write(jet4_password(path))
        r = subprocess.run([ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script, path, out, pwf],
                           capture_output=True, timeout=3 * 3600, creationflags=0x08000000)
        if r.returncode != 0 or not os.path.exists(out):
            msg = (r.stderr or r.stdout).decode("utf-8", "replace").strip()
            raise MyltError(msg or "PowerShell không xuất được dữ liệu")
    except BaseException:
        shutil.rmtree(d, ignore_errors=True)
        raise
    return _gen_jsonl(out, d)


def _gen_jsonl(out, tmpdir):
    import json
    cm = None
    try:
        with open(out, encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                if cm is None:
                    cm = pick_columns(list(r))
                    if not cm:
                        return
                yield _norm_one(r, cm)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _read_oledb_ps(path: str) -> list[dict]:
    return list(_iter_oledb_ps(path))


BIG_FILE = 60 * 1024 * 1024         # file lớn hơn mức này: bỏ access-parser (Python thuần, quá chậm/tốn RAM)


def iter_rows(path: str):
    """Như read_rows nhưng trả về bộ lặp (đọc dần, hợp với kho hàng trăm MB). Thử lần lượt các bộ đọc."""
    if not os.path.isfile(path):
        raise MyltError(f"Không thấy file {path}")
    errors = []
    readers = [("mdbtools", _iter_mdbtools), ("ODBC", _read_odbc)]
    if os.path.getsize(path) < BIG_FILE:
        readers.insert(0, ("access-parser", _read_access_parser))
    if os.name == "nt":
        readers.insert(0, ("OLEDB", _iter_oledb_ps))
    for name, fn in readers:
        try:
            return iter(fn(path))
        except ImportError:
            errors.append(f"{name}: chưa cài")
        except Exception as e:  # noqa: BLE001 – file hỏng / không phải kho MyLT / thiếu driver
            errors.append(f"{name}: {e}")
    raise MyltError("Không đọc được kho MyLT – " + "; ".join(errors))


def read_rows(path: str) -> list[dict]:
    """Các dòng {NoiDung, IDCauHoi, TuLuan, SoLan} của kho MyLT. Windows: thử bộ máy Access (OLEDB) trước."""
    return list(iter_rows(path))


def count_questions(path: str) -> int:
    try:
        return sum(1 for r in read_rows(path) if str(r["NoiDung"]).strip())
    except MyltError:
        return -1


# ---------------------------------------------------------------- tìm trên máy, giải nén
def find_banks(extra_dirs=(), max_dirs: int = 4000) -> list[str]:
    """Các file Bank.mylt có trên máy (lớn nhất trước). Tìm ở thư mục người dùng, Desktop, Downloads, ổ C:..H:."""
    roots = list(extra_dirs)                       # thư mục chỉ định tìm trước
    home = os.path.expanduser("~")
    for sub in ("Desktop", "Documents", "Downloads", "OneDrive", ""):
        roots.append(os.path.join(home, sub) if sub else home)
    roots += [f"{d}:\\" for d in "CDEFGH"] + ["/mnt", "/media"]
    seen, found = set(), []
    skip = {"windows", "program files", "program files (x86)", "$recycle.bin", "system volume information",
            "appdata", "node_modules", ".git", "programdata"}
    for root in roots:
        if not os.path.isdir(root):
            continue
        visited = 0                                  # hạn mức số thư mục duyệt tính riêng cho từng gốc
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


# ---------------------------------------------------------------- chẩn đoán, đồng bộ
def diagnose(path: str) -> str:
    """Báo cáo chi tiết khi đọc kho MyLT (để gửi cho người hỗ trợ nếu đọc lỗi hoặc ra 0 câu)."""
    L = [f"File: {path}"]
    try:
        L.append(f"Dung lượng: {os.path.getsize(path):,} byte")
        with open(path, "rb") as f:
            head = f.read(0x98)
        L.append(f"Đầu file: {'Jet 4 (Access 2000/2003)' if head[4:19] == b'Standard Jet DB' else 'không phải Jet/Access?'}; "
                 f"mã phiên bản byte 0x14 = {head[0x14] if len(head) > 0x14 else '?'}")
        pw = jet4_password(path)
        L.append("Mật khẩu file Access: " + ("có (đã giải được)" if pw else "không đặt"))
    except OSError as e:
        return f"Không mở được file: {e}"
    try:
        from access_parser import AccessParser
        db = AccessParser(path)
        for t in [t for t in db.catalog if not str(t).startswith("MSys")]:
            tb = db.parse_table(t)
            cols = list(tb)
            n = len(tb[cols[0]]) if cols else 0
            L.append(f"Bảng {t}: {n} dòng; cột: {', '.join(map(str, cols))}; nhận cột nội dung: {pick_columns(cols) or 'KHÔNG'}")
    except Exception as e:  # noqa: BLE001
        L.append(f"access-parser: {type(e).__name__}: {e}")
    for name, fn in (("OLEDB (Windows)", _read_oledb_ps), ("mdbtools", _read_mdbtools), ("ODBC", _read_odbc)):
        if name.startswith("OLEDB") and os.name != "nt":
            continue
        try:
            L.append(f"{name}: đọc được {len(fn(path))} dòng")
        except Exception as e:  # noqa: BLE001
            L.append(f"{name}: {str(e)[:160]}")
    L.append("Công cụ giải nén: " + (", ".join(p for _, p in _tools()) or "không có WinRAR/7-Zip"))
    return "\n".join(L)


def sync_if_linked(bank, settings) -> dict | None:
    """Kho MyLT đã «liên kết» (cài đặt mylt/link): nhập thêm câu mới từ file đó mỗi lần mở phần mềm.
    Chỉ thêm, không xoá/sửa câu đã có. Trả về kết quả nhập hoặc None."""
    path = str(settings.value("mylt/link", "") or "")
    if not path or not os.path.isfile(path):
        return None
    mt = str(os.path.getmtime(path))
    if str(settings.value("mylt/link_mtime", "")) == mt:
        return None                                   # file không đổi từ lần đồng bộ trước
    res = import_rows(bank, iter_rows(path), source=path)
    settings.setValue("mylt/link_mtime", mt)
    return res


# ---------------------------------------------------------------- nhập vào kho
def import_rows(bank, rows, source: str = "Bank.mylt", progress=None, should_stop=None) -> dict:
    """Thêm các câu vào kho (bộ lặp hay danh sách). Ghi theo lô 2000 dòng cho nhanh. Trả về
    {'them', 'trung', 'loi', 'tong'}; progress(số_dòng_đã_xử_lý, 0) gọi mỗi lô; câu lỗi ghi lí do (tối đa 200)."""
    res = {"them": 0, "trung": 0, "loi": [], "tong": 0}
    n_err = 0

    def err(msg):
        nonlocal n_err
        n_err += 1
        if len(res["loi"]) < 200:
            res["loi"].append(msg)
    for i, r in enumerate(rows, 1):
        res["tong"] = i
        if i % 2000 == 0:
            bank.con.commit()
            if progress:
                progress(i, 0)
            if should_stop and should_stop():
                break
        text = USED_MARK.sub("", str(r.get("NoiDung") or "")).strip()
        if not text:
            err(f"Dòng {i}: nội dung trống")
            continue
        try:
            qs = parse_tex(text)
            if not qs:
                env = "bt" if str(r.get("TuLuan") or "0") not in ("0", "", "False", "false", "0.0") else "ex"
                qs = parse_tex(f"\\begin{{{env}}}\n{text}\n\\end{{{env}}}")
        except (ValueError, IndexError, RecursionError) as e:        # LaTeX hỏng (thiếu ngoặc…): bỏ câu này, đi tiếp
            err(f"Dòng {i}: LaTeX hỏng ({str(e)[:60]})")
            continue
        if not qs:
            err(f"Dòng {i}: không nhận ra câu hỏi")
            continue
        idc = str(r.get("IDCauHoi") or "").strip().upper()
        try:
            used = int(float(r.get("SoLan") or 0))
        except (TypeError, ValueError):
            used = 0
        for q in qs:
            if idc and not q.id_code:
                q.set_id(idc)
            new_id = bank.add(q, source, commit=False)
            if new_id is None:
                res["trung"] += 1
                continue
            res["them"] += 1
            if used:
                bank.con.execute("UPDATE questions SET used_count=? WHERE id=?", (used, new_id))
    bank.con.commit()
    res["so_loi"] = n_err
    return res


def import_mylt(bank, path: str, password: str = DEFAULT_PASSWORD, progress=None, should_stop=None) -> dict:
    """Nhập từ Bank.mylt hoặc từ file nén (.rar/.zip/.7z) chứa Bank.mylt."""
    if path.lower().endswith((".rar", ".zip", ".7z")):
        path = extract_archive(path, password)
    return import_rows(bank, iter_rows(path), source=path, progress=progress, should_stop=should_stop)
