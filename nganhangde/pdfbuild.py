"""Biên dịch file .tex thành PDF (pdflatex / xelatex / lualatex – MiKTeX hoặc TeX Live).

* Tự tìm trình biên dịch: PATH, thư mục cài MiKTeX/TeX Live hay gặp trên Windows, hoặc đường dẫn do người dùng chọn.
* Chạy nhiều lượt (mặc định 2 – cho ex_test ghi/đọc file đáp án), có giới hạn thời gian.
* Đọc file .log, rút ra lỗi dễ hiểu: «Dòng 123: Undefined control sequence \\foo».
* Thiếu gói ex_test ⇒ dùng gói rút gọn đi kèm (chép vào thư mục biên dịch dưới tên ex_test.sty).
* Xem trước một câu / một nhóm câu: dựng tài liệu tạm từ file mẫu rồi biên dịch.
"""
from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field

ENGINES = ("pdflatex", "xelatex", "lualatex")
AUX_EXT = (".aux", ".log", ".out", ".toc", ".synctex.gz", ".fls", ".fdb_latexmk", ".nav", ".snm", ".bbl", ".blg")
LITE_STY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates", "nhd_extest.sty")


@dataclass
class BuildResult:
    tex: str
    ok: bool
    pdf: str | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    used_lite: bool = False
    seconds: float = 0.0

    def summary(self) -> str:
        name = os.path.basename(self.tex)
        if self.ok:
            return f"✔ {name} → {os.path.basename(self.pdf or '')}" + (" (gói ex_test rút gọn)" if self.used_lite else "")
        return f"✘ {name}: " + ("; ".join(self.errors[:3]) or "lỗi không rõ – xem file .log")


class EngineMissing(RuntimeError):
    pass


# Trên Windows, chương trình dòng lệnh gọi từ ứng dụng cửa sổ sẽ bật cửa sổ đen ⇒ chạy ẩn
NO_WINDOW = {"creationflags": 0x08000000} if os.name == "nt" else {}


# ---------------------------------------------------------------- tìm trình biên dịch
def _candidate_dirs() -> list[str]:
    out = []
    pf = [os.environ.get(k, "") for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
    for base in pf:
        if not base:
            continue
        out += [os.path.join(base, "MiKTeX", "miktex", "bin", "x64"),
                os.path.join(base, "MiKTeX", "miktex", "bin"),
                os.path.join(base, "Programs", "MiKTeX", "miktex", "bin", "x64")]
    roots = [f"{d}:\\texlive" for d in "CDEFGH"] + ["/usr/local/texlive"]
    for root in roots:                       # TeX Live mọi năm (2019 → bin\win32, 2023+ → bin\windows), mọi ổ đĩa
        out += sorted(glob.glob(os.path.join(root, "20*", "bin", "*")), reverse=True)
    out += ["/Library/TeX/texbin", "/usr/bin", "/usr/local/bin"]
    return out


def texstudio_ini_paths() -> list[str]:
    """Các nơi TeXstudio lưu cài đặt (Windows: %APPDATA%\\texstudio, bản portable: thư mục config cạnh exe)."""
    out = []
    for base in (os.environ.get("APPDATA", ""), os.path.expanduser("~/.config")):
        if base:
            out.append(os.path.join(base, "texstudio", "texstudio.ini"))
    for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        if base:
            out.append(os.path.join(base, "texstudio", "config", "texstudio.ini"))
    return [p for p in out if os.path.isfile(p)]


def texstudio_engines(ini_paths=None) -> dict[str, str]:
    """Trình biên dịch TeXstudio đang dùng: {'pdflatex': đường dẫn, …} – đọc «Tools\\Commands\\…» và
    «Tools\\SearchPaths» trong texstudio.ini. Lệnh không có đường dẫn đầy đủ (vd chỉ «pdflatex») thì bỏ qua
    phần lệnh, chỉ dùng thư mục trong SearchPaths."""
    found: dict[str, str] = {}
    for ini in (ini_paths if ini_paths is not None else texstudio_ini_paths()):
        try:
            with open(ini, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        dirs = []
        m = re.search(r"^Tools\\SearchPaths=(.*)$", text, re.M)
        if m:
            dirs = [d.strip().strip('"') for d in re.split(r"[;]", m.group(1)) if d.strip()]
        for eng in ENGINES:
            m = re.search(rf"^Tools\\Commands\\{eng}=(.*)$", text, re.M)
            if m:
                cmd = m.group(1).strip()
                if len(cmd) >= 2 and cmd[0] == cmd[-1] == '"':      # Qt lưu: "\"C:/…/pdflatex.exe\" -synctex=1 …"
                    cmd = cmd[1:-1]
                cmd = cmd.replace('\\"', '"').strip()
                exe = cmd[1:].split('"', 1)[0] if cmd.startswith('"') else cmd.split(" ", 1)[0]
                exe = exe.replace("/", os.sep)
                if os.path.isabs(exe) and os.path.isfile(exe):
                    found.setdefault(eng, exe)
                    continue
            for d in dirs:
                for name in (eng + ".exe", eng):
                    c = os.path.join(d.replace("/", os.sep), name)
                    if os.path.isfile(c):
                        found.setdefault(eng, c)
    return found


def find_engine(preferred: str = "auto", custom: str = "") -> str:
    """Đường dẫn trình biên dịch. preferred: auto | pdflatex | xelatex | lualatex.
    Thứ tự tìm: đường dẫn tự chỉ → theo cài đặt TeXstudio → PATH → thư mục cài mặc định MiKTeX/TeX Live."""
    if custom and os.path.isfile(custom):
        return custom
    order0 = ENGINES if preferred in ("", "auto") else (preferred,) + tuple(e for e in ENGINES if e != preferred)
    ts = texstudio_engines()
    for eng in order0:
        if eng in ts:
            return ts[eng]
    order = ENGINES if preferred in ("", "auto") else (preferred,) + tuple(e for e in ENGINES if e != preferred)
    for eng in order:
        p = shutil.which(eng)
        if p:
            return p
        for d in _candidate_dirs():
            for name in (eng + ".exe", eng):
                c = os.path.join(d, name)
                if os.path.isfile(c):
                    return c
    raise EngineMissing("Chưa tìm thấy LaTeX (pdflatex/xelatex). Máy có TeX Live hoặc MiKTeX (dùng chung với TeXstudio) "
                        "thì chỉ đường dẫn tới pdflatex.exe trong «Cài đặt biên dịch PDF», vd "
                        "C:\\texlive\\2019\\bin\\win32\\pdflatex.exe.")


def has_package(engine: str, name: str, extra_dirs=()) -> bool:
    for d in extra_dirs:
        if d and os.path.isfile(os.path.join(d, name)):
            return True
    kpse = os.path.join(os.path.dirname(engine), "kpsewhich" + (".exe" if engine.endswith(".exe") else ""))
    kpse = kpse if os.path.isfile(kpse) else shutil.which("kpsewhich")
    if not kpse:
        return True                   # không kiểm tra được ⇒ cứ thử biên dịch
    try:
        r = subprocess.run([kpse, name], capture_output=True, text=True, timeout=20, **NO_WINDOW)
        return bool(r.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return True


# ---------------------------------------------------------------- đọc lỗi
ERR_RE = re.compile(r"^! (.+)$")
LINE_RE = re.compile(r"^l\.(\d+)\s?(.*)$")
FRIENDLY = [
    (r"Undefined control sequence", "lệnh không tồn tại (gõ sai tên lệnh hoặc thiếu gói)"),
    (r"File `(.+?)' not found", r"thiếu file/gói \1"),
    (r"Missing \$ inserted", "thiếu dấu $ (công thức chưa đóng/mở đúng)"),
    (r"Missing \} inserted|Extra \}", "ngoặc { } không cân bằng"),
    (r"Extra alignment tab", "thừa dấu & trong bảng/hệ"),
    (r"Environment (\S+) undefined", r"môi trường \1 không tồn tại"),
    (r"\\begin\{(\S+)\} on input line (\d+) ended by \\end\{(\S+)\}", r"\\begin{\1} (dòng \2) lại đóng bằng \\end{\3}"),
    (r"Unicode character (.+?) \(U\+", r"kí tự \1 chưa được hỗ trợ (thiếu gói tiếng Việt / phông)"),
    (r"Emergency stop", "dừng khẩn cấp"),
]


def parse_log(log_text: str) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    lines = log_text.splitlines()
    for i, ln in enumerate(lines):
        m = ERR_RE.match(ln)
        if m:
            msg = m.group(1).strip()
            for pat, rep_ in FRIENDLY:
                m2 = re.search(pat, msg)
                if m2:
                    msg = f"{msg} – {m2.expand(rep_)}"
                    break
            where = ""
            for nxt in lines[i + 1:i + 12]:
                lm = LINE_RE.match(nxt)
                if lm:
                    where = f"Dòng {lm.group(1)}: "
                    break
            item = (where + msg)[:220]
            if item not in errors:
                errors.append(item)
        elif "LaTeX Warning: Reference" in ln or "Label(s) may have changed" in ln:
            warns.append(ln.strip()[:160])
    return errors, warns


# ---------------------------------------------------------------- biên dịch
def compile_tex(tex_path: str, engine: str | None = None, *, runs: int = 2, timeout: int = 180,
                extest_dir: str = "", clean: bool = True, preferred: str = "auto") -> BuildResult:
    import time
    t0 = time.time()
    tex_path = os.path.abspath(tex_path)
    work = os.path.dirname(tex_path)
    name = os.path.splitext(os.path.basename(tex_path))[0]
    res = BuildResult(tex_path, False)
    engine = engine or find_engine(preferred)
    with open(tex_path, encoding="utf-8", errors="ignore") as f:
        src = f.read()
    lite_copy = None
    from .packages import list_packages, package_dir
    pkg_dir = ""
    try:
        if list_packages():
            pkg_dir = package_dir()                    # TEMPLATE\GOI LENH: ex_test.sty mới nhất + gói riêng
    except OSError:
        pass
    search = [d for d in (extest_dir, pkg_dir) if d]
    if re.search(r"\\usepackage(\[[^\]]*\])?\{ex_test\}", src) and \
            not has_package(engine, "ex_test.sty", [work] + search):
        lite_copy = os.path.join(work, "ex_test.sty")
        shutil.copyfile(LITE_STY, lite_copy)
        res.used_lite = True
    env = dict(os.environ)
    if search:
        env["TEXINPUTS"] = os.pathsep.join(search) + os.pathsep + env.get("TEXINPUTS", "")
    os.makedirs(os.path.join(work, "ans"), exist_ok=True)        # ex_test ghi đáp án vào ans/
    cmd = [engine, "-interaction=nonstopmode", "-halt-on-error", os.path.basename(tex_path)]
    log = ""
    try:
        for _ in range(max(1, runs)):
            r = subprocess.run(cmd, cwd=work, capture_output=True, timeout=timeout, env=env, **NO_WINDOW)
            logf = os.path.join(work, name + ".log")
            log = open(logf, encoding="utf-8", errors="ignore").read() if os.path.exists(logf) else \
                r.stdout.decode("utf-8", "ignore")
            if r.returncode != 0:
                break
    except subprocess.TimeoutExpired:
        res.errors = [f"Quá {timeout} giây – có thể LaTeX đang chờ cài gói (MiKTeX) hoặc lặp vô hạn"]
        return res
    finally:
        if lite_copy and os.path.exists(lite_copy):
            os.remove(lite_copy)
    res.errors, res.warnings = parse_log(log)
    if len(res.errors) > 1:                         # bỏ dòng «Fatal error…» khi đã có lỗi cụ thể
        res.errors = [e for e in res.errors if "Fatal error occurred" not in e and "Emergency stop" not in e] \
            or res.errors
    pdf = os.path.join(work, name + ".pdf")
    res.ok = os.path.exists(pdf) and not res.errors
    res.pdf = pdf if os.path.exists(pdf) else None
    if clean:
        for ext in AUX_EXT:
            p = os.path.join(work, name + ext)
            if os.path.exists(p) and not (ext == ".log" and not res.ok):
                try:
                    os.remove(p)
                except OSError:
                    pass
    res.seconds = time.time() - t0
    return res


def preview_questions(questions, *, mode: str = "loigiai", template_path: str | None = None, engine=None,
                      extest_dir: str = "", title: str = "XEM TRƯỚC", out_dir: str | None = None) -> BuildResult:
    """Dựng tài liệu tạm cho một/nhiều câu (theo file mẫu đề) rồi biên dịch – dùng để xem nhanh PDF."""
    from .exporter import fill, load_template, questions_to_tex
    if not out_dir:                                   # như MyLT: TEMP\build – gom file tạm biên dịch một chỗ
        try:
            from .appdirs import path as app_path
            out_dir = tempfile.mkdtemp(prefix="xem_", dir=_ensure(app_path("tam", "build")))
        except OSError:
            out_dir = tempfile.mkdtemp(prefix="nhd_pdf_")
    os.makedirs(out_dir, exist_ok=True)
    body = questions_to_tex(list(questions), with_solution=(mode == "loigiai"))
    tex = fill(load_template(template_path), MODE=mode, NOI_DUNG=body, TEN_DE=title, MA_DE="—",
               THOI_GIAN="")
    p = os.path.join(out_dir, "xem_truoc.tex")
    with open(p, "w", encoding="utf-8") as f:
        f.write(tex)
    return compile_tex(p, engine, runs=1, extest_dir=extest_dir)


def _ensure(d: str) -> str:
    os.makedirs(d, exist_ok=True)
    return d


def compile_many(paths, engine=None, progress=None, **kw) -> list[BuildResult]:
    out = []
    for i, p in enumerate(paths, 1):
        if progress:
            progress(i, len(paths), p)
        out.append(compile_tex(p, engine, **kw))
    return out
