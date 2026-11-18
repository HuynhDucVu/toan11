"""Gán ID tự động bằng Google Gemini.

Quy trình:
  1. Lấy danh sách dạng trong Map ID (giới hạn theo phạm vi, vd lớp 10) → bảng «mã | chương › bài › dạng».
  2. Gửi lần lượt từng nhóm câu (mặc định 10 câu/lần) kèm bảng trên cho Gemini, yêu cầu trả về JSON:
     {"ket_qua": [{"cau": 1, "ma": "0D71-2", "muc_do": "H", "tin_cay": 0.8, "ly_do": "..."}]}
  3. Kiểm tra lại: mã phải có trong Map ID, mức độ phải là N/H/V/C ⇒ ghép thành ID 0D7H1-2.
     Mã không có trong Map ID bị loại (Gemini «bịa» mã).

Cần khoá API Gemini (https://aistudio.google.com/apikey). Nội dung câu hỏi được gửi tới máy chủ Google.
Không cần thư viện ngoài: gọi REST bằng urllib.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .idmap import split_key

API = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-2.5-flash"
LEVELS = {"N": "Nhận biết – nhắc lại/nhận ra kiến thức, công thức, áp dụng trực tiếp 1 bước",
          "H": "Thông hiểu – hiểu và vận dụng đơn giản, vài bước biến đổi quen thuộc",
          "V": "Vận dụng – phối hợp nhiều kiến thức, bài toán nhiều bước hoặc thực tế",
          "C": "Vận dụng cao – bài khó, cần sáng tạo, kĩ thuật đặc biệt"}


class AIError(RuntimeError):
    pass


@dataclass
class AIResult:
    index: int                # vị trí câu trong danh sách gửi
    id_code: str | None       # ID đầy đủ đã kiểm tra (None nếu không hợp lệ)
    score: float              # độ tin cậy Gemini tự đánh giá (0..1)
    reason: str
    raw_code: str = ""        # mã Gemini trả về (để báo khi không hợp lệ)


def _http(url: str, data: dict | None = None, api_key: str = "", timeout: int = 90) -> dict:
    body = json.dumps(data).encode("utf-8") if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET",
                                 headers={"Content-Type": "application/json", "x-goog-api-key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:  # noqa: BLE001
            msg = ""
        hint = {400: "yêu cầu không hợp lệ (kiểm tra tên mô hình)", 401: "khoá API sai",
                403: "khoá API sai hoặc chưa bật Gemini API", 404: "không có mô hình này",
                429: "vượt hạn mức miễn phí – đợi một lát hoặc giảm số câu mỗi lần",
                500: "lỗi máy chủ Google", 503: "máy chủ Google đang quá tải – thử lại sau"}.get(e.code, "")
        raise AIError(f"Gemini báo lỗi {e.code}: {hint} {msg}".strip()) from None
    except urllib.error.URLError as e:
        raise AIError(f"Không kết nối được Gemini (cần Internet): {e.reason}") from None


class GeminiClient:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, transport=None):
        if not api_key:
            raise AIError("Chưa nhập khoá API Gemini (lấy tại https://aistudio.google.com/apikey)")
        self.key, self.model = api_key.strip(), (model or DEFAULT_MODEL).strip()
        self.http = transport or _http          # cho phép thay bằng hàm giả lập khi kiểm thử

    def list_models(self) -> list[str]:
        data = self.http(f"{API}/models?pageSize=200", None, self.key)
        return sorted(m["name"].split("/", 1)[1] for m in data.get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))

    def generate_json(self, prompt: str, retries: int = 2) -> dict:
        body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}}
        last = None
        for attempt in range(retries + 1):
            try:
                data = self.http(f"{API}/models/{self.model}:generateContent", body, self.key)
                text = "".join(p.get("text", "") for c in data.get("candidates", [])[:1]
                               for p in c.get("content", {}).get("parts", []))
                if not text:
                    reason = (data.get("promptFeedback") or {}).get("blockReason") or \
                             (data.get("candidates") or [{}])[0].get("finishReason", "")
                    raise AIError(f"Gemini không trả lời ({reason or 'phản hồi rỗng'})")
                return _loads_json(text)
            except AIError as e:
                last = e
                if "429" in str(e) or "503" in str(e) or "500" in str(e):
                    time.sleep(2 * (attempt + 1))
                    continue
                raise
        raise last


def _loads_json(text: str) -> dict:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise AIError("Gemini trả về dữ liệu không đúng dạng JSON") from None


# ---------------------------------------------------------------- dựng câu hỏi gửi Gemini
def map_catalog(mapping: dict[str, str], scope: str = "") -> list[tuple[str, str]]:
    """[(mã không mức độ, 'chương › bài › dạng')] cho mọi dạng (và bài không có dạng) trong phạm vi."""
    out = []
    keys = [k for k in mapping if not k.startswith("#") and k.upper().startswith(scope.upper())]
    have_dang = {k.split("-")[0] for k in keys if "-" in k}
    for k in sorted(keys, key=split_key):
        parts = split_key(k)
        if "-" in k or (len(parts) == 4 and k not in have_dang):
            ch = mapping.get("".join(parts[:3]), "")
            bai = mapping.get("".join(parts[:4]), "")
            label = " › ".join(x for x in (mapping.get(parts[0], ""), mapping.get("".join(parts[:2]), ""), ch, bai,
                                           mapping[k] if "-" in k else "") if x)
            out.append((k, label))
    return out


def _q_text(q, limit: int = 1500) -> str:
    parts = [q.stem.strip()]
    if q.qtype == "TN":
        parts += [f"{'ABCD'[i] if i < 4 else i + 1}. {c}" for i, c in enumerate(q.choices)]
    elif q.qtype == "DS":
        parts += [f"{'abcd'[i] if i < 4 else i + 1}) {c}" for i, c in enumerate(q.choices)]
    elif q.qtype == "KQ":
        parts.append(f"(Đáp án: {q.short_answer})")
    if q.solution.strip():
        parts.append("Lời giải (tóm tắt): " + " ".join(q.solution.split())[:400])
    return "\n".join(parts)[:limit]


def build_prompt(questions, catalog, judge_level: bool = True) -> str:
    cat = "\n".join(f"{k} | {v}" for k, v in catalog)
    lv = "\n".join(f"{k}: {v}" for k, v in LEVELS.items())
    qs = "\n\n".join(f"### Câu {i}\n{_q_text(q)}" for i, q in enumerate(questions, 1))
    return f"""Bạn là giáo viên Toán THPT Việt Nam, đang phân loại câu hỏi vào ngân hàng đề theo chương trình GDPT 2018.
Với MỖI câu hỏi bên dưới, chọn ĐÚNG MỘT mã trong BẢNG MÃ (cột 1) mô tả đúng nhất nội dung kiến thức của câu,
{"và đánh giá mức độ nhận thức theo thang dưới đây" if judge_level else "(không cần đánh giá mức độ)"}.
Chỉ dùng mã có trong bảng; không tự tạo mã mới. Nếu không có mã nào phù hợp, để "ma" là "".

THANG MỨC ĐỘ:
{lv}

BẢNG MÃ (mã | lớp › môn › chương › bài › dạng):
{cat}

CÁC CÂU HỎI (LaTeX):
{qs}

Trả về JSON duy nhất, đúng cấu trúc:
{{"ket_qua": [{{"cau": <số thứ tự câu>, "ma": "<mã trong bảng>", "muc_do": "N|H|V|C", "tin_cay": <0..1>, "ly_do": "<ngắn gọn>"}}]}}"""


def classify(client: GeminiClient, questions, mapping: dict[str, str], *, scope: str = "",
             default_level: str = "N", judge_level: bool = True, batch: int = 10, progress=None,
             should_stop=None) -> list[AIResult]:
    """Phân loại danh sách câu; trả về AIResult theo đúng thứ tự câu đưa vào."""
    catalog = map_catalog(mapping, scope)
    if not catalog:
        raise AIError("Map ID chưa có dạng nào trong phạm vi đã chọn – nạp Map ID trước (Công cụ → Giải nghĩa ID)")
    valid = {k for k, _ in catalog}
    out: list[AIResult] = []
    for start in range(0, len(questions), batch):
        if should_stop and should_stop():
            break
        chunk = questions[start:start + batch]
        if progress:
            progress(start, len(questions))
        data = client.generate_json(build_prompt(chunk, catalog, judge_level))
        rows = {int(r.get("cau", 0)): r for r in data.get("ket_qua", []) if str(r.get("cau", "")).isdigit()}
        for i, q in enumerate(chunk, 1):
            r = rows.get(i, {})
            code = str(r.get("ma", "")).strip().upper().replace(" ", "")
            lv = str(r.get("muc_do", "")).strip().upper()[:1]
            if not judge_level or lv not in LEVELS:
                old = q.id_code[3] if len(q.id_code or "") >= 4 and q.id_code[3] in LEVELS else ""
                lv = old or default_level
            try:
                score = max(0.0, min(1.0, float(r.get("tin_cay", 0.5))))
            except (TypeError, ValueError):
                score = 0.5
            reason = str(r.get("ly_do", ""))[:300]
            full = None
            if code in valid:
                parts = split_key(code)
                full = "".join(parts[:3]) + lv + parts[3] + (f"-{parts[4]}" if len(parts) > 4 else "")
            out.append(AIResult(start + i - 1, full, score if full else 0.0,
                                reason if full else f"Mã «{code or 'trống'}» không có trong Map ID – bỏ qua",
                                raw_code=code))
    if progress:
        progress(len(questions), len(questions))
    return out
