import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from ..paths import resource_path


@dataclass
class TeXLogDiagnostic:
    line_no: int | None
    summary: str
    suggestion_vi: str


@dataclass
class PdfBuildResult:
    success: bool
    pdf_path: str | None
    compiler: str
    log_path: str | None = None
    diagnostics: list[TeXLogDiagnostic] = field(default_factory=list)
    stderr: str = ""


def detect_tex_compiler(preferred: str = "pdflatex") -> str | None:
    """Tự động tìm trình biên dịch LaTeX (PATH, TeX Live 2018-2026 trên C:/D:, MiKTeX)."""
    if preferred and Path(preferred).is_file():
        return str(Path(preferred))

    candidates = list(dict.fromkeys([preferred or "pdflatex", "pdflatex", "xelatex", "lualatex"]))
    for cmd in candidates:
        found = shutil.which(cmd)
        if found:
            return found

    local_app = os.environ.get("LOCALAPPDATA", "")
    search_dirs: list[Path] = [
        Path(local_app) / "Programs" / "MiKTeX" / "miktex" / "bin" / "x64",
        Path(r"C:\Program Files\MiKTeX\miktex\bin\x64"),
        Path(r"C:\Program Files\MiKTeX 2.9\miktex\bin\x64"),
        Path("/Library/TeX/texbin"),
    ]
    # Quét tự động TeX Live trên ổ C: và D: (cả win32 lẫn windows)
    for drive in ("C:", "D:"):
        tl_root = Path(f"{drive}\\texlive")
        if tl_root.exists():
            for year_dir in sorted(tl_root.iterdir(), reverse=True):
                if year_dir.is_dir():
                    search_dirs.append(year_dir / "bin" / "windows")
                    search_dirs.append(year_dir / "bin" / "win32")

    for d in search_dirs:
        if not d.exists():
            continue
        for cmd in candidates:
            exe = d / (f"{cmd}.exe" if os.name == "nt" else cmd)
            if exe.exists():
                return str(exe)
    return None


def unwrap_tex_log(log_text: str) -> str:
    merged: list[str] = []
    for ln in log_text.splitlines():
        if merged and len(merged[-1]) == 79 and not ln.startswith(("!", "l.", "LaTeX ", "Package ")):
            merged[-1] += ln
        else:
            merged.append(ln)
    return "\n".join(merged)


def diagnose_tex_log(log_text: str) -> list[TeXLogDiagnostic]:
    lines = unwrap_tex_log(log_text).splitlines()
    diags: list[TeXLogDiagnostic] = []
    for i, ln in enumerate(lines):
        # Hỗ trợ cả định dạng "! Error" lẫn "-file-line-error" (file.tex:12: Error)
        err: str | None = None
        line_no: int | None = None
        if ln.startswith("! "):
            err = ln[2:].strip()
            for look in lines[i + 1 : i + 6]:
                m = re.match(r"^l\.(\d+)\b", look)
                if m:
                    line_no = int(m.group(1))
                    break
        else:
            m_fl = re.match(r"^[^:\n]+\.tex:(\d+):\s*(.+)$", ln)
            if m_fl:
                line_no = int(m_fl.group(1))
                err = m_fl.group(2).strip()

        if err:
            if "Undefined control sequence" in err:
                hint = "Lệnh LaTeX chưa khai báo hoặc sai chính tả."
            elif "Missing $ inserted" in err:
                hint = "Thiếu dấu '$' mở/đóng chế độ toán học."
            elif "File `" in err and "not found" in err:
                hint = "Thiếu gói .sty hoặc tệp hình ảnh (kiểm tra nhd_extest.sty / \\includegraphics)."
            elif "Runaway argument" in err or "File ended while scanning" in err:
                hint = "Thiếu ngoặc nhọn đóng '}' ở \\choice, \\choiceTF hoặc \\loigiai."
            else:
                hint = "Kiểm tra cú pháp LaTeX tại dòng báo lỗi."
            diags.append(TeXLogDiagnostic(line_no, err, hint))
    return diags


def compile_tex_to_pdf(
    tex_path: str,
    compiler: str = "pdflatex",
    passes: int = 1,
    timeout_sec: int = 90,
) -> PdfBuildResult:
    exe = detect_tex_compiler(compiler)
    if not exe:
        return PdfBuildResult(
            False,
            None,
            compiler,
            diagnostics=[
                TeXLogDiagnostic(
                    None,
                    "Không tìm thấy pdflatex / xelatex / lualatex",
                    "Hãy kiểm tra cài đặt TeX Live (VD: C:\\texlive\\2019\\bin\\win32) hoặc MiKTeX.",
                )
            ],
            stderr="Không tìm thấy trình biên dịch LaTeX trên máy.",
        )

    tex_file = Path(tex_path).resolve()
    env = os.environ.copy()
    sep = ";" if os.name == "nt" else ":"
    tpl_dir = resource_path("nganhangde/templates").as_posix()
    old_ti = env.get("TEXINPUTS", "")
    env["TEXINPUTS"] = f".{sep}{tpl_dir}{sep}{old_ti}{sep}"

    # Bỏ -file-line-error để giữ log chuẩn và tránh ẩn lỗi; dùng CREATE_NO_WINDOW trên Windows
    cmd = [exe, "-interaction=nonstopmode", "-halt-on-error", tex_file.name]
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" and hasattr(subprocess, "CREATE_NO_WINDOW") else 0

    ok = True
    last_out = ""
    for _ in range(max(1, passes)):
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(tex_file.parent),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_sec,
                creationflags=creationflags,
            )
            stdout_txt = proc.stdout.decode("utf-8", errors="replace") if proc.stdout else ""
            stderr_txt = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
            # pdflatex ghi lỗi chủ yếu ra stdout
            last_out = (stderr_txt.strip() + "\n" + stdout_txt[-1200:].strip()).strip()
            if proc.returncode != 0:
                ok = False
                break
        except subprocess.TimeoutExpired:
            return PdfBuildResult(
                False,
                None,
                exe,
                diagnostics=[TeXLogDiagnostic(None, "Quá thời gian biên dịch", f"Vượt {timeout_sec} giây.")],
                stderr=f"Quá thời gian biên dịch ({timeout_sec}s).",
            )
        except Exception as exc:
            return PdfBuildResult(
                False,
                None,
                exe,
                diagnostics=[TeXLogDiagnostic(None, "Lỗi gọi trình biên dịch", str(exc))],
                stderr=str(exc),
            )

    pdf_f = tex_file.with_suffix(".pdf")
    log_f = tex_file.with_suffix(".log")
    diags = diagnose_tex_log(log_f.read_text(encoding="utf-8", errors="ignore")) if log_f.exists() else []
    return PdfBuildResult(
        ok and pdf_f.exists(),
        str(pdf_f) if pdf_f.exists() else None,
        exe,
        str(log_f) if log_f.exists() else None,
        diags,
        last_out,
    )


def open_pdf_file(pdf_path: str | Path) -> None:
    """Mở tệp PDF bằng trình xem mặc định của hệ điều hành."""
    p = str(Path(pdf_path).resolve())
    if os.name == "nt":
        os.startfile(p)  # type: ignore[attr-defined]
    else:
        opener = shutil.which("xdg-open") or shutil.which("open")
        if opener:
            subprocess.Popen([opener, p])


def compile_tikz_snippet_to_pdf(
    tikz_code: str,
    out_dir: str | Path | None = None,
    compiler: str = "pdflatex",
) -> PdfBuildResult:
    """Bọc đoạn mã TikZ vào lớp standalone (tương thích TeX Live 2019) và biên dịch ra PDF."""
    import tempfile
    import uuid
    target_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "toan11_tikz_preview"
    target_dir.mkdir(parents=True, exist_ok=True)
    # Dọn nhẹ các tệp cũ không bị khóa
    for old_f in target_dir.glob("preview_tikz_*.*"):
        try:
            old_f.unlink()
        except OSError:
            pass
    tex_file = target_dir / f"preview_tikz_{uuid.uuid4().hex[:8]}.tex"
    # Dùng \usepackage[utf8]{vietnam} thay vì babel để tránh xung đột ký tự active với TikZ/tkz-tab trên TeX Live 2019
    doc = (
        "\\documentclass[tikz,border=4pt]{standalone}\n"
        "\\usepackage[utf8]{vietnam}\n"
        "\\usepackage{amsmath,amssymb,amsfonts}\n"
        "\\usepackage{tikz,tkz-tab,pgfplots}\n"
        "\\usetikzlibrary{calc,angles,quotes,intersections,patterns,arrows.meta,positioning}\n"
        "\\pgfplotsset{compat=1.16}\n"
        "\\begin{document}\n"
        f"{tikz_code}\n"
        "\\end{document}\n"
    )
    tex_file.write_text(doc, encoding="utf-8")
    return compile_tex_to_pdf(str(tex_file), compiler=compiler, passes=1, timeout_sec=60)
