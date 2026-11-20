"""Nhà cung cấp AI theo chuẩn «OpenAI Chat Completions»: OpenAI, DeepSeek, Grok (xAI).

Gọi REST bằng urllib (không cần thư viện ngoài). Cùng giao diện list_models() / generate_json().
Chưa hỗ trợ đọc PDF (dùng Gemini hoặc Claude cho chức năng PDF → LaTeX).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from .aiid import AIError, _loads_json

ENDPOINTS = {
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini", "platform.openai.com/api-keys"),
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat", "platform.deepseek.com/api_keys"),
    "grok": ("https://api.x.ai/v1", "grok-3-mini", "console.x.ai"),
}
NAMES = {"openai": "OpenAI", "deepseek": "DeepSeek", "grok": "Grok (xAI)"}


class OpenAICompatClient:
    def __init__(self, provider: str, api_key: str, model: str = "", transport=None):
        if provider not in ENDPOINTS:
            raise AIError(f"Không hỗ trợ nhà cung cấp «{provider}»")
        base, default, where = ENDPOINTS[provider]
        if not api_key:
            raise AIError(f"Chưa nhập khoá API {NAMES[provider]} (lấy tại {where})")
        self.provider, self.base, self.key = provider, base, api_key.strip()
        self.model = (model or default).strip()
        self.http = transport or self._http

    def _http(self, path: str, data: dict | None = None) -> dict:
        body = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(self.base + path, data=body, method="POST" if body else "GET",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": f"Bearer {self.key}"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:  # noqa: BLE001
                msg = ""
            hint = {401: "khoá API sai", 402: "tài khoản hết tiền", 403: "không có quyền",
                    404: "không có mô hình này", 429: "vượt hạn mức – thử lại sau"}.get(e.code, "")
            raise AIError(f"{NAMES[self.provider]} báo lỗi {e.code}: {hint} {msg}".strip()) from None
        except urllib.error.URLError as e:
            raise AIError(f"Không kết nối được {NAMES[self.provider]}: {e.reason}") from None

    def list_models(self) -> list[str]:
        return sorted(m["id"] for m in self.http("/models").get("data", []))

    def generate_json(self, prompt: str, schema: dict | None = None, retries: int = 2) -> dict:
        if schema:
            prompt += "\n\nJSON phải đúng lược đồ sau:\n" + json.dumps(schema, ensure_ascii=False)
        body = {"model": self.model, "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}}
        last = None
        for attempt in range(retries + 1):
            try:
                data = self.http("/chat/completions", body)
                text = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
                if not text:
                    raise AIError(f"{NAMES[self.provider]} không trả lời (phản hồi rỗng)")
                return _loads_json(text)
            except AIError as e:
                last = e
                if "429" in str(e) or " 5" in str(e)[:30]:
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        raise last

    def generate_from_pdf(self, pdf_bytes: bytes, prompt: str, schema: dict | None = None) -> dict:
        raise AIError(f"{NAMES[self.provider]} chưa dùng được cho PDF – chọn Gemini hoặc Claude")
