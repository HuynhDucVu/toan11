"""Bài giảng video Manim từ file nguồn (.tex / .docx / .txt): AI thiết kế → sinh code → main → biên dịch → chạy video.

Các bước (dùng trong hộp thoại «Bài giảng Manim»):
  1. design_lecture  – AI đọc nội dung nguồn, trả về bản thiết kế (JSON: các cảnh, mỗi cảnh có chữ và công thức).
  2. scene_code      – sinh mã Python (lớp Scene) từ bản thiết kế, không phụ thuộc AI nên ổn định.
  3. write_project   – ghi bai_giang.py (code) và main.py (chạy manim cho mọi cảnh) vào thư mục xuất.
  4. render          – biên dịch bằng manim (cần cài manim, LaTeX và ffmpeg trên máy).
  5. play            – mở video kết quả.
  6. size_report     – dung lượng từng video và cả bài giảng (ước tính cho cả đề).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess

CODE_FILE = "bai_giang.py"
MAIN_FILE = "main.py"
TEX_PREAMBLE = r"\usepackage{amsmath,amssymb}\usepackage[utf8]{vietnam}"
QUALITIES = {"Thấp (480p, nhanh)": "-ql", "Trung bình (720p)": "-qm", "Cao (1080p, chậm)": "-qh"}

DESIGN_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "scenes": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "blocks": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"kind": {"type": "string", "enum": ["text", "math", "step"]},
                                   "content": {"type": "string"}},
                    "required": ["kind", "content"], "additionalProperties": False}},
            },
            "required": ["title", "blocks"], "additionalProperties": False}},
    },
    "required": ["title", "scenes"], "additionalProperties": False,
}


def read_source(path: str) -> str:
    """Nội dung nguồn dạng văn bản: .tex/.txt đọc trực tiếp, .docx đọc bằng bộ đọc Word của phần mềm."""
    if path.lower().endswith(".docx"):
        from .docxnative import DocxOptions, docx_to_latex
        text, _ = docx_to_latex(path, DocxOptions(images=False))
        return text
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def design_lecture(client, source: str, max_scenes: int = 8) -> dict:
    """AI thiết kế bài giảng: tối đa max_scenes cảnh, mỗi cảnh 3–6 khối (chữ, công thức LaTeX, bước giải)."""
    prompt = ("Bạn là giáo viên Toán THPT soạn bài giảng video ngắn. Từ nội dung nguồn dưới đây, thiết kế bài giảng "
              f"gồm tối đa {max_scenes} cảnh, mỗi cảnh có tiêu đề và 3–6 khối: kind=text (ý chính bằng tiếng Việt), "
              "kind=math (một công thức LaTeX thuần, không có dấu $), kind=step (một bước giải hoặc ví dụ ngắn). "
              "Giữ đúng nội dung và kí hiệu của nguồn, không bịa số liệu. Trả về JSON theo schema.\n\n"
              "NỘI DUNG NGUỒN:\n" + source[:20000])
    data = client.generate_json(prompt, DESIGN_SCHEMA)
    scenes = [s for s in data.get("scenes", []) if s.get("blocks")][:max_scenes]
    if not scenes:
        raise ValueError("AI không thiết kế được cảnh nào từ nội dung này.")
    return {"title": str(data.get("title", "Bài giảng")).strip() or "Bài giảng", "scenes": scenes}


def _cls(i: int, title: str) -> str:
    from .textnorm import unaccent
    slug = re.sub(r"[^0-9A-Za-z]+", "_", unaccent(title)).strip("_")[:30] or "Canh"
    return f"Canh{i:02d}_{slug}"


def scene_code(design: dict) -> tuple[str, list[str]]:
    """Mã Python của mọi cảnh; trả về (mã, danh sách tên lớp theo thứ tự)."""
    names, parts = [], []
    for i, sc in enumerate(design["scenes"], 1):
        name = _cls(i, sc.get("title", ""))
        names.append(name)
        body = [f"        title = Text({sc.get('title', '')!r}, font_size=36).to_edge(UP)",
                "        self.play(Write(title))",
                "        mobs = []"]
        for b in sc.get("blocks", []):
            k, c = b.get("kind", "text"), b.get("content", "")
            if k == "math":
                body.append(f"        mobs.append(MathTex({c!r}, tex_template=TEX, font_size=40))")
            elif k == "step":
                body.append(f"        mobs.append(Text({('• ' + c)!r}, font_size=30))")
            else:
                body.append(f"        mobs.append(Text({c!r}, font_size=30))")
        body += ["        group = VGroup(*mobs).arrange(DOWN, buff=0.45).next_to(title, DOWN, buff=0.6)",
                 "        if group.height > 5.8:",
                 "            group.scale_to_fit_height(5.8)",
                 "        for m in mobs:",
                 "            self.play(FadeIn(m, shift=UP * 0.2), run_time=0.8)",
                 "            self.wait(0.6)",
                 "        self.wait(1.2)",
                 "        self.play(FadeOut(group), FadeOut(title))"]
        parts.append(f"class {name}(Scene):\n    def construct(self):\n" + "\n".join(body) + "\n")
    head = ("# Tạo tự động bởi Ngân hàng đề thi – bài giảng Manim.\n"
            "from manim import *\n\n"
            f"TEX = TexTemplate(preamble={TEX_PREAMBLE!r})\n\n\n")
    return head + "\n\n".join(parts), names


def write_code(design: dict, out_dir: str) -> dict:
    """Bước 2: ghi bai_giang.py. Trả về {'code': đường dẫn, 'scenes': [tên lớp]}."""
    os.makedirs(out_dir, exist_ok=True)
    code, names = scene_code(design)
    code_p = os.path.join(out_dir, CODE_FILE)
    with open(code_p, "w", encoding="utf-8") as f:
        f.write(code)
    return {"code": code_p, "scenes": names}


def write_project(design: dict, out_dir: str, quality: str = "-qm") -> dict:
    """Bước 2 + 3: ghi bai_giang.py và main.py vào out_dir. Trả về {'code', 'main', 'scenes'}."""
    info = write_code(design, out_dir)
    return dict(write_main(out_dir, info["scenes"], quality), code=info["code"])


def write_main(out_dir: str, names: list[str], quality: str = "-qm") -> dict:
    """Bước 3: ghi main.py (chạy manim cho mọi cảnh với chất lượng đã chọn)."""
    main_p = os.path.join(out_dir, MAIN_FILE)
    main = ("# Chạy: python main.py   (cần: pip install manim, LaTeX và ffmpeg trên máy)\n"
            "import subprocess\nimport sys\n\n"
            f"QUALITY = {quality!r}\n"
            f"SCENES = {list(names)!r}\n\n\n"
            "def render_all():\n"
            "    cmd = [sys.executable, '-m', 'manim', QUALITY, " + repr(CODE_FILE) + ", *SCENES]\n"
            "    subprocess.run(cmd, check=True)\n\n\n"
            "if __name__ == '__main__':\n    render_all()\n")
    with open(main_p, "w", encoding="utf-8") as f:
        f.write(main)
    return {"main": main_p, "scenes": list(names)}


def manim_command() -> list[str] | None:
    """Lệnh chạy manim trên máy: lệnh «manim» trong PATH, hoặc python -m manim nếu python đó đã cài manim."""
    if shutil.which("manim"):
        return ["manim"]
    py = shutil.which("python") or shutil.which("python3")
    if py:
        try:
            ok = subprocess.run([py, "-c", "import manim"], capture_output=True, timeout=60).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            ok = False
        if ok:
            return [py, "-m", "manim"]
    return None


def missing_tools() -> list[str]:
    """Các thành phần còn thiếu để biên dịch video, kèm cách cài (rỗng = đủ)."""
    out = []
    if manim_command() is None:
        out.append("manim: mở cửa sổ lệnh và chạy «pip install manim» (Python đang dùng phải là Python đã cài manim)")
    if shutil.which("latex") is None:
        out.append("LaTeX: cài MiKTeX (https://miktex.org/download) hoặc TeX Live; cần để vẽ công thức")
    if shutil.which("dvisvgm") is None:
        out.append("dvisvgm: đi kèm MiKTeX/TeX Live; kiểm tra thư mục cài có dvisvgm.exe")
    if shutil.which("ffmpeg") is None:
        out.append("ffmpeg: tải từ https://ffmpeg.org/download.html rồi thêm thư mục bin vào PATH")
    return out


def render(out_dir: str, scenes: list[str], quality: str = "-qm", timeout: int = 3600) -> tuple[bool, list[str], str]:
    """Biên dịch từng cảnh. Trả về (thành công, danh sách file .mp4, thông báo)."""
    cmd = manim_command()
    miss = missing_tools()
    if miss:
        return False, [], "Còn thiếu:\n• " + "\n• ".join(miss)
    run = subprocess.run(cmd + [quality, CODE_FILE, *scenes], cwd=out_dir, capture_output=True, text=True, timeout=timeout)
    if run.returncode != 0:
        tail = (run.stderr or run.stdout or "").strip().splitlines()[-6:]
        return False, [], "Biên dịch lỗi:\n" + "\n".join(tail)
    videos = find_videos(out_dir)
    return bool(videos), videos, f"Đã biên dịch {len(videos)} video."


def find_videos(out_dir: str) -> list[str]:
    """Các video .mp4 do manim tạo trong out_dir/media (theo thứ tự tên)."""
    found = []
    for root, _dirs, files in os.walk(os.path.join(out_dir, "media", "videos")):
        for f in files:
            if f.endswith(".mp4") and "partial_movie_files" not in root:
                found.append(os.path.join(root, f))
    return sorted(found)


def size_report(videos: list[str]) -> dict:
    """Dung lượng từng video và tổng; cộng thêm ước tính cho cả đề (trung bình × số cảnh)."""
    sizes = {os.path.basename(v): os.path.getsize(v) for v in videos if os.path.exists(v)}
    total = sum(sizes.values())
    avg = total / len(sizes) if sizes else 0
    return {"files": sizes, "total": total, "avg": avg,
            "human": _human(total)}


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
