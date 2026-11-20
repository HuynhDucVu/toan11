"""Chọn nhà cung cấp AI: Gemini (mặc định, có hạn mức miễn phí), Claude, OpenAI, DeepSeek, Grok.

Mọi client có cùng giao diện: list_models(), generate_json(prompt, schema=None),
generate_from_pdf(pdf_bytes, prompt, schema=None). Cài đặt lưu theo từng nhà cung cấp:
ai/provider, ai/<provider>_key, ai/<provider>_model (riêng Gemini giữ khoá cũ ai/key, ai/model).
"""
from __future__ import annotations

from .aiid import AIError

PROVIDERS = [("gemini", "Google Gemini"), ("claude", "Anthropic Claude"), ("openai", "OpenAI"),
             ("deepseek", "DeepSeek"), ("grok", "Grok (xAI)")]
KEY_HELP = {"gemini": "aistudio.google.com/apikey (miễn phí)", "claude": "platform.claude.com → API keys",
            "openai": "platform.openai.com/api-keys", "deepseek": "platform.deepseek.com/api_keys",
            "grok": "console.x.ai"}
PDF_OK = {"gemini", "claude"}


def default_model(provider: str) -> str:
    if provider == "gemini":
        from .aiid import DEFAULT_MODEL
        return DEFAULT_MODEL
    if provider == "claude":
        from .ai_claude import DEFAULT_MODEL
        return DEFAULT_MODEL
    from .ai_openai_compat import ENDPOINTS
    return ENDPOINTS[provider][1]


def make_client(provider: str, api_key: str, model: str = "", **kw):
    provider = provider or "gemini"
    if provider == "gemini":
        from .aiid import GeminiClient
        return GeminiClient(api_key, model or default_model("gemini"), **kw)
    if provider == "claude":
        from .ai_claude import ClaudeClient
        return ClaudeClient(api_key, model or default_model("claude"), **kw)
    from .ai_openai_compat import ENDPOINTS, OpenAICompatClient
    if provider in ENDPOINTS:
        return OpenAICompatClient(provider, api_key, model, **kw)
    raise AIError(f"Không hỗ trợ nhà cung cấp «{provider}»")


def _k(provider: str, what: str) -> str:
    return f"ai/{what}" if provider == "gemini" else f"ai/{provider}_{what}"


def client_from_settings(st):
    """Tạo client theo cài đặt đã lưu (QSettings hoặc dict có .value)."""
    p = st.value("ai/provider", "gemini") or "gemini"
    kw = {"effort": st.value("ai/claude_effort", "medium")} if p == "claude" else {}
    return make_client(p, st.value(_k(p, "key"), ""), st.value(_k(p, "model"), ""), **kw)


def provider_name(p: str) -> str:
    return dict(PROVIDERS).get(p, p)
