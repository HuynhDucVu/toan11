from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


@dataclass
class Tikz2PicConfig:
    dpi: int = 150
    question_color: str = "#006666"
    solution_color: str = "#80FF80"
    compiler: str = "pdflatex"
    border_pt: int = 2
    replace_in_tex: bool = False


@dataclass
class TikzExportItem:
    index: int
    in_solution: bool
    image_path: Path
    ok: bool
    error: str = ""


STANDALONE_TEMPLATE = r"""\documentclass[tikz,border={border}pt]{{standalone}}
\usepackage[utf8]{{inputenc}}
\usepackage[vietnamese]{{babel}}
\usepackage{{amsmath,amssymb,amsfonts}}
\usepackage{{xcolor}}
\usepackage{{tikz,tkz-tab,tkz-euclide,pgfplots}}
\usetikzlibrary{{calc,angles,quotes,intersections,patterns,arrows.meta,positioning}}
\pgfplotsset{{compat=1.16}}
\definecolor{{myltdefault}}{{HTML}}{{{hex_color}}}
\begin{{document}}
\color{{myltdefault}}
{tikz_code}
\end{{document}}
"""


def _find_loigiai_spans(tex_content: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for m in re.finditer(r"\\loigiai\s*\{", tex_content):
        start = m.start()
        idx = m.end() - 1
        depth = 0
        while idx < len(tex_content):
            ch = tex_content[idx]
            if ch == "{" and (idx == 0 or tex_content[idx - 1] != "\\"):
                depth += 1
            elif ch == "}" and (idx == 0 or tex_content[idx - 1] != "\\"):
                depth -= 1
                if depth == 0:
                    spans.append((start, idx + 1))
                    break
            idx += 1
    return spans


def _is_inside_spans(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(s <= pos < e for s, e in spans)


def _pdf_to_png(pdf_path: Path, png_path: Path, dpi: int) -> None:
    if fitz is not None:
        doc = fitz.open(str(pdf_path))
        try:
            page = doc[0]
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            pix.save(str(png_path))
        finally:
            doc.close()
        return

    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("Cần cài PyMuPDF (pip install pymupdf) hoặc pdftoppm.")
    prefix = str(png_path.with_suffix(""))
    subprocess.run(
        [pdftoppm, "-png", "-r", str(dpi), "-singlefile", str(pdf_path), prefix],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def export_tikz_to_png(
    tex_content: str,
    output_dir: Path,
    cfg: Tikz2PicConfig | None = None,
) -> tuple[list[TikzExportItem], str]:
    cfg = cfg or Tikz2PicConfig()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    loigiai_spans = _find_loigiai_spans(tex_content)
    pattern = re.compile(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", re.DOTALL)
    matches = list(pattern.finditer(tex_content))

    results: list[TikzExportItem] = []
    replacements: list[tuple[int, int, str]] = []

    with tempfile.TemporaryDirectory(prefix="tikz2pic_") as tmp:
        tmp_dir = Path(tmp)
        for i, m in enumerate(matches, start=1):
            in_sol = _is_inside_spans(m.start(), loigiai_spans)
            raw_hex = (cfg.solution_color if in_sol else cfg.question_color).lstrip("#").upper()
            prefix = "lg" if in_sol else "de"
            img_name = f"hinh_{prefix}_{i:03d}.png"
            img_path = output_dir / img_name

            standalone_tex = STANDALONE_TEMPLATE.format(
                border=cfg.border_pt,
                hex_color=raw_hex,
                tikz_code=m.group(0),
            )
            tex_file = tmp_dir / f"fig_{i:03d}.tex"
            pdf_file = tmp_dir / f"fig_{i:03d}.pdf"
            tex_file.write_text(standalone_tex, encoding="utf-8")

            try:
                proc = subprocess.run(
                    [cfg.compiler, "-interaction=nonstopmode", "-halt-on-error", tex_file.name],
                    cwd=str(tmp_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                )
                if proc.returncode != 0 or not pdf_file.exists():
                    err_msg = proc.stdout.decode("utf-8", errors="ignore")[-400:]
                    results.append(TikzExportItem(i, in_sol, img_path, False, err_msg))
                    continue

                _pdf_to_png(pdf_file, img_path, cfg.dpi)
                results.append(TikzExportItem(i, in_sol, img_path, True))

                if cfg.replace_in_tex:
                    rel_path = f"{output_dir.name}/{img_name}"
                    replacements.append(
                        (m.start(), m.end(), f"\\includegraphics[scale=0.75]{{{rel_path}}}")
                    )
            except Exception as exc:
                results.append(TikzExportItem(i, in_sol, img_path, False, str(exc)))

    new_tex = tex_content
    if cfg.replace_in_tex and replacements:
        for start, end, rep in reversed(replacements):
            new_tex = new_tex[:start] + rep + new_tex[end:]

    return results, new_tex
