import json
import queue
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ..core.generator import ExamVariant
from .online_gas import OnlineSubmissionResult, grade_online_submission


def detect_lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class LanArenaServer:
    def __init__(self, variant: ExamVariant, host: str = "0.0.0.0", port: int = 8765):
        self.variant, self.host, self.port = variant, host, port
        self._lock = threading.Lock()
        self._results: list[OnlineSubmissionResult] = []
        self._sse_queues: list[queue.Queue[str]] = []
        self._stop_event = threading.Event()
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def get_leaderboard(self) -> list[dict]:
        with self._lock:
            ordered = sorted(self._results, key=lambda r: (-r.total, r.elapsed_sec))
            return [{"rank": i, "student_name": r.student_name, "student_class": r.student_class, "total": r.total, "elapsed_sec": r.elapsed_sec} for i, r in enumerate(ordered, 1)]

    def _broadcast_sse(self, event_name: str, data_obj: dict) -> None:
        payload = f"event: {event_name}\ndata: {json.dumps(data_obj, ensure_ascii=False)}\n\n"
        with self._lock:
            for q in list(self._sse_queues):
                try:
                    q.put_nowait(payload)
                except queue.Full:
                    pass

    def start(self) -> tuple[str, int]:
        arena = self
        self._stop_event.clear()

        class ArenaHandler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"
            def log_message(self, format, *args):
                return
            def _send(self, body_bytes: bytes, ctype: str, status: int = 200):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body_bytes)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body_bytes)
            def do_GET(self):
                if self.path == "/api/exam":
                    qs = [{"qtype": q.qtype, "stem": q.stem, "choices": q.choices} for q in arena.variant.questions if q.qtype in ("TN", "DS", "KQ")]
                    self._send(json.dumps({"code": arena.variant.code, "questions": qs}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                elif self.path == "/api/leaderboard":
                    self._send(json.dumps({"code": arena.variant.code, "leaderboard": arena.get_leaderboard()}, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
                elif self.path == "/api/events":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "keep-alive")
                    self.end_headers()
                    q: queue.Queue[str] = queue.Queue(maxsize=64)
                    with arena._lock:
                        arena._sse_queues.append(q)
                    try:
                        self.wfile.write(f"event: leaderboard\ndata: {json.dumps({'leaderboard': arena.get_leaderboard()}, ensure_ascii=False)}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        while not arena._stop_event.is_set():
                            try:
                                self.wfile.write(q.get(timeout=0.5).encode("utf-8"))
                                self.wfile.flush()
                            except queue.Empty:
                                self.wfile.write(b": heartbeat\n\n")
                                self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    finally:
                        with arena._lock:
                            if q in arena._sse_queues:
                                arena._sse_queues.remove(q)
                elif self.path == "/host":
                    h = (
                        "<!DOCTYPE html><html lang='vi'><head><meta charset='utf-8'><title>Bảng Xếp Hạng SSE</title>"
                        "<style>body{font-family:system-ui;max-width:840px;margin:auto;padding:18px}table{width:100%;border-collapse:collapse}"
                        "th,td{border:1px solid #ddd;padding:10px;text-align:center}th{background:#1f4e78;color:#fff}</style></head><body>"
                        f"<h2>BẢNG XẾP HẠNG TRỰC TIẾP (SSE) — MÃ {arena.variant.code}</h2>"
                        "<table><thead><tr><th>Hạng</th><th>Học sinh</th><th>Lớp</th><th>Điểm</th><th>Giây</th></tr></thead><tbody id='tb'></tbody></table>"
                        "<script>const es=new EventSource('/api/events');es.addEventListener('leaderboard',e=>{const rows=JSON.parse(e.data).leaderboard;"
                        "tb.innerHTML=rows.map(x=>`<tr><td>${x.rank}</td><td>${x.student_name}</td><td>${x.student_class}</td><td><b>${x.total}</b></td><td>${x.elapsed_sec}</td></tr>`).join('');});</script></body></html>"
                    )
                    self._send(h.encode("utf-8"), "text/html; charset=utf-8")
                else:
                    h = (
                        "<!DOCTYPE html><html lang='vi'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                        f"<title>Đấu trường LAN — Mã {arena.variant.code}</title><style>body{{font-family:system-ui;max-width:820px;margin:auto;padding:14px}}.q{{border:1px solid #ddd;padding:12px;border-radius:8px;margin:10px 0}}button{{background:#1f4e78;color:#fff;border:none;padding:10px 18px;border-radius:6px}}</style></head>"
                        f"<body><h2>ĐẤU TRƯỜNG TOÁN LAN — MÃ {arena.variant.code}</h2><input id='nm' placeholder='Họ tên'> <input id='cl' placeholder='Lớp'><div id='qs'></div>"
                        "<button onclick='send()'>NỘP BÀI</button><div id='rs'></div><script>let t0=Date.now(),n1=0,n2=0,n3=0;"
                        "fetch('/api/exam').then(r=>r.json()).then(d=>{d.questions.forEach(q=>{const e=document.createElement('div');e.className='q';"
                        "if(q.qtype==='TN'){n1++;e.innerHTML=`<b>Câu ${n1}:</b> ${q.stem}<br>`+q.choices.map((c,j)=>`<label><input type=radio name=P1_${n1} value=${'ABCD'[j]}> ${'ABCD'[j]}. ${c}</label><br>`).join('');}"
                        "else if(q.qtype==='DS'){n2++;e.innerHTML=`<b>Đ/S ${n2}:</b> ${q.stem}<br>`+q.choices.map((c,j)=>`<div>${'abcd'[j]}) ${c} <label><input type=radio name=P2_${n2}_${j} value=Đ>Đ</label><label><input type=radio name=P2_${n2}_${j} value=S>S</label></div>`).join('');}"
                        "else if(q.qtype==='KQ'){n3++;e.innerHTML=`<b>TLN ${n3}:</b> ${q.stem}<br><input id=P3_${n3} maxlength=4>`;}"
                        "qs.appendChild(e);});});async function send(){const ans={};for(let i=1;i<=n1;i++){const el=document.querySelector(`input[name=P1_${i}]:checked`);ans[`P1_${i}`]=el?el.value:'';}"
                        "for(let i=1;i<=n2;i++){let s='';for(let j=0;j<4;j++){const el=document.querySelector(`input[name=P2_${i}_${j}]:checked`);s+=el?el.value:'-';}ans[`P2_${i}`]=s;}"
                        "for(let i=1;i<=n3;i++){ans[`P3_${i}`]=(document.getElementById(`P3_${i}`).value||'').trim();}"
                        "const r=await(await fetch('/api/submit',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({student_name:nm.value,student_class:cl.value,elapsed_sec:Math.round((Date.now()-t0)/1000),answers:ans})})).json();rs.innerHTML=`<h3>Điểm: ${r.total}</h3>`;}</script></body></html>"
                    )
                    self._send(h.encode("utf-8"), "text/html; charset=utf-8")
            def do_POST(self):
                if self.path != "/api/submit":
                    self._send(b'{"error":"Not found"}', "application/json", 404)
                    return
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8") or "{}")
                res = grade_online_submission(arena.variant, data.get("answers", {}), student_name=data.get("student_name", "Ẩn danh"), student_class=data.get("student_class", ""), elapsed_sec=int(data.get("elapsed_sec", 0)))
                with arena._lock:
                    arena._results.append(res)
                arena._broadcast_sse("leaderboard", {"leaderboard": arena.get_leaderboard()})
                self._send(json.dumps({"status": "ok", "total": res.total}).encode("utf-8"), "application/json")

        self._httpd = ThreadingHTTPServer((self.host, self.port), ArenaHandler)
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        return self._httpd.server_address

    def stop(self) -> None:
        self._stop_event.set()
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
