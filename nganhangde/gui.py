"""Giao diện cửa sổ (Tkinter – có sẵn trong Python trên Windows, không cần cài thêm)."""
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .db import Bank
from .exporter import export_questions, export_versions
from .generator import NotEnoughQuestions, Rule, make_versions
from .idcode import MUC_DO, parse_id
from .parser import parse_file, parse_tex, validate

QTYPES = ["", "TN", "DS", "KQ", "TL"]
TEN_LOAI = {"TN": "Trắc nghiệm", "DS": "Đúng/Sai", "KQ": "Trả lời ngắn", "TL": "Tự luận"}


class App(tk.Tk):
    def __init__(self, db_path: str):
        super().__init__()
        self.bank = Bank(db_path)
        self.title(f"Ngân hàng đề thi – {os.path.abspath(db_path)}")
        self.geometry("1200x720")
        self._build_toolbar()
        self._build_body()
        self.refresh()

    # ------------------------------------------------------------ giao diện
    def _build_toolbar(self):
        bar = ttk.Frame(self, padding=4)
        bar.pack(fill="x")
        for text, cmd in (("Nhập file .tex", self.import_files), ("Thêm câu", self.add_question),
                          ("Sửa câu", self.edit_question), ("Xoá câu", self.delete_questions),
                          ("Xuất câu đã chọn", self.export_selected), ("Tạo đề (trộn đề)", self.open_generator),
                          ("Thống kê", self.show_stats)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=2)
        self.status = tk.StringVar()
        ttk.Label(bar, textvariable=self.status).pack(side="right")

    def _build_body(self):
        pw = ttk.PanedWindow(self, orient="horizontal")
        pw.pack(fill="both", expand=True)

        # --- bộ lọc
        f = ttk.LabelFrame(pw, text="Bộ lọc", padding=6)
        self.v_type, self.v_lop, self.v_chuong = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_muc, self.v_id, self.v_text = tk.StringVar(), tk.StringVar(), tk.StringVar()
        rows = (("Loại câu", ttk.Combobox(f, textvariable=self.v_type, values=QTYPES, width=12, state="readonly")),
                ("Lớp (0=10,1=11,2=12)", ttk.Combobox(f, textvariable=self.v_lop, values=["", "0", "1", "2"], width=12)),
                ("Chương", ttk.Entry(f, textvariable=self.v_chuong, width=14)),
                ("Mức độ", ttk.Combobox(f, textvariable=self.v_muc, values=["", "N", "H", "V", "C"], width=12, state="readonly")),
                ("Mẫu ID (* ?)", ttk.Entry(f, textvariable=self.v_id, width=14)),
                ("Từ khoá", ttk.Entry(f, textvariable=self.v_text, width=14)))
        for r, (lbl, w) in enumerate(rows):
            ttk.Label(f, text=lbl).grid(row=2 * r, column=0, sticky="w")
            w.grid(row=2 * r + 1, column=0, sticky="we", pady=(0, 6))
            w.bind("<Return>", lambda e: self.refresh())
        ttk.Button(f, text="Lọc", command=self.refresh).grid(row=20, column=0, sticky="we")
        ttk.Button(f, text="Xoá lọc", command=self.clear_filter).grid(row=21, column=0, sticky="we", pady=4)
        pw.add(f, weight=0)

        # --- danh sách
        mid = ttk.PanedWindow(pw, orient="vertical")
        cols = ("id", "loai", "ma", "muc", "dapan", "noidung")
        self.tree = ttk.Treeview(mid, columns=cols, show="headings", selectmode="extended")
        for c, t, w in zip(cols, ("#", "Loại", "ID", "Mức độ", "Đáp án", "Nội dung"),
                           (50, 90, 90, 100, 70, 600)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=(c == "noidung"))
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", lambda e: self.edit_question())
        mid.add(self.tree, weight=3)

        # --- xem trước
        self.preview = tk.Text(mid, wrap="word", height=14, font=("Consolas", 10))
        mid.add(self.preview, weight=2)
        pw.add(mid, weight=1)

    # ------------------------------------------------------------ dữ liệu
    def clear_filter(self):
        for v in (self.v_type, self.v_lop, self.v_chuong, self.v_muc, self.v_id, self.v_text):
            v.set("")
        self.refresh()

    def refresh(self):
        qs = self.bank.search(qtype=self.v_type.get() or None, lop=self.v_lop.get() or None,
                              chuong=self.v_chuong.get().upper() or None,
                              muc_do=self.v_muc.get() or None, id_like=self.v_id.get() or None,
                              text=self.v_text.get() or None)
        self.tree.delete(*self.tree.get_children())
        for q in qs:
            idc = parse_id(q.id_code) if q.id_code else None
            muc = MUC_DO.get(idc.muc_do, "") if idc else ""
            self.tree.insert("", "end", iid=str(q.db_id), values=(
                q.db_id, TEN_LOAI[q.qtype], q.id_code, muc, q.answer_text, " ".join(q.stem.split())[:200]))
        self.status.set(f"Hiển thị {len(qs)} / {self.bank.count()} câu")

    def selected_ids(self):
        return [int(i) for i in self.tree.selection()]

    def on_select(self, _=None):
        ids = self.selected_ids()
        self.preview.delete("1.0", "end")
        if not ids:
            return
        q = self.bank.get(ids[0])
        idc = parse_id(q.id_code) if q.id_code else None
        head = (idc.describe() if idc else "Chưa có ID") + "\n"
        warns = validate(q)
        if warns:
            head += "Cảnh báo: " + "; ".join(warns) + "\n"
        self.preview.insert("end", head + "-" * 60 + "\n" + q.to_latex())

    # ------------------------------------------------------------ thao tác
    def import_files(self):
        paths = filedialog.askopenfilenames(filetypes=[("LaTeX", "*.tex"), ("Tất cả", "*.*")])
        if not paths:
            return
        report = []
        for p in paths:
            qs = parse_file(p)
            added = sum(1 for q in qs if self.bank.add(q, p))
            report.append(f"{os.path.basename(p)}: {len(qs)} câu, thêm {added}, trùng {len(qs) - added}")
        self.refresh()
        messagebox.showinfo("Nhập dữ liệu", "\n".join(report))

    def add_question(self):
        EditDialog(self, None)

    def edit_question(self):
        ids = self.selected_ids()
        if ids:
            EditDialog(self, ids[0])

    def delete_questions(self):
        ids = self.selected_ids()
        if ids and messagebox.askyesno("Xoá", f"Xoá {len(ids)} câu đã chọn?"):
            self.bank.delete(ids)
            self.refresh()

    def export_selected(self):
        ids = self.selected_ids() or [int(i) for i in self.tree.get_children()]
        path = filedialog.asksaveasfilename(defaultextension=".tex", filetypes=[("LaTeX", "*.tex")])
        if path:
            export_questions([self.bank.get(i) for i in ids], path)
            messagebox.showinfo("Xuất", f"Đã xuất {len(ids)} câu ra\n{path}")

    def show_stats(self):
        win = tk.Toplevel(self)
        win.title("Thống kê ngân hàng")
        cols = ("lop", "mon", "chuong", "qtype", "muc_do", "n")
        tv = ttk.Treeview(win, columns=cols, show="headings", height=25)
        for c, t in zip(cols, ("Lớp", "Môn", "Chương", "Loại", "Mức độ", "Số câu")):
            tv.heading(c, text=t)
            tv.column(c, width=80)
        for r in self.bank.stats():
            tv.insert("", "end", values=tuple(r))
        tv.pack(fill="both", expand=True)

    def open_generator(self):
        GeneratorDialog(self)


class EditDialog(tk.Toplevel):
    """Soạn/sửa 1 câu trực tiếp bằng mã LaTeX \\begin{ex}...\\end{ex}."""
    TEMPLATE = ("\\begin{ex}%[Nguồn]%[0D1N1-1]\n\tNội dung câu hỏi\n\t\\choice\n\t{\\True A}\n\t{B}\n\t{C}\n\t{D}\n"
                "\t\\loigiai{\n\t\tLời giải\n\t}\n\\end{ex}")

    def __init__(self, app: App, db_id: int | None):
        super().__init__(app)
        self.app, self.db_id = app, db_id
        self.title("Sửa câu" if db_id else "Thêm câu")
        self.geometry("800x500")
        self.text = tk.Text(self, wrap="word", font=("Consolas", 11), undo=True)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", app.bank.get(db_id).to_latex() if db_id else self.TEMPLATE)
        ttk.Button(self, text="Lưu", command=self.save).pack(pady=4)

    def save(self):
        qs = parse_tex(self.text.get("1.0", "end"))
        if len(qs) != 1:
            messagebox.showerror("Lỗi", f"Cần đúng 1 khối \\begin{{ex}}...\\end{{ex}} (đang có {len(qs)})", parent=self)
            return
        q = qs[0]
        warns = validate(q)
        if warns and not messagebox.askyesno("Cảnh báo", "\n".join(warns) + "\n\nVẫn lưu?", parent=self):
            return
        if self.db_id:
            self.app.bank.update(self.db_id, q)
        elif self.app.bank.add(q, "nhap-tay") is None:
            messagebox.showerror("Trùng", "Câu này đã có trong kho", parent=self)
            return
        self.app.refresh()
        self.destroy()


class GeneratorDialog(tk.Toplevel):
    """Nhập ma trận đề → sinh nhiều mã đề."""

    def __init__(self, app: App):
        super().__init__(app)
        self.app = app
        self.title("Tạo đề theo ma trận")
        self.geometry("760x520")

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        self.v_ten = tk.StringVar(value="ĐỀ KIỂM TRA")
        self.v_truong = tk.StringVar()
        self.v_tg = tk.StringVar(value="90")
        self.v_n = tk.StringVar(value="4")
        self.v_out = tk.StringVar(value=os.path.abspath("de_xuat"))
        self.v_diff = tk.BooleanVar(value=False)
        self.v_unused = tk.BooleanVar(value=True)
        for r, (lbl, var) in enumerate((("Tên đề", self.v_ten), ("Trường", self.v_truong),
                                        ("Thời gian (phút)", self.v_tg), ("Số mã đề", self.v_n),
                                        ("Thư mục xuất", self.v_out))):
            ttk.Label(top, text=lbl).grid(row=r, column=0, sticky="w")
            ttk.Entry(top, textvariable=var, width=60).grid(row=r, column=1, sticky="we")
        ttk.Checkbutton(top, text="Mỗi mã đề một bộ câu khác nhau", variable=self.v_diff).grid(row=5, column=1, sticky="w")
        ttk.Checkbutton(top, text="Ưu tiên câu ít được dùng", variable=self.v_unused).grid(row=6, column=1, sticky="w")

        mf = ttk.LabelFrame(self, text="Ma trận (mỗi dòng: loại, mẫu ID, mức độ, số câu)", padding=6)
        mf.pack(fill="both", expand=True, padx=6)
        cols = ("qtype", "id", "muc_do", "count")
        self.tv = ttk.Treeview(mf, columns=cols, show="headings", height=8)
        for c, t in zip(cols, ("Loại", "Mẫu ID", "Mức độ", "Số câu")):
            self.tv.heading(c, text=t)
        self.tv.pack(fill="both", expand=True)
        add = ttk.Frame(mf)
        add.pack(fill="x", pady=4)
        self.e_type = ttk.Combobox(add, values=QTYPES[1:], width=5, state="readonly")
        self.e_type.set("TN")
        self.e_id, self.e_cnt = ttk.Entry(add, width=14), ttk.Entry(add, width=5)
        self.e_id.insert(0, "*")
        self.e_muc = ttk.Combobox(add, values=["", "N", "H", "V", "C"], width=4, state="readonly")
        for w in (self.e_type, self.e_id, self.e_muc, self.e_cnt):
            w.pack(side="left", padx=2)
        ttk.Button(add, text="Thêm dòng", command=self.add_rule).pack(side="left", padx=4)
        ttk.Button(add, text="Xoá dòng", command=lambda: [self.tv.delete(i) for i in self.tv.selection()]).pack(side="left")
        ttk.Button(self, text="TẠO ĐỀ", command=self.generate).pack(pady=6)

    def add_rule(self):
        try:
            n = int(self.e_cnt.get())
        except ValueError:
            messagebox.showerror("Lỗi", "Số câu phải là số nguyên", parent=self)
            return
        self.tv.insert("", "end", values=(self.e_type.get(), self.e_id.get() or "*", self.e_muc.get(), n))

    def generate(self):
        rules = [Rule(v[0], int(v[3]), str(v[1]), v[2] or None)
                 for v in (self.tv.item(i, "values") for i in self.tv.get_children())]
        if not rules:
            messagebox.showerror("Lỗi", "Chưa có dòng ma trận nào", parent=self)
            return
        try:
            vs = make_versions(self.app.bank, rules, int(self.v_n.get()),
                               same_questions=not self.v_diff.get(), prefer_unused=self.v_unused.get())
        except NotEnoughQuestions as e:
            messagebox.showerror("Không đủ câu", str(e), parent=self)
            return
        files = export_versions(vs, self.v_out.get(), ten_de=self.v_ten.get(),
                                truong=self.v_truong.get(), thoi_gian=self.v_tg.get())
        self.app.bank.mark_used({q.db_id for v in vs for q in v.all_questions()})
        messagebox.showinfo("Xong", f"Đã tạo {len(vs)} mã đề:\n" + "\n".join(files), parent=self)


def run(db_path: str | None = None):
    App(db_path or "nganhang.db").mainloop()


if __name__ == "__main__":
    run()
