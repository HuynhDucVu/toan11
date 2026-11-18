"""Xuất đề làm bài online: 1 file HTML tự chứa (mở bằng trình duyệt – máy tính, iPhone, Android)
và file Moodle XML để nhập vào ngân hàng câu hỏi Moodle.

HTML: học sinh nhập tên, làm bài (đồng hồ đếm ngược), bấm «Nộp bài» ⇒ chấm ngay theo thang điểm
thi tốt nghiệp (TN 0,25 · Đúng/Sai 0,1/0,25/0,5/1 · trả lời ngắn 0,5), hiện đáp án và (tuỳ chọn) lời giải.
Công thức vẽ bằng MathJax (cần mạng khi mở). Đáp án được mã hoá nhẹ trong file – chỉ chống
xem trộm thông thường, không phải bảo mật thật: không dùng cho kì thi quan trọng.
"""
from __future__ import annotations

import base64
import html
import json

from .exporter import SCORING, plain_answer
from .generator import SECTION_ORDER, ExamVersion
from .htmlconv import MATHJAX_MACROS, dollar_to_paren, latex_to_html

PART_TITLE = {"TN": "PHẦN I. Trắc nghiệm nhiều phương án lựa chọn",
              "DS": "PHẦN II. Trắc nghiệm đúng sai", "KQ": "PHẦN III. Trả lời ngắn", "TL": "PHẦN IV. Tự luận"}

CSS = """
:root{--c:#1f4e79;--bg:#f5f7fa;--card:#fff;--ok:#0b7a0b;--bad:#c00000;--mut:#666}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#222}
header{background:var(--c);color:#fff;padding:12px 16px;position:sticky;top:0;z-index:9;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
header h1{font-size:17px;margin:0;flex:1 1 220px}#timer{font-weight:700;font-variant-numeric:tabular-nums;background:#ffffff22;padding:4px 10px;border-radius:6px}
main{max-width:860px;margin:0 auto;padding:12px 16px 80px}.card{background:var(--card);border-radius:10px;padding:14px 16px;margin:12px 0;box-shadow:0 1px 3px #0002}
h2{font-size:17px;color:var(--c);margin:22px 0 4px}.q b.num{color:var(--c)}.opt{display:flex;gap:8px;align-items:flex-start;padding:8px;border:1px solid #d6dde6;border-radius:8px;margin:6px 0;cursor:pointer}
.opt input{margin-top:5px}.ds{display:grid;grid-template-columns:1fr auto;gap:6px 10px;align-items:center;margin-top:6px}.ds .tf label{margin-left:8px;white-space:nowrap}
input[type=text]{font-size:16px;padding:8px;border:1px solid #b9c6d4;border-radius:6px;width:min(220px,100%)}
button{font-size:16px;background:var(--c);color:#fff;border:0;border-radius:8px;padding:10px 18px;cursor:pointer}
.right{border-color:var(--ok)!important;background:#e9f6e9}.wrong{border-color:var(--bad)!important;background:#fdeaea}
.res{font-weight:600;margin-top:6px}.res.ok{color:var(--ok)}.res.bad{color:var(--bad)}.sol{display:none;border-left:3px solid var(--c);padding-left:10px;margin-top:8px;color:#333}
.done .sol{display:block}.fig{display:inline-block;padding:6px 10px;border:1px dashed #999;color:var(--mut);border-radius:6px;font-size:14px}
html,body{overflow-x:hidden}.card{overflow-wrap:anywhere;min-width:0}
mjx-container[display="true"]{display:block;overflow-x:auto;overflow-y:hidden;max-width:100%;padding:2px 0}
mjx-container{max-width:100%}.q>div,.opt span,.ds>div,.sol{min-width:0;overflow-x:auto}
#score{font-size:20px;font-weight:700;color:var(--c)}footer{position:fixed;z-index:10;bottom:0;left:0;right:0;background:#fff;box-shadow:0 -1px 4px #0002;padding:10px 16px;text-align:center}
@media (prefers-color-scheme:dark){:root{--bg:#15191e;--card:#1f252c;--mut:#aaa}body{color:#e6e6e6}.opt{border-color:#3a4552}.right{background:#173a1d}.wrong{background:#43191b}footer{background:#1f252c}.sol{color:#ddd}}
"""

JS = r"""
const K = JSON.parse(atob(DATA));            // đáp án
const S = {TN:0.25, KQ:0.5, DS:{0:0,1:0.1,2:0.25,3:0.5,4:1}};
let left = MINUTES*60, timer = setInterval(()=>{ left--; const m=Math.max(0,Math.floor(left/60)), s=Math.max(0,left%60);
  document.getElementById('timer').textContent = String(m).padStart(2,'0')+':'+String(s).padStart(2,'0');
  if(left<=0){ clearInterval(timer); submit(true); } },1000);
function norm(x){ return (x||'').toString().trim().replace(/\s+/g,'').replace(/\./g,',').replace(/^\+/,''); }
function submit(auto){
  if(!auto && !confirm('Nộp bài?')) return;
  clearInterval(timer); let total=0, max=0;
  document.querySelectorAll('.q').forEach(q=>{
    const id=q.dataset.id, t=q.dataset.type, key=K[id]; let pts=0, full=0, msg='';
    if(t==='TN'){ full=S.TN; const c=q.querySelector('input:checked');
      q.querySelectorAll('.opt').forEach((o,i)=>{ if(i===key) o.classList.add('right'); });
      if(c && +c.value===key){ pts=full; } else if(c){ c.closest('.opt').classList.add('wrong'); }
      msg = 'Đáp án: '+'ABCD'[key];
    } else if(t==='DS'){ full=S.DS[4]; let n=0;
      key.forEach((v,i)=>{ const c=q.querySelector('input[name="'+id+'_'+i+'"]:checked'); const row=q.querySelectorAll('.ds .tf')[i];
        if(c && (c.value==='1')===v){ n++; row.classList.add('right'); } else { row.classList.add('wrong'); } });
      pts=S.DS[n]; msg='Đúng '+n+'/4 ý · Đáp án: '+key.map(v=>v?'Đ':'S').join(''); 
    } else if(t==='KQ'){ full=S.KQ; const v=q.querySelector('input[type=text]').value;
      if(norm(v)!=='' && norm(v)===norm(key)) pts=full; msg='Đáp án: '+key;
      q.querySelector('input[type=text]').classList.add(pts?'right':'wrong');
    } else { msg='Câu tự luận – giáo viên chấm.'; }
    total+=pts; max+=full; q.querySelectorAll('input').forEach(i=>i.disabled=true);
    const r=document.createElement('div'); r.className='res '+(full&&pts===full?'ok':'bad');
    r.textContent=(full? (pts.toFixed(2).replace('.',',')+' / '+full.toString().replace('.',',')+' điểm · ') : '')+msg; q.appendChild(r);
    if(SHOW_SOL) q.classList.add('done');
  });
  const name=document.getElementById('hs').value||'(chưa ghi tên)';
  document.getElementById('score').textContent = name+': '+total.toFixed(2).replace('.',',')+' / '+max.toFixed(2).replace('.',',')+' điểm';
  document.getElementById('submit').style.display='none'; window.scrollTo({top:0,behavior:'smooth'});
}
"""


def _vn(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _q_html(q, s: str, i: int, qid: str) -> str:
    stem = latex_to_html(q.stem)
    body = [f"<div class='card q' data-id='{qid}' data-type='{s}'><div><b class='num'>Câu {i}.</b> {stem}</div>"]
    if s == "TN":
        for k, c in enumerate(q.choices):
            body.append(f"<label class='opt'><input type='radio' name='{qid}' value='{k}'>"
                        f"<span><b>{'ABCD'[k] if k < 4 else k + 1}.</b> {latex_to_html(c)}</span></label>")
    elif s == "DS":
        body.append("<div class='ds'>")
        for k, c in enumerate(q.choices):
            body.append(f"<div><b>{'abcd'[k] if k < 4 else k + 1})</b> {latex_to_html(c)}</div>"
                        f"<div class='tf'><label><input type='radio' name='{qid}_{k}' value='1'> Đúng</label>"
                        f"<label><input type='radio' name='{qid}_{k}' value='0'> Sai</label></div>")
        body.append("</div>")
    elif s == "KQ":
        body.append("<div style='margin-top:8px'>Trả lời: <input type='text' inputmode='decimal' "
                    "autocomplete='off' placeholder='vd: 0,25'></div>")
    else:
        body.append("<div style='margin-top:8px'><textarea rows='4' style='width:100%' "
                    "placeholder='Bài làm (giáo viên chấm)'></textarea></div>")
    if q.solution.strip():
        body.append(f"<div class='sol'><b>Lời giải.</b> {latex_to_html(q.solution)}</div>")
    body.append("</div>")
    return "".join(body)


def version_html(v: ExamVersion, *, ten_de="ĐỀ KIỂM TRA", thoi_gian=90, show_solution=True) -> str:
    key, parts = {}, []
    for s in SECTION_ORDER:
        qs = v.sections.get(s) or []
        if not qs:
            continue
        parts.append(f"<h2>{PART_TITLE[s]}</h2>")
        for i, q in enumerate(qs, 1):
            qid = f"{s}{i}"
            if s == "TN":
                key[qid] = q.correct.index(True) if sum(q.correct) == 1 else -1
            elif s == "DS":
                key[qid] = list(q.correct)
            elif s == "KQ":
                key[qid] = plain_answer(q.short_answer)
            parts.append(_q_html(q, s, i, qid))
    data = base64.b64encode(json.dumps(key, ensure_ascii=False).encode("utf-8")).decode()
    mj = json.dumps({"tex": {"inlineMath": [["$", "$"], ["\\(", "\\)"]], "macros": MATHJAX_MACROS},
                     "svg": {"fontCache": "global"}}, ensure_ascii=False)
    title = html.escape(f"{ten_de} – Mã đề {v.code}")
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>{CSS}</style><script>window.MathJax={mj};</script>
<script defer src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.min.js"></script>
</head><body><header><h1>{title}</h1><span id="timer">{thoi_gian:02d}:00</span></header><main>
<div class="card">Họ và tên: <input type="text" id="hs" placeholder="Nhập họ tên" style="width:min(320px,100%)">
<div id="score" style="margin-top:8px"></div>
<div style="color:var(--mut);font-size:14px;margin-top:6px">Thang điểm: Phần I {_vn(SCORING['TN'])}/câu · Phần II đúng 1/2/3/4 ý
được 0,1/0,25/0,5/1 · Phần III {_vn(SCORING['KQ'])}/câu. Hết giờ bài tự nộp.</div></div>
{''.join(parts)}</main>
<footer><button id="submit" onclick="submit(false)">Nộp bài</button></footer>
<script>const DATA="{data}", MINUTES={int(thoi_gian)}, SHOW_SOL={'true' if show_solution else 'false'};{JS}</script>
</body></html>"""


def export_html(versions, out_dir, **kw) -> list[str]:
    import os
    os.makedirs(out_dir, exist_ok=True)
    files = []
    for v in versions:
        p = os.path.join(out_dir, f"online_{v.code}.html")
        with open(p, "w", encoding="utf-8") as f:
            f.write(version_html(v, **kw))
        files.append(p)
    return files


# ---------------------------------------------------------------- Moodle XML
def _cdata(s: str) -> str:
    return "<![CDATA[" + s.replace("]]>", "]]]]><![CDATA[>") + "]]>"


def _mtext(s: str) -> str:
    return _cdata(dollar_to_paren(latex_to_html(s)))


def moodle_xml(questions, category: str = "Ngân hàng đề") -> str:
    """Xuất câu hỏi sang Moodle XML: TN → multichoice; Đúng/Sai → cloze (4 ý); trả lời ngắn → shortanswer."""
    out = ['<?xml version="1.0" encoding="UTF-8"?>', "<quiz>",
           f'<question type="category"><category><text>$course$/{html.escape(category)}</text></category></question>']
    for n, q in enumerate(questions, 1):
        name = html.escape(f"{q.id_code or 'cau'} #{q.db_id if q.db_id is not None else n}")
        fb = f"<generalfeedback format='html'><text>{_mtext(q.solution)}</text></generalfeedback>" if q.solution else ""
        if q.qtype == "TN" and sum(q.correct) == 1:
            ans = "".join(f"<answer fraction='{100 if ok else 0}' format='html'><text>{_mtext(c)}</text></answer>"
                          for c, ok in zip(q.choices, q.correct))
            out.append(f"<question type='multichoice'><name><text>{name}</text></name>"
                       f"<questiontext format='html'><text>{_mtext(q.stem)}</text></questiontext>{fb}"
                       f"<defaultgrade>{SCORING['TN']}</defaultgrade><single>true</single>"
                       f"<shuffleanswers>1</shuffleanswers><answernumbering>ABCD</answernumbering>{ans}</question>")
        elif q.qtype == "DS":
            items = "".join(
                f"<p>{'abcd'[k] if k < 4 else k + 1}) {dollar_to_paren(latex_to_html(c))} "
                f"{{1:MULTICHOICE:{'=' if ok else ''}Đúng~{'' if ok else '='}Sai}}</p>"
                for k, (c, ok) in enumerate(zip(q.choices, q.correct)))
            text = dollar_to_paren(latex_to_html(q.stem)) + items
            out.append(f"<question type='cloze'><name><text>{name}</text></name>"
                       f"<questiontext format='html'><text>{_cdata(text)}</text></questiontext>{fb}</question>")
        elif q.qtype == "KQ":
            a = plain_answer(q.short_answer)
            alts = {a, a.replace(",", ".")}
            ans = "".join(f"<answer fraction='100'><text>{html.escape(x)}</text></answer>" for x in alts)
            out.append(f"<question type='shortanswer'><name><text>{name}</text></name>"
                       f"<questiontext format='html'><text>{_mtext(q.stem)}</text></questiontext>{fb}"
                       f"<defaultgrade>{SCORING['KQ']}</defaultgrade><usecase>0</usecase>{ans}</question>")
        else:
            out.append(f"<question type='essay'><name><text>{name}</text></name>"
                       f"<questiontext format='html'><text>{_mtext(q.stem)}</text></questiontext>{fb}</question>")
    out.append("</quiz>")
    return "\n".join(out)


def export_moodle(questions, path: str, category: str = "Ngân hàng đề") -> str:
    with open(path, "w", encoding="utf-8") as f:
        f.write(moodle_xml(questions, category))
    return path
