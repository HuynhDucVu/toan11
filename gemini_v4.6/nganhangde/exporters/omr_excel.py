import csv
from dataclasses import dataclass
from typing import Sequence
from ..core.generator import ExamVariant


@dataclass(frozen=True)
class OMRProfile:
    code: str
    label: str
    max_tn: int
    max_ds: int
    max_kq: int
    exam_code_digits: int = 4


OMR_PROFILES: dict[str, OMRProfile] = {
    "BGD_2025_A4": OMRProfile("BGD_2025_A4", "Phiếu Bộ GD 2025 / QM2025 A4", 40, 8, 6, 4),
    "QM2025_TOAN_12_4_6": OMRProfile("QM2025_TOAN_12_4_6", "Phiếu QM2025 Toán rút gọn / Ngang", 12, 4, 6, 4),
    "QM2025_HSG_30_10_10": OMRProfile("QM2025_HSG_30_10_10", "Phiếu QM2025 HSG (30.10.10)", 30, 10, 10, 4),
    "QM2025_KHTN_10": OMRProfile("QM2025_KHTN_10", "Phiếu QM2025 KHTN lên 10", 16, 3, 12, 4),
}


def check_omr_capacity(variant: ExamVariant, profile_key: str = "BGD_2025_A4") -> list[str]:
    p = OMR_PROFILES[profile_key]
    warns = []
    if len(variant.key_tn) > p.max_tn:
        warns.append(f"Mã {variant.code}: Phần I ({len(variant.key_tn)}) > {p.max_tn} của {p.label}.")
    if len(variant.key_ds) > p.max_ds:
        warns.append(f"Mã {variant.code}: Phần II ({len(variant.key_ds)}) > {p.max_ds} của {p.label}.")
    if len(variant.key_kq) > p.max_kq:
        warns.append(f"Mã {variant.code}: Phần III ({len(variant.key_kq)}) > {p.max_kq} của {p.label}.")
    if len(variant.code) != p.exam_code_digits:
        warns.append(f"Mã {variant.code}: dài {len(variant.code)} chữ số (chuẩn phiếu {p.exam_code_digits} số).")
    return warns


def export_answer_csv_bom(variants: Sequence[ExamVariant], out_csv: str) -> None:
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if not variants:
            w.writerow(["Phần", "Câu"])
            return
        w.writerow(["Phần", "Câu"] + [f"Mã {v.code}" for v in variants])
        for i in range(len(variants[0].key_tn)):
            w.writerow(["Phần I", i + 1] + [v.key_tn[i][1] for v in variants])
        for i in range(len(variants[0].key_ds)):
            w.writerow(["Phần II", i + 1] + [v.key_ds[i][1] for v in variants])
        for i in range(len(variants[0].key_kq)):
            w.writerow(["Phần III", i + 1] + [v.key_kq[i][1] for v in variants])


def export_omr_excel(
    variants: Sequence[ExamVariant], out_xlsx: str, exam_title: str = "Đề kiểm tra Toán",
    profile_key: str = "BGD_2025_A4", template_xlsx: str | None = None,
) -> list[str]:
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill

    warns = [w for v in variants for w in check_omr_capacity(v, profile_key)]
    if template_xlsx:
        wb = openpyxl.load_workbook(template_xlsx)
        ws = wb.active
        r = ws.max_row + 1
        for v in variants:
            vals = [v.code] + [a for _, a in v.key_tn] + [a for _, a in v.key_ds] + [a for _, a in v.key_kq]
            for c_i, val in enumerate(vals, 1):
                ws.cell(r, c_i, val)
            r += 1
        wb.save(out_xlsx)
        return warns

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BangDapAn"
    headers = ["Phần", "Câu"] + [f"Mã {v.code}" for v in variants]
    ws.append(headers)
    fill = PatternFill("solid", fgColor="1F4E78")
    for c in range(1, len(headers) + 1):
        cell = ws.cell(1, c)
        cell.fill, cell.font, cell.alignment = fill, Font(color="FFFFFF", bold=True), Alignment(horizontal="center")
    if variants:
        for i in range(len(variants[0].key_tn)):
            ws.append(["Phần I", i + 1] + [v.key_tn[i][1] for v in variants])
        for i in range(len(variants[0].key_ds)):
            ws.append(["Phần II", i + 1] + [v.key_ds[i][1] for v in variants])
        for i in range(len(variants[0].key_kq)):
            ws.append(["Phần III", i + 1] + [v.key_kq[i][1] for v in variants])
    wi = wb.create_sheet("Thong tin")
    wi.append(["Thuộc tính", "Giá trị"])
    wi.append(["Tên đề thi", exam_title])
    wi.append(["Mẫu phiếu OMR", OMR_PROFILES[profile_key].label])
    wi.append(["Số mã đề", len(variants)])
    wi.append(["Phần I", len(variants[0].key_tn) if variants else 0])
    wi.append(["Phần II", len(variants[0].key_ds) if variants else 0])
    wi.append(["Phần III", len(variants[0].key_kq) if variants else 0])
    wb.save(out_xlsx)
    return warns
