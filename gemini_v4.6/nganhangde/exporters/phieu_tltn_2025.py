from __future__ import annotations
from pathlib import Path
import re
import shutil
from ..paths import resource_path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    PdfReader = None
    PdfWriter = None


PHIEU_TEMPLATES = {
    "1mat": "phieu_2025_1mat.pdf",
    "full": "phieu_2025_full.pdf",
}


def get_template_path(template_key: str = "1mat") -> Path:
    filename = PHIEU_TEMPLATES.get(template_key, PHIEU_TEMPLATES["1mat"])
    path = resource_path(f"nganhangde/assets/phieu_2025/{filename}")
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy mẫu phiếu tại: {path}")
    return path


def inject_phieu_into_tex(
    tex_content: str,
    template_key: str = "1mat",
    pages: str = "-",
    copy_to_dir: Path | None = None,
) -> str:
    tpl_path = get_template_path(template_key)

    if copy_to_dir is not None:
        copy_to_dir = Path(copy_to_dir)
        copy_to_dir.mkdir(parents=True, exist_ok=True)
        dest = copy_to_dir / tpl_path.name
        if not dest.exists():
            shutil.copy2(tpl_path, dest)
        latex_pdf_ref = tpl_path.name
    else:
        latex_pdf_ref = tpl_path.as_posix()

    if not re.search(r"\\usepackage(\[[^\]]*\])?\{[^}]*\bpdfpages\b[^}]*\}", tex_content):
        if r"\begin{document}" in tex_content:
            tex_content = tex_content.replace(
                r"\begin{document}",
                "\\usepackage{pdfpages}\n\\begin{document}",
                1,
            )

    include_cmd = (
        "\n% --- Tự động chèn phiếu TLTN THPT QG 2025 ---\n"
        f"\\includepdf[pages={pages}]{{{latex_pdf_ref}}}\n"
        r"\end{document}"
    )

    if r"\end{document}" in tex_content:
        tex_content = tex_content.replace(r"\end{document}", include_cmd, 1)
    else:
        tex_content += include_cmd

    return tex_content


def append_phieu_to_pdf(
    exam_pdf_path: Path,
    template_key: str = "1mat",
    output_pdf_path: Path | None = None,
    page_indices: list[int] | None = None,
) -> Path:
    if PdfReader is None or PdfWriter is None:
        raise RuntimeError("Chưa cài thư viện pypdf. Chạy lệnh: pip install pypdf")

    exam_pdf = Path(exam_pdf_path)
    if not exam_pdf.exists():
        raise FileNotFoundError(f"Không tìm thấy tệp đề PDF: {exam_pdf}")

    tpl_path = get_template_path(template_key)
    out_path = Path(output_pdf_path) if output_pdf_path else exam_pdf

    writer = PdfWriter()
    exam_reader = PdfReader(str(exam_pdf))
    for page in exam_reader.pages:
        writer.add_page(page)

    tpl_reader = PdfReader(str(tpl_path))
    if page_indices is None:
        for page in tpl_reader.pages:
            writer.add_page(page)
    else:
        for idx in page_indices:
            if 0 <= idx < len(tpl_reader.pages):
                writer.add_page(tpl_reader.pages[idx])

    tmp_path = out_path.with_suffix(".tmp.pdf")
    with open(tmp_path, "wb") as f:
        writer.write(f)
    tmp_path.replace(out_path)
    return out_path
