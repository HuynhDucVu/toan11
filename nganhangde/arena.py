"""Phòng thi LAN: máy giáo viên phát đề qua Wi-Fi/mạng LAN, học sinh làm bài trên điện thoại/máy tính.

* Không cần Internet: chỉ cần các máy cùng mạng Wi-Fi/LAN. MathJax (hiển thị công thức) đi kèm phần mềm và
  được máy giáo viên phát cho học sinh.
* Trang làm bài **không chứa đáp án**: học sinh nộp → máy chủ chấm → trả đáp án để hiện lời giải.
* Mỗi học sinh vào trang chủ, nhập họ tên → được chia mã đề lần lượt (101, 102, 103, …).
* Giáo viên xem bảng điểm trực tiếp (trong phần mềm hoặc trang /bang), xuất CSV.

Chỉ dùng thư viện chuẩn (http.server, chạy luồng nền).
"""
from __future__ import annotations

import csv
import html
import itertools
import json
import socket
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse

from .online import grade_answers, version_html


def lan_ip() -> str:
    """Địa chỉ IP của máy trong mạng LAN (không gửi gói tin nào ra ngoài)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


HOME = """<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{font-family:system-ui,Segoe UI,Arial;max-width:520px;margin:40px auto;padding:0 16px}}
input,button{{font-size:18px;padding:10px;width:100%;box-sizing:border-box;margin-top:10px}}
button{{background:#1f4e79;color:#fff;border:0;border-radius:6px}}</style></head><body>
<h2>{title}</h2><p>Thời gian làm bài: {tg} phút.</p>
<form action="vao" method="get"><input name="ten" placeholder="Họ và tên, lớp" required autofocus>
<button>Vào làm bài</button></form></body></html>"""


class Arena:
    def __init__(self, versions, *, ten_de="BÀI KIỂM TRA", thoi_gian=45, scoring=None, show_solution=True,
                 host="0.0.0.0", port=8765):
        if not versions:
            raise ValueError("Chưa có mã đề nào")
        self.versions = {v.code: v for v in versions}
        self.ten_de, self.thoi_gian, self.scoring, self.show_solution = ten_de, thoi_gian, scoring, show_solution
        self.host, self.port = host, port
        self.results: list[dict] = []
        self.lock = threading.Lock()
        self._next = itertools.cycle(list(self.versions))
        self._pages = {}
        self.httpd = None
        self.thread = None

    # ------------------------------------------------------------------ trang
    def page(self, code: str) -> str:
        if code not in self._pages:
            self._pages[code] = version_html(self.versions[code], ten_de=self.ten_de, thoi_gian=self.thoi_gian,
                                             show_solution=self.show_solution, scoring=self.scoring, arena=True)
        return self._pages[code]

    def submit(self, data: dict) -> dict:
        code = str(data.get("ma", ""))
        v = self.versions.get(code)
        if v is None:
            return {"loi": "Mã đề không hợp lệ"}
        ans = data.get("tra_loi") or {}
        total, mx, per = grade_answers(v, ans, self.scoring)
        row = {"luc": datetime.now().strftime("%H:%M:%S"), "ten": str(data.get("ten", ""))[:80], "ma": code,
               "diem": total, "toi_da": mx, "chi_tiet": per, "tra_loi": ans}
        with self.lock:
            self.results.append(row)
        from .online import answer_key
        return {"key": answer_key(v), "diem": total, "toi_da": mx}

    def board_html(self) -> str:
        with self.lock:
            rows = sorted(self.results, key=lambda r: -r["diem"])
        tr = "".join(f"<tr><td>{i}</td><td>{html.escape(r['ten'])}</td><td>{r['ma']}</td>"
                     f"<td><b>{str(r['diem']).replace('.', ',')}</b> / {str(r['toi_da']).replace('.', ',')}</td><td>{r['luc']}</td></tr>"
                     for i, r in enumerate(rows, 1))
        return (f"<!doctype html><html lang='vi'><head><meta charset='utf-8'><meta http-equiv='refresh' content='5'>"
                f"<title>Bảng điểm</title><style>body{{font-family:system-ui,Arial;margin:24px}}td,th{{padding:6px 12px;"
                f"border-bottom:1px solid #ddd}}</style></head><body><h2>{html.escape(self.ten_de)} – bảng điểm "
                f"({len(rows)} bài)</h2><table><tr><th>#</th><th>Họ tên</th><th>Mã đề</th><th>Điểm</th><th>Nộp lúc</th>"
                f"</tr>{tr}</table></body></html>")

    def export_csv(self, path: str) -> str:
        with self.lock:
            rows = list(self.results)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["Họ tên", "Mã đề", "Điểm", "Tối đa", "Nộp lúc"] + sorted({k for r in rows for k in r["chi_tiet"]}))
            keys = sorted({k for r in rows for k in r["chi_tiet"]})
            for r in rows:
                w.writerow([r["ten"], r["ma"], str(r["diem"]).replace(".", ","), str(r["toi_da"]).replace(".", ","),
                            r["luc"]] + [str(r["chi_tiet"].get(k, "")).replace(".", ",") for k in keys])
        return path

    # ------------------------------------------------------------------ máy chủ
    def _handler(self):
        arena = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):          # không in log ra console
                pass

            def _send(self, code, body: str | bytes, ctype="text/html; charset=utf-8"):
                b = body.encode("utf-8") if isinstance(body, str) else body
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(b)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if u.path in ("/", "/index.html"):
                    return self._send(200, HOME.format(title=html.escape(arena.ten_de), tg=arena.thoi_gian))
                if u.path == "/vao":
                    ten = (q.get("ten") or [""])[0].strip()
                    with arena.lock:
                        code = next(arena._next)
                    self.send_response(302)
                    self.send_header("Location", f"/de/{code}/?ten={quote(ten)}")
                    self.end_headers()
                    return None
                if u.path.startswith("/de/"):
                    code = u.path.split("/")[2]
                    if code in arena.versions:
                        return self._send(200, arena.page(code))
                if u.path == "/mathjax.js":
                    from .online import mathjax_local
                    try:
                        with open(mathjax_local(), "rb") as f:
                            return self._send(200, f.read(), "application/javascript")
                    except OSError:
                        return self._send(404, "")
                if u.path == "/bang":
                    return self._send(200, arena.board_html())
                return self._send(404, "Không có trang này")

            def do_POST(self):
                if not self.path.rstrip("/").endswith("/nop"):
                    return self._send(404, "Không có trang này")
                n = int(self.headers.get("Content-Length") or 0)
                if n > 2_000_000:
                    return self._send(413, json.dumps({"loi": "Bài quá lớn"}), "application/json")
                try:
                    data = json.loads(self.rfile.read(n).decode("utf-8"))
                    res = arena.submit(data)
                except (ValueError, UnicodeDecodeError):
                    res = {"loi": "Dữ liệu nộp bài không hợp lệ"}
                return self._send(200, json.dumps(res, ensure_ascii=False), "application/json; charset=utf-8")
        return H

    def start(self):
        self.httpd = ThreadingHTTPServer((self.host, self.port), self._handler())
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        return self.url()

    def url(self) -> str:
        return f"http://{lan_ip() if self.host in ('0.0.0.0', '') else self.host}:{self.port}/"

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
