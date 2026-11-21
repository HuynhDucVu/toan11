import csv
import datetime
import json
import os
import secrets
from dataclasses import dataclass, field
from typing import Sequence
from ..core.generator import ExamVariant
from ..core.matrix_cv7991 import DEFAULT_DS_NONLINEAR_SCALE

GAS_CODE_TEMPLATE = """// Triển khai: Deploy > New deployment > Web app (Execute as: Me | Who has access: Anyone)
const EXAM_FOLDER_NAME = "__FOLDER_NAME__";
const SERVER_ANSWER_KEY = __SERVER_KEY_JSON__;
const TF_SCALE = [0, 0.1, 0.25, 0.5, 1.0];

function doGet(e) {
  return HtmlService.createHtmlOutputFromFile("ExamClient")
    .setTitle("Đề trực tuyến — Mã " + SERVER_ANSWER_KEY.code)
    .addMetaTag("viewport", "width=device-width, initial-scale=1")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

function submitFromClient(payload) { return gradeAndSave_(payload); }

function doPost(e) {
  const payload = JSON.parse((e && e.postData && e.postData.contents) ? e.postData.contents : "{}");
  return ContentService.createTextOutput(JSON.stringify(gradeAndSave_(payload))).setMimeType(ContentService.MimeType.JSON);
}

function gradeAndSave_(data) {
  const ans = data.answers || {};
  let s1 = 0, s2 = 0, s3 = 0;
  (SERVER_ANSWER_KEY.TN || []).forEach(function(it) { if (String(ans["P1_"+it[0]]||"").trim().toUpperCase() === String(it[1]).toUpperCase()) s1 += 0.25; });
  (SERVER_ANSWER_KEY.DS || []).forEach(function(it) { let h=0, st=String(ans["P2_"+it[0]]||"----").toUpperCase(); for(let j=0;j<4;j++) if(st[j]===String(it[1])[j]) h++; s2 += TF_SCALE[h]||0; });
  (SERVER_ANSWER_KEY.KQ || []).forEach(function(it) { const st=String(ans["P3_"+it[0]]||"").trim().replace(".",","); if(st && st===String(it[1]).trim().replace(".",",")) s3 += 0.5; });
  const total = Number((s1+s2+s3).toFixed(2));
  const lock = LockService.getScriptLock();
  lock.waitLock(15000);
  try {
    const folder = getOrCreateFolder_(EXAM_FOLDER_NAME);
    const ss = getOrCreateSheet_(folder, EXAM_FOLDER_NAME + "_KetQua");
    const sh = ss.getSheets()[0];
    if (sh.getLastRow() === 0) sh.appendRow(["ThoiGian","HoTen","Lop","MaDe","DiemP1","DiemP2","DiemP3","TongDiem","ChiTietJSON"]);
    sh.appendRow([new Date(), data.student_name||"", data.student_class||"", SERVER_ANSWER_KEY.code, Number(s1.toFixed(2)), Number(s2.toFixed(2)), Number(s3.toFixed(2)), total, JSON.stringify(ans)]);
  } finally { lock.releaseLock(); }
  return { status: "ok", score_p1: Number(s1.toFixed(2)), score_p2: Number(s2.toFixed(2)), score_p3: Number(s3.toFixed(2)), total: total };
}

function getOrCreateFolder_(name) { const it = DriveApp.getFoldersByName(name); return it.hasNext() ? it.next() : DriveApp.createFolder(name); }
function getOrCreateSheet_(folder, name) { const it = folder.getFilesByName(name); if (it.hasNext()) return SpreadsheetApp.openById(it.next().getId()); const ss = SpreadsheetApp.create(name); DriveApp.getFileById(ss.getId()).moveTo(folder); return ss; }
"""


@dataclass
class OnlineSubmissionResult:
    student_name: str
    student_class: str
    exam_code: str
    score_p1: float
    score_p2: float
    score_p3: float
    score_tl: float
    total: float
    elapsed_sec: int = 0
    item_correct: dict[str, bool] = field(default_factory=dict)


def make_drive_folder_id(exam_slug: str) -> str:
    return f"{exam_slug}-T11-{datetime.date.today().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def grade_online_submission(
    variant: ExamVariant, student_answers: dict, p1_weight: float = 0.25, p3_weight: float = 0.5,
    ds_scale: dict[int, float] | None = None, essay_scores: Sequence[float] | None = None,
    student_name: str = "", student_class: str = "", elapsed_sec: int = 0,
) -> OnlineSubmissionResult:
    scale = ds_scale or DEFAULT_DS_NONLINEAR_SCALE
    flags: dict[str, bool] = {}
    s1 = s2 = s3 = 0.0
    for qn, ok in variant.key_tn:
        hit = str(student_answers.get(f"P1_{qn}", "")).strip().upper() == ok
        flags[f"P1_{qn}"] = hit
        if hit:
            s1 += p1_weight
    for qn, ok in variant.key_ds:
        stu = str(student_answers.get(f"P2_{qn}", "----")).strip().upper()
        hits = sum(1 for c, s in zip(ok, stu) if c == s)
        flags[f"P2_{qn}"] = hits == 4
        s2 += float(scale.get(hits, 0.0))
    for qn, ok in variant.key_kq:
        stu = str(student_answers.get(f"P3_{qn}", "")).strip().replace(".", ",")
        hit = bool(stu) and stu == str(ok).strip().replace(".", ",")
        flags[f"P3_{qn}"] = hit
        if hit:
            s3 += p3_weight
    stl = round(sum(float(x) for x in (essay_scores or [])), 2)
    return OnlineSubmissionResult(student_name, student_class, variant.code, round(s1, 2), round(s2, 2), round(s3, 2), stl, round(s1 + s2 + s3 + stl, 2), elapsed_sec, flags)


def export_online_exam_bundle(
    variant: ExamVariant, out_dir: str, exam_slug: str = "DeKiemTra",
    gas_webapp_url: str = "", duration_min: int = 90, server_only_key: bool = True,
) -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    fid = make_drive_folder_id(exam_slug)
    server_key = {"code": variant.code, "TN": variant.key_tn, "DS": variant.key_ds, "KQ": variant.key_kq}
    gs_path = os.path.join(out_dir, "Code.gs")
    open(gs_path, "w", encoding="utf-8").write(GAS_CODE_TEMPLATE.replace("__FOLDER_NAME__", fid).replace("__SERVER_KEY_JSON__", json.dumps(server_key, ensure_ascii=False)))

    client_payload = {
        "folder_id": fid, "code": variant.code, "gas_url": gas_webapp_url, "duration_sec": duration_min * 60,
        "questions": [{"qtype": q.qtype, "stem": q.stem, "choices": q.choices} for q in variant.questions if q.qtype in ("TN", "DS", "KQ")],
    }
    if not server_only_key:
        client_payload["offline_key"] = server_key

    html_path = os.path.join(out_dir, "ExamClient.html")
    html_doc = f"""<!DOCTYPE html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Đề trực tuyến — Mã {variant.code}</title>
<script>window.MathJax={{tex:{{inlineMath:[['$','$'],['\\\\(','\\\\)']]}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js" async></script>
<style>body{{font-family:system-ui,sans-serif;max-width:860px;margin:auto;padding:14px;line-height:1.6}}
.top{{position:sticky;top:0;background:#1f4e78;color:#fff;padding:10px 14px;border-radius:8px;display:flex;justify-content:space-between}}
.card{{border:1px solid #ddd;border-radius:8px;padding:14px;margin:12px 0}} button{{background:#1f4e78;color:#fff;border:none;padding:10px 18px;border-radius:6px;cursor:pointer}}</style>
</head><body><div class="top"><b>MÃ ĐỀ {variant.code}</b><span id="timer">--:--</span><span id="scoreBox"></span></div>
<p><input id="stuName" placeholder="Họ và tên"> <input id="stuClass" placeholder="Lớp"></p><div id="root"></div>
<button onclick="submitExam()">NỘP BÀI</button><script>
const CFG={json.dumps(client_payload, ensure_ascii=False)}; let rem=CFG.duration_sec,n1=0,n2=0,n3=0;
CFG.questions.forEach(q=>{{const d=document.createElement('div');d.className='card';
if(q.qtype==='TN'){{n1++;d.innerHTML=`<b>Phần I - Câu ${{n1}}:</b> ${{q.stem}}<br>`+q.choices.map((c,j)=>`<label><input type=radio name="P1_${{n1}}" value="${{'ABCD'[j]}}"> <b>${{'ABCD'[j]}}.</b> ${{c}}</label><br>`).join('');}}
else if(q.qtype==='DS'){{n2++;d.innerHTML=`<b>Phần II - Câu ${{n2}}:</b> ${{q.stem}}<br>`+q.choices.map((c,j)=>`<div><b>${{'abcd'[j]}})</b> ${{c}} <label><input type=radio name="P2_${{n2}}_${{j}}" value="Đ">Đ</label> <label><input type=radio name="P2_${{n2}}_${{j}}" value="S">S</label></div>`).join('');}}
else if(q.qtype==='KQ'){{n3++;d.innerHTML=`<b>Phần III - Câu ${{n3}}:</b> ${{q.stem}}<br><input id="P3_${{n3}}" maxlength=4 placeholder="VD: -1,5">`;}}
document.getElementById('root').appendChild(d);}});
const tk=setInterval(()=>{{rem=Math.max(0,rem-1);timer.innerText=`${{String(Math.floor(rem/60)).padStart(2,'0')}}:${{String(rem%60).padStart(2,'0')}}`;if(rem===0){{clearInterval(tk);submitExam();}}}},1000);
function collect(){{const a={{}};for(let i=1;i<=n1;i++){{const e=document.querySelector(`input[name="P1_${{i}}"]:checked`);a[`P1_${{i}}`]=e?e.value:'';}}
for(let i=1;i<=n2;i++){{let s='';for(let j=0;j<4;j++){{const e=document.querySelector(`input[name="P2_${{i}}_${{j}}"]:checked`);s+=e?e.value:'-';}}a[`P2_${{i}}`]=s;}}
for(let i=1;i<=n3;i++){{a[`P3_${{i}}`]=(document.getElementById(`P3_${{i}}`).value||'').trim().replace('.',',');}}return a;}}
async function submitExam(){{clearInterval(tk);const pl={{student_name:stuName.value,student_class:stuClass.value,exam_code:CFG.code,answers:collect()}};
if(typeof google!=='undefined'&&google.script&&google.script.run){{google.script.run.withSuccessHandler(r=>{{scoreBox.innerText=`Điểm: ${{r.total}}`;}}).submitFromClient(pl);}}
else if(CFG.gas_url){{await fetch(CFG.gas_url,{{method:'POST',mode:'no-cors',body:JSON.stringify(pl)}});scoreBox.innerText='Đã nộp bài!';}}
}}
</script></body></html>"""
    open(html_path, "w", encoding="utf-8").write(html_doc)
    return {"folder_id": fid, "gas_script": gs_path, "exam_html": html_path}


def export_online_results(results: Sequence[OnlineSubmissionResult], out_dir: str, exam_title: str = "Đề trực tuyến", exam_url: str = "") -> dict[str, str]:
    import openpyxl
    os.makedirs(out_dir, exist_ok=True)
    xp, cp, jp = os.path.join(out_dir, "ket_qua.xlsx"), os.path.join(out_dir, "ket_qua.csv"), os.path.join(out_dir, "ket_qua.json")
    headers = ["Họ tên", "Lớp", "Mã đề", "Phần I", "Phần II", "Phần III", "Tự luận", "Tổng điểm", "Thời gian (s)"]
    rows = [[r.student_name, r.student_class, r.exam_code, r.score_p1, r.score_p2, r.score_p3, r.score_tl, r.total, r.elapsed_sec] for r in results]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "KetQua"
    ws.append(headers)
    for row in rows:
        ws.append(row)
    tots = [r.total for r in results]
    wi = wb.create_sheet("Thong tin")
    wi.append(["Chỉ số", "Giá trị"])
    wi.append(["Tên đề thi", exam_title])
    wi.append(["Đường dẫn", exam_url])
    wi.append(["Tổng số bài nộp", len(tots)])
    wi.append(["Điểm trung bình", round(sum(tots) / len(tots), 2) if tots else 0.0])
    wi.append(["Điểm cao nhất", max(tots) if tots else 0.0])
    wi.append(["Điểm thấp nhất", min(tots) if tots else 0.0])
    wb.save(xp)
    with open(cp, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        w.writerows(rows)
    json.dump([r.__dict__ for r in results], open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    return {"xlsx": xp, "csv": cp, "json": jp}
