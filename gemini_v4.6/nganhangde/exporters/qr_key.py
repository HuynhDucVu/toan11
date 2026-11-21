import json
from ..core.generator import ExamVariant


def encode_qr_payload(variant: ExamVariant, fmt: str = "compact") -> str:
    p1 = "".join(a for _, a in variant.key_tn)
    p2 = "|".join(a for _, a in variant.key_ds)
    p3 = "|".join(a for _, a in variant.key_kq)
    if fmt == "json":
        return json.dumps({"code": variant.code, "p1": p1, "p2": [a for _, a in variant.key_ds], "p3": [a for _, a in variant.key_kq]}, ensure_ascii=False, separators=(",", ":"))
    return f"MD:{variant.code};P1:{p1};P2:{p2};P3:{p3}"


def generate_qr_png(variant: ExamVariant, out_png: str, fmt: str = "compact") -> str:
    try:
        import qrcode
    except ImportError as exc:
        raise RuntimeError("Thiếu thư viện QR. Chạy: pip install qrcode[pil]") from exc
    payload = encode_qr_payload(variant, fmt=fmt)
    qrcode.make(payload).save(out_png)
    return payload
