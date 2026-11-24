"""Mathpix: ảnh/PDF → LaTeX qua REST API (cần app_id và app_key của người dùng)."""
from __future__ import annotations

import base64
import json
import mimetypes
import urllib.request

API = "https://api.mathpix.com/v3/text"


class MathpixError(RuntimeError):
    pass


def build_request(path: str, data: bytes | None = None) -> dict:
    data = data if data is not None else open(path, "rb").read()
    mime = mimetypes.guess_type(path)[0] or "image/png"
    src = f"data:{mime};base64," + base64.b64encode(data).decode()
    return {"src": src, "formats": ["text"], "math_inline_delimiters": ["$", "$"],
            "math_display_delimiters": ["\\[", "\\]"], "rm_spaces": True}


def image_to_latex(path: str, app_id: str, app_key: str, *, data: bytes | None = None, timeout: int = 60) -> str:
    if not app_id or not app_key:
        raise MathpixError("Chưa nhập app_id / app_key của Mathpix (Cài đặt → Giao diện & Mathpix).")
    body = json.dumps(build_request(path, data)).encode()
    req = urllib.request.Request(API, body, {"Content-Type": "application/json", "app_id": app_id, "app_key": app_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            res = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise MathpixError(f"Gọi Mathpix thất bại: {e}") from e
    if res.get("error"):
        raise MathpixError(str(res["error"]))
    return str(res.get("text", "")).strip()
