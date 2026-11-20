"""Chế độ trình chiếu: mỗi câu một trang HTML toàn màn hình, có bảng vẽ (bút) để giảng trên máy chiếu.

Phím: → / Space câu sau · ← câu trước · Đ hoặc A hiện đáp án · L hiện lời giải · B bật/tắt bút vẽ · X xoá nét vẽ
· T bấm giờ · F toàn màn hình · số + Enter nhảy tới câu. MathJax đi kèm (thư mục mathjax/) – không cần Internet.
"""
from __future__ import annotations

import html
import json

from .htmlconv import MATHJAX_MACROS, latex_to_html

TYPE = {"TN": "Trắc nghiệm", "DS": "Đúng/Sai", "KQ": "Trả lời ngắn", "TL": "Tự luận"}

CSS = """
:root{--bg:#fff;--fg:#111;--acc:#1f4e79}
body.dark{--bg:#111;--fg:#eee;--acc:#8ec5ff}
html,body{margin:0;height:100%;background:var(--bg);color:var(--fg);font-family:'Times New Roman',serif}
.slide{display:none;position:absolute;inset:0;padding:4vh 6vw;box-sizing:border-box;font-size:3.1vh;overflow:auto}
.slide.on{display:block}
.slide h2{margin:0 0 2vh;color:var(--acc);font-family:system-ui,Arial;font-size:2.6vh}
.opts{display:grid;grid-template-columns:1fr 1fr;gap:1.4vh 4vw;margin-top:3vh}
.opt.right.show{background:#c8f7c5;color:#111;border-radius:8px}
.ans,.sol{display:none;margin-top:3vh;padding:2vh 2vw;border-left:6px solid var(--acc);background:rgba(31,78,121,.08)}
.ans.show,.sol.show{display:block}
canvas{position:fixed;inset:0;z-index:5;pointer-events:none}
canvas.on{pointer-events:auto;cursor:crosshair}
#bar{position:fixed;right:1vw;bottom:1vh;z-index:6;font:14px system-ui;opacity:.55}
#bar button{font:14px system-ui;margin-left:4px}
#timer{position:fixed;left:1vw;bottom:1vh;font:bold 22px system-ui;color:var(--acc);z-index:6}
"""

JS = r"""
const S=[...document.querySelectorAll('.slide')]; let cur=0, jump='';
const cv=document.getElementById('cv'), cx=cv.getContext('2d'); let drawing=false, pen=false;
function fit(){ const d=cx.getImageData(0,0,cv.width||1,cv.height||1); cv.width=innerWidth; cv.height=innerHeight; cx.putImageData(d,0,0); }
addEventListener('resize',fit); fit();
function show(i){ cur=Math.max(0,Math.min(S.length-1,i)); S.forEach((s,k)=>s.classList.toggle('on',k===cur));
  document.getElementById('pos').textContent=(cur+1)+'/'+S.length; cx.clearRect(0,0,cv.width,cv.height); }
function tog(sel){ S[cur].querySelectorAll(sel).forEach(e=>e.classList.toggle('show')); }
let t0=null, tick=null; function timer(){ const el=document.getElementById('timer');
  if(tick){ clearInterval(tick); tick=null; return; } t0=Date.now();
  tick=setInterval(()=>{ const s=Math.floor((Date.now()-t0)/1000); el.textContent=String(Math.floor(s/60)).padStart(2,'0')+':'+String(s%60).padStart(2,'0'); },500); }
function setPen(v){ pen=v; cv.classList.toggle('on',pen); }
cv.addEventListener('pointerdown',e=>{ drawing=true; cx.beginPath(); cx.moveTo(e.clientX,e.clientY); });
cv.addEventListener('pointermove',e=>{ if(!drawing) return; cx.lineWidth=3; cx.lineCap='round';
  cx.strokeStyle=document.body.classList.contains('dark')?'#ffd54f':'#d32f2f'; cx.lineTo(e.clientX,e.clientY); cx.stroke(); });
addEventListener('pointerup',()=>drawing=false);
addEventListener('keydown',e=>{ const k=e.key.toLowerCase();
  if(/^[0-9]$/.test(k)){ jump+=k; return; }
  if(k==='enter' && jump){ show(+jump-1); jump=''; return; }
  if(k==='arrowright'||k===' '||k==='pagedown'){ show(cur+1); e.preventDefault(); }
  else if(k==='arrowleft'||k==='pageup') show(cur-1);
  else if(k==='a'||k==='đ'){ tog('.ans'); tog('.opt.right'); }
  else if(k==='l') tog('.sol');
  else if(k==='b') setPen(!pen);
  else if(k==='x') cx.clearRect(0,0,cv.width,cv.height);
  else if(k==='t') timer();
  else if(k==='n') document.body.classList.toggle('dark');
  else if(k==='f'){ document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen(); } });
show(0);
"""


def slides_html(questions, title: str = "Trình chiếu") -> str:
    from .exporter import plain_answer
    slides = []
    for i, q in enumerate(questions, 1):
        body = [f"<h2>Câu {i} · {TYPE.get(q.qtype, q.qtype)}{' · ' + html.escape(q.id_code) if q.id_code else ''}</h2>",
                f"<div>{latex_to_html(q.stem)}</div>"]
        if q.qtype in ("TN", "DS") and q.choices:
            lab = "ABCD" if q.qtype == "TN" else "abcd"
            body.append("<div class='opts'>" + "".join(
                f"<div class='opt{' right' if ok and q.qtype == 'TN' else ''}'><b>{lab[k] if k < 4 else k + 1}"
                f"{'.' if q.qtype == 'TN' else ')'}</b> {latex_to_html(c)}</div>"
                for k, (c, ok) in enumerate(zip(q.choices, q.correct))) + "</div>")
        ans = q.answer_text if q.qtype in ("TN", "DS") else plain_answer(q.answer_text) if q.qtype == "KQ" else ""
        if ans:
            body.append(f"<div class='ans'><b>Đáp án:</b> {html.escape(ans)}</div>")
        if q.solution.strip():
            body.append(f"<div class='sol'><b>Lời giải.</b> {latex_to_html(q.solution)}</div>")
        slides.append(f"<section class='slide'>{''.join(body)}</section>")
    mj = json.dumps({"tex": {"inlineMath": [["$", "$"], ["\\(", "\\)"]], "macros": MATHJAX_MACROS}},
                    ensure_ascii=False)
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style>
<script>window.MathJax={mj};</script>
<script defer src="mathjax/tex-svg.js"></script>
</head><body>{''.join(slides)}<canvas id="cv"></canvas><div id="timer"></div>
<div id="bar"><span id="pos"></span> · ←/→ chuyển câu · A đáp án · L lời giải · B bút · X xoá · T giờ · N nền tối · F toàn màn hình
<button onclick="show(cur-1)">◀</button><button onclick="show(cur+1)">▶</button>
<button onclick="tog('.ans');tog('.opt.right')">Đáp án</button><button onclick="tog('.sol')">Lời giải</button>
<button onclick="setPen(!pen)">Bút</button></div>
<script>{JS}</script></body></html>"""


def export_slides(questions, path: str, title: str = "Trình chiếu") -> str:
    """Ghi file HTML + thư mục mathjax/ bên cạnh (chạy được không cần Internet)."""
    import os
    import shutil
    from .online import mathjax_local
    with open(path, "w", encoding="utf-8") as f:
        f.write(slides_html(questions, title))
    d = os.path.join(os.path.dirname(os.path.abspath(path)), "mathjax")
    os.makedirs(d, exist_ok=True)
    if not os.path.exists(os.path.join(d, "tex-svg.js")):
        shutil.copy(mathjax_local(), os.path.join(d, "tex-svg.js"))
    return path
