import concurrent.futures
import json
import os
import tempfile
from dataclasses import dataclass, field
from typing import Callable
from .providers import AIConfig, AIProviderClient, AIResult, AIUsage

OCR_EXTEST_PROMPT = (
    "Trích xuất toàn bộ câu hỏi Toán trong PDF sang LaTeX chuẩn ex_test v3.3.4: "
    "dùng \\begin{ex}...\\end{ex}, \\choice, \\choiceTF + \\begin{itemchoice}\\itemch, \\shortans (dấu phẩy thập phân). Chỉ xuất mã LaTeX."
)


@dataclass
class OCRChunkResult:
    chunk_index: int
    start_page: int
    end_page: int
    tex: str
    truncated: bool = False
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass
class PDFOCRSessionResult:
    full_tex: str
    chunks: list[OCRChunkResult]
    total_usage: AIUsage
    truncated_chunks: list[int] = field(default_factory=list)


def split_pdf_into_chunks(pdf_path: str, chunk_pages: int = 10, work_dir: str | None = None) -> list[tuple[int, int, str]]:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("Thiếu PyMuPDF. Chạy: pip install pymupdf") from exc
    out_dir = work_dir or tempfile.mkdtemp(prefix="toan11_ocr_")
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    slices: list[tuple[int, int, str]] = []
    for start in range(0, len(doc), chunk_pages):
        end = min(start + chunk_pages, len(doc))
        sub = fitz.open()
        sub.insert_pdf(doc, from_page=start, to_page=end - 1)
        fp = os.path.join(out_dir, f"chunk_{start + 1:04d}_{end:04d}.pdf")
        sub.save(fp)
        sub.close()
        slices.append((start + 1, end, fp))
    doc.close()
    return slices


def ocr_pdf_to_extest(
    pdf_path: str, ai_config: AIConfig, chunk_pages: int = 10, max_concurrency: int = 2,
    checkpoint_path: str | None = None, on_progress: Callable[[int, int, str], None] | None = None,
    chunk_processor: Callable[[str, str], AIResult] | None = None,
) -> PDFOCRSessionResult:
    slices = split_pdf_into_chunks(pdf_path, chunk_pages=chunk_pages)
    completed: dict[int, OCRChunkResult] = {}
    if checkpoint_path and os.path.exists(checkpoint_path):
        for it in json.load(open(checkpoint_path, encoding="utf-8")).get("chunks", []):
            u = it.get("usage", {})
            completed[it["chunk_index"]] = OCRChunkResult(it["chunk_index"], it["start_page"], it["end_page"], it["tex"], it.get("truncated", False), AIUsage(u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("total_tokens", 0)))

    client = AIProviderClient(ai_config) if chunk_processor is None else None

    def _run_one(idx: int, sp: int, ep: int, fp: str) -> OCRChunkResult:
        if chunk_processor is not None:
            res = chunk_processor(fp, OCR_EXTEST_PROMPT)
        else:
            uploaded = client._get_gemini().files.upload(file=fp)
            res = client.stream_gemini_multimodal(uploaded, OCR_EXTEST_PROMPT)
        return OCRChunkResult(idx, sp, ep, res.text.strip(), "MAX_TOKENS" in (res.finish_reason or "").upper(), res.usage)

    pending = [(i, sp, ep, fp) for i, (sp, ep, fp) in enumerate(slices) if i not in completed]
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(max_concurrency, 2))) as pool:
        futs = [pool.submit(_run_one, i, sp, ep, fp) for i, sp, ep, fp in pending]
        for fut in concurrent.futures.as_completed(futs):
            cr = fut.result()
            completed[cr.chunk_index] = cr
            if checkpoint_path:
                json.dump({"source_pdf": pdf_path, "chunks": [{"chunk_index": c.chunk_index, "start_page": c.start_page, "end_page": c.end_page, "tex": c.tex, "truncated": c.truncated, "usage": c.usage.__dict__} for _, c in sorted(completed.items())]}, open(checkpoint_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            if on_progress:
                on_progress(len(completed), len(slices), f"Xong trang {cr.start_page}-{cr.end_page}")

    ordered = [completed[i] for i in sorted(completed)]
    tot_u = AIUsage(sum(c.usage.input_tokens for c in ordered), sum(c.usage.output_tokens for c in ordered), sum(c.usage.total_tokens for c in ordered))
    return PDFOCRSessionResult("\n\n".join(f"% === TRANG {c.start_page}-{c.end_page} ===\n{c.tex}" for c in ordered), ordered, tot_u, [c.chunk_index for c in ordered if c.truncated])
