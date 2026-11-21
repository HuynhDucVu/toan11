import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class AIUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AIResult:
    text: str
    parsed: object | None = None
    finish_reason: str = "STOP"
    usage: AIUsage = field(default_factory=AIUsage)


@dataclass
class AIConfig:
    provider: str = "gemini"
    api_key: str = ""
    model: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_output_tokens: int = 32768
    thinking_budget: int | None = None
    max_retries: int = 3


class AIProviderClient:
    OPENAI_URLS = {
        "openai": "https://api.openai.com/v1/chat/completions",
        "deepseek": "https://api.deepseek.com/v1/chat/completions",
        "grok": "https://api.x.ai/v1/chat/completions",
    }

    def __init__(self, config: AIConfig):
        self.config = config
        self._gemini = None

    def _get_gemini(self):
        if self._gemini is None:
            try:
                from google import genai
            except ImportError as exc:
                raise RuntimeError("Thiếu SDK google-genai. Chạy: pip install google-genai pydantic") from exc
            key = self.config.api_key or os.getenv("GEMINI_API_KEY", "")
            self._gemini = genai.Client(api_key=key) if key else genai.Client()
        return self._gemini

    def _with_backoff(self, fn: Callable):
        delay = 2.0
        for attempt in range(self.config.max_retries):
            try:
                return fn()
            except Exception as exc:
                msg = str(exc).lower()
                if not any(k in msg for k in ("429", "rate", "quota", "timeout", "503")) or attempt == self.config.max_retries - 1:
                    raise
                time.sleep(delay)
                delay *= 2.0

    def generate_structured(self, prompt: str, schema_cls, system_instruction: str = "") -> AIResult:
        if self.config.provider == "gemini":
            from google.genai import types
            client = self._get_gemini()
            cfg_kwargs = dict(
                system_instruction=system_instruction or None,
                temperature=self.config.temperature,
                max_output_tokens=self.config.max_output_tokens,
                response_mime_type="application/json",
                response_schema=schema_cls,
            )
            if self.config.thinking_budget is not None and hasattr(types, "ThinkingConfig"):
                cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=self.config.thinking_budget)
            cfg = types.GenerateContentConfig(**cfg_kwargs)
            resp = self._with_backoff(lambda: client.models.generate_content(model=self.config.model, contents=prompt, config=cfg))
            um = getattr(resp, "usage_metadata", None)
            usage = AIUsage(getattr(um, "prompt_token_count", 0) or 0, getattr(um, "candidates_token_count", 0) or 0, getattr(um, "total_token_count", 0) or 0)
            parsed = getattr(resp, "parsed", None) or (schema_cls.model_validate_json(resp.text) if resp.text else None)
            return AIResult(resp.text or "", parsed, usage=usage)

        if self.config.provider in self.OPENAI_URLS:
            schema_js = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False)
            msgs = ([{"role": "system", "content": system_instruction}] if system_instruction else []) + [{"role": "user", "content": f"{prompt}\nJSON Schema:\n{schema_js}"}]
            req = urllib.request.Request(
                self.OPENAI_URLS[self.config.provider],
                data=json.dumps({"model": self.config.model, "messages": msgs, "temperature": self.config.temperature, "response_format": {"type": "json_object"}}).encode("utf-8"),
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"}, method="POST",
            )
            data = self._with_backoff(lambda: json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8")))
            txt, u = data["choices"][0]["message"]["content"], data.get("usage", {})
            return AIResult(txt, schema_cls.model_validate_json(txt), usage=AIUsage(u.get("prompt_tokens", 0), u.get("completion_tokens", 0), u.get("total_tokens", 0)))

        if self.config.provider == "claude":
            schema_js = json.dumps(schema_cls.model_json_schema(), ensure_ascii=False)
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps({"model": self.config.model, "max_tokens": min(self.config.max_output_tokens, 8192), "system": system_instruction or "Chỉ trả JSON.", "messages": [{"role": "user", "content": f"{prompt}\nSchema:\n{schema_js}"}]}).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-api-key": self.config.api_key, "anthropic-version": "2023-06-01"}, method="POST",
            )
            data = self._with_backoff(lambda: json.loads(urllib.request.urlopen(req, timeout=90).read().decode("utf-8")))
            txt = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
            u = data.get("usage", {})
            return AIResult(txt, schema_cls.model_validate_json(txt), usage=AIUsage(u.get("input_tokens", 0), u.get("output_tokens", 0), u.get("input_tokens", 0) + u.get("output_tokens", 0)))
        raise ValueError(f"Provider không hỗ trợ: {self.config.provider}")

    def stream_gemini_multimodal(self, file_part, instruction: str, on_chunk: Callable[[str], None] | None = None) -> AIResult:
        from google.genai import types
        client = self._get_gemini()
        cfg = types.GenerateContentConfig(temperature=self.config.temperature, max_output_tokens=self.config.max_output_tokens)

        def _run() -> AIResult:
            chunks, reason, usage = [], "STOP", AIUsage()
            for ck in client.models.generate_content_stream(model=self.config.model, contents=[file_part, instruction], config=cfg):
                piece = getattr(ck, "text", None) or ""
                if piece:
                    chunks.append(piece)
                    if on_chunk:
                        on_chunk(piece)
                cands = getattr(ck, "candidates", None) or []
                if cands and getattr(cands[0], "finish_reason", None):
                    reason = str(cands[0].finish_reason)
                um = getattr(ck, "usage_metadata", None)
                if um:
                    usage = AIUsage(getattr(um, "prompt_token_count", 0) or 0, getattr(um, "candidates_token_count", 0) or 0, getattr(um, "total_token_count", 0) or 0)
            return AIResult("".join(chunks), finish_reason=reason, usage=usage)
        return self._with_backoff(_run)
