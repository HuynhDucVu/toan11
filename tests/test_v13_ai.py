"""Giai đoạn 3 – AI: nhà cung cấp, câu tương tự, bù ma trận, PDF → LaTeX, chấm tự luận (giả lập, không gọi mạng)."""
import json
from types import SimpleNamespace

import pytest

from nganhangde.aiid import AIError
from nganhangde.parser import parse_tex

TN = r"""\begin{ex}%[0D2N1-1]
Tập nghiệm của $x-1>0$ là
\choice
{$(-\infty;1)$}
{\True $(1;+\infty)$}
{$[1;+\infty)$}
{$\mathbb{R}$}
\loigiai{$x>1$. Chọn đáp án B.}
\end{ex}"""
BAD = r"""\begin{ex}
Câu lỗi
\choice
{a}{b}{c}{d}
\loigiai{}
\end{ex}"""


class Fake:
    provider = "gemini"
    model = "fake"

    def __init__(self, items=None, pdf_items=None):
        self.items, self.pdf_items, self.calls = items or [TN], pdf_items or [TN], []

    def generate_json(self, prompt, schema=None):
        self.calls.append(("json", prompt, schema))
        if schema and "diem" in schema["properties"]:
            return {"diem": 0.83, "nhan_xet": "ok", "chi_tiet": [{"y": "1", "diem": 0.83, "ghi_chu": ""}]}
        if schema and "nguyen_nhan" in schema["properties"]:
            return {"nguyen_nhan": "thiếu }", "cach_sua": "thêm }", "dong": 3, "sua_thanh": "x}"}
        return {"cau_hoi": list(self.items)}

    def generate_from_pdf(self, data, prompt, schema=None):
        self.calls.append(("pdf", len(data), schema))
        return {"cau_hoi": list(self.pdf_items)}


def test_similar_reviews_and_tags():
    from nganhangde import aitasks
    q = parse_tex(TN)[0]
    props = aitasks.similar(Fake([TN, BAD]), q, 2)
    assert len(props) == 2 and props[0].ok and not props[1].ok
    assert props[1].question.id_code == "0D2N1-1"       # câu thiếu ID nhận ID câu mẫu
    assert "AI" in props[0].question.tags


def test_fill_gaps(tmp_path):
    from nganhangde import aitasks
    from nganhangde.db import Bank
    from nganhangde.generator import Rule
    b = Bank(str(tmp_path / "k.db"))
    b.add(parse_tex(TN)[0])
    b.set_idmap({"0D3": "Chương 3", "0D31": "Bài 1", "0D31-2": "Dạng hàm số bậc hai"})
    rules = [Rule("TN", 3, "0D2*"), Rule("TN", 1, "0D3N1-2"), Rule("TN", 1, "0D2*")]
    assert aitasks.gaps(b, rules) == [(0, 2), (1, 1)]
    f = Fake([TN, TN, TN])
    props = aitasks.fill_gaps(f, b, rules)
    assert len(props) == 3
    assert any("Dạng hàm số bậc hai" in c[1] for c in f.calls)
    with pytest.raises(AIError):
        aitasks.fill_gaps(f, b, [Rule("KQ", 1, "9X9*")])
    b.close()


def test_pdf_chunks_and_convert(tmp_path):
    pypdf = pytest.importorskip("pypdf")
    from nganhangde import aitasks
    w = pypdf.PdfWriter()
    for _ in range(23):
        w.add_blank_page(width=200, height=200)
    p = tmp_path / "de.pdf"
    with open(p, "wb") as fh:
        w.write(fh)
    ch = aitasks.pdf_chunks(str(p), 10)
    assert [c[0] for c in ch] == ["trang 1–10", "trang 11–20", "trang 21–23"]
    f = Fake()
    props = aitasks.pdf_to_latex(f, str(p), 10)
    assert len(props) == 3 and sum(c[0] == "pdf" for c in f.calls) == 3
    assert "PDF" in props[0].question.tags and "AI" not in props[0].question.tags


def test_grade_and_diagnose(tmp_path):
    from nganhangde import aitasks
    r = aitasks.grade_essay(Fake(), "Giải pt", "x=1", 1.0, answer_text="x=1")
    assert r["diem"] == 0.75
    t = tmp_path / "a.tex"
    t.write_text("a\nb\nc{\nd\n", encoding="utf-8")
    d = aitasks.diagnose_log(Fake(), ["Dòng 3: Missing }"], str(t))
    assert d["dong"] == 3


def test_claude_client_request_shape():
    pytest.importorskip("anthropic")
    from nganhangde.ai_claude import ClaudeClient
    sent = {}

    def create(**kw):
        sent.update(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text='{"cau_hoi": []}')])
    fake = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    c = ClaudeClient("", client=fake)
    assert c.generate_json("x", {"type": "object"}) == {"cau_hoi": []}
    assert sent["model"] == "claude-opus-5-5" and sent["fallbacks"] == "default"
    assert sent["output_config"]["format"]["type"] == "json_schema" and sent["output_config"]["effort"] == "medium"
    c.generate_from_pdf(b"%PDF", "y")
    assert sent["messages"][0]["content"][0]["type"] == "document"

    def refuse(**kw):
        return SimpleNamespace(stop_reason="refusal", content=[])
    c.client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=refuse)))
    with pytest.raises(AIError):
        c.generate_json("x")


def test_openai_compat_and_factory(monkeypatch):
    from nganhangde import ai
    from nganhangde.ai_openai_compat import OpenAICompatClient
    seen = []

    def tr(path, data=None):
        seen.append((path, data))
        if path == "/models":
            return {"data": [{"id": "b"}, {"id": "a"}]}
        return {"choices": [{"message": {"content": json.dumps({"ok": 1})}}]}
    c = OpenAICompatClient("deepseek", "k", transport=tr)
    assert c.list_models() == ["a", "b"] and c.generate_json("p") == {"ok": 1}
    assert seen[-1][1]["model"] == "deepseek-chat" and seen[-1][1]["response_format"]["type"] == "json_object"
    with pytest.raises(AIError):
        c.generate_from_pdf(b"", "p")
    with pytest.raises(AIError):
        ai.make_client("openai", "")
    st = {"ai/provider": "grok", "ai/grok_key": "k", "ai/grok_model": "m"}
    cl = ai.client_from_settings(SimpleNamespace(value=lambda k, d=None: st.get(k, d)))
    assert cl.provider == "grok" and cl.model == "m" and cl.base == "https://api.x.ai/v1"
