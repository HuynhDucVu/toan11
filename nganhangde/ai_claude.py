"""Nhà cung cấp AI: Claude (Anthropic) – dùng thư viện chính thức `anthropic`.

Cùng giao diện với GeminiClient: list_models(), generate_json(prompt, schema=None),
generate_from_pdf(pdf_bytes, prompt, schema=None).

* Mặc định mô hình claude-opus-5-5, effort "medium" (đổi được).
* Có `schema` ⇒ dùng structured outputs (output_config.format = json_schema): JSON trả về luôn đúng cấu trúc.
* Bật dự phòng phía máy chủ (fallbacks="default"): nếu mô hình từ chối vì bộ lọc an toàn,
  máy chủ tự chạy lại bằng mô hình dự phòng trong cùng lời gọi.
"""
from __future__ import annotations

import base64
import json

from .aiid import AIError, _loads_json

DEFAULT_MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class ClaudeClient:
    provider = "claude"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, effort: str = "medium", client=None):
        if not api_key and client is None:
            raise AIError("Chưa nhập khoá API Claude (lấy tại platform.claude.com → API keys)")
        try:
            import anthropic
        except ImportError:
            raise AIError("Thiếu thư viện anthropic – chạy: pip install anthropic") from None
        self._anthropic = anthropic
        self.model = (model or DEFAULT_MODEL).strip()
        self.effort = effort or "medium"
        self.client = client or anthropic.Anthropic(api_key=api_key.strip(), max_retries=3)

    # ------------------------------------------------------------------ tiện ích
    def list_models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list())
        except self._anthropic.APIError as e:
            raise AIError(self._msg(e)) from None

    def _msg(self, e) -> str:
        a = self._anthropic
        if isinstance(e, a.AuthenticationError):
            return "Claude: khoá API sai hoặc đã bị thu hồi"
        if isinstance(e, a.PermissionDeniedError):
            return "Claude: khoá API không có quyền dùng mô hình này"
        if isinstance(e, a.NotFoundError):
            return f"Claude: không có mô hình «{self.model}»"
        if isinstance(e, a.RateLimitError):
            return "Claude: vượt hạn mức – đợi một lát rồi thử lại"
        if isinstance(e, a.BadRequestError):
            return f"Claude: yêu cầu không hợp lệ – {getattr(e, 'message', e)}"
        if isinstance(e, a.APIStatusError):
            return f"Claude báo lỗi {e.status_code}: {getattr(e, 'message', e)}"
        if isinstance(e, a.APIConnectionError):
            return "Không kết nối được Claude (cần Internet)"
        return f"Claude: {e}"

    def _call(self, content, schema: dict | None) -> dict:
        kw = {"output_config": {"effort": self.effort}}
        if schema:
            kw["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        try:
            resp = self.client.beta.messages.create(
                model=self.model, max_tokens=16000, betas=[FALLBACK_BETA], fallbacks="default",
                messages=[{"role": "user", "content": content}], **kw)
        except self._anthropic.APIError as e:
            raise AIError(self._msg(e)) from None
        if resp.stop_reason == "refusal":
            raise AIError("Claude từ chối trả lời yêu cầu này")
        if resp.stop_reason == "max_tokens":
            raise AIError("Câu trả lời của Claude quá dài, bị cắt – giảm số câu mỗi lần gửi")
        text = "".join(b.text for b in resp.content if b.type == "text")
        if not text:
            raise AIError("Claude không trả lời (phản hồi rỗng)")
        return json.loads(text) if schema else _loads_json(text)

    # ------------------------------------------------------------------ giao diện chung
    def generate_json(self, prompt: str, schema: dict | None = None) -> dict:
        return self._call(prompt, schema)

    def generate_from_pdf(self, pdf_bytes: bytes, prompt: str, schema: dict | None = None) -> dict:
        doc = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                              "data": base64.standard_b64encode(pdf_bytes).decode("ascii")}}
        return self._call([doc, {"type": "text", "text": prompt}], schema)
