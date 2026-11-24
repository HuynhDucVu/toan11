import os
import re
import shutil
from dataclasses import dataclass, field
from typing import Sequence
from ..core.generator import ExamVariant
from .qr_key import generate_qr_png

INCLUDEGRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
SECTION_HEADERS = {
    "TN": r"\section*{PHẦN I. Câu trắc nghiệm nhiều phương án lựa chọn.}",
    "DS": r"\section*{PHẦN II. Câu trắc nghiệm đúng sai.}",
    "KQ": r"\section*{PHẦN III. Câu trắc nghiệm trả lời ngắn.}",
    "TL": r"\section*{PHẦN IV. Tự luận.}",
}


@dataclass
class TexExportResult:
    created_files: list[str] = field(default_factory=list)
    copied_assets: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def export_exam_tex_suite(
    variants: Sequence[ExamVariant], out_dir: str, exam_title: str = "ĐỀ KIỂM TRA ĐỊNH KÌ",
    template_path: str | None = None, solution_mode: str = "loigiai", extest_version: str = "3.3.4",
    asset_source_dir: str | None = None, embed_qr_in_solution: bool = False,
) -> TexExportResult:
    os.makedirs(out_dir, exist_ok=True)
    res = TexExportResult()
    if solution_mode == "solcolor" and extest_version.startswith("3.0.7"):
        res.warnings.append("Cảnh báo: [solcolor] có thể lỗi trên ex_test v3.0.7; nên dùng [loigiai] hoặc v3.3.4.")
    tpl = open(template_path, encoding="utf-8").read() if template_path and os.path.exists(template_path) else None

    for v in variants:
        def build(with_sol: bool) -> str:
            buckets = {k: [q for q in v.questions if q.qtype == k] for k in ("TN", "DS", "KQ", "TL")}
            out = []
            for k in ("TN", "DS", "KQ", "TL"):
                if buckets[k]:
                    out.append(SECTION_HEADERS[k])
                    out.extend(q.to_latex(include_solution=with_sol) for q in buckets[k])
            return "\n\n".join(out)

        body_de, body_lg = build(False), build(True)
        if asset_source_dir:
            for rel in INCLUDEGRAPHICS_RE.findall(body_lg):
                src = rel if os.path.isabs(rel) else os.path.join(asset_source_dir, rel)
                if not os.path.exists(src):
                    res.warnings.append(f"Thiếu tệp ảnh: {rel}")
                    continue
                dst = os.path.join(out_dir, os.path.basename(rel) if os.path.isabs(rel) else rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.abspath(src) != os.path.abspath(dst):
                    shutil.copy2(src, dst)
                    res.copied_assets.append(dst)

        if embed_qr_in_solution:
            qr_name = f"qr_{v.code}.png"
            qr_path = os.path.join(out_dir, qr_name)
            try:
                generate_qr_png(v, qr_path)
                res.created_files.append(qr_path)
                body_lg += f"\n\n\\begin{{center}}\\textbf{{Mã QR đáp án — Mã {v.code}}}\\\\[4pt]\\includegraphics[width=3.2cm]{{{qr_name}}}\\end{{center}}"
            except RuntimeError as exc:
                res.warnings.append(str(exc))

        for mode_s, fname, content in [("dethi", f"de_{v.code}.tex", body_de), (solution_mode, f"loigiai_{v.code}.tex", body_lg)]:
            full = tpl.replace("<<TEN_DE>>", exam_title).replace("<<MA_DE>>", v.code).replace("<<MODE>>", mode_s).replace("<<NOI_DUNG>>", content) if tpl else f"% {exam_title} | {v.code}\n\n{content}\n"
            out_p = os.path.join(out_dir, fname)
            open(out_p, "w", encoding="utf-8").write(full)
            res.created_files.append(out_p)
    return res
