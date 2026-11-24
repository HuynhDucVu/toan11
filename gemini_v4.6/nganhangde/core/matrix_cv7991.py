from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable
from .parser import Question

CV7991_DEFAULT_POINTS = {"TN": 3.0, "DS": 2.0, "KQ": 2.0, "TL": 3.0}
DEFAULT_DS_NONLINEAR_SCALE = {0: 0.0, 1: 0.1, 2: 0.25, 3: 0.5, 4: 1.0}


@dataclass
class MatrixRule:
    qtype: str
    count: int
    id_glob: str = "*"
    muc_do: str = ""
    zone: int = 0
    topic: str = ""
    competency: str = ""


@dataclass
class ExamMatrix:
    name: str
    rules: list[MatrixRule] = field(default_factory=list)
    part_points: dict[str, float] = field(default_factory=lambda: dict(CV7991_DEFAULT_POINTS))
    essay_item_points: list[float] = field(default_factory=list)
    ds_scale: dict[int, float] = field(default_factory=lambda: dict(DEFAULT_DS_NONLINEAR_SCALE))
    template_path: str = ""

    def total_by_type(self) -> dict[str, int]:
        counts = {"TN": 0, "DS": 0, "KQ": 0, "TL": 0}
        for r in self.rules:
            if r.qtype in counts:
                counts[r.qtype] += r.count
        return counts

    def set_essay_total_points(self, total_points: float) -> list[float]:
        self.part_points["TL"] = round(float(total_points), 4)
        n_tl = self.total_by_type()["TL"]
        if n_tl <= 0:
            self.essay_item_points = []
            return []
        per_q = round(self.part_points["TL"] / n_tl, 4)
        pts = [per_q] * n_tl
        pts[-1] = round(pts[-1] + round(self.part_points["TL"] - sum(pts), 4), 4)
        self.essay_item_points = pts
        return pts

    def set_individual_essay_points(self, points: list[float]) -> None:
        self.essay_item_points = [round(float(p), 4) for p in points]
        self.part_points["TL"] = round(sum(self.essay_item_points), 4)

    def validate_cv7991(self, strict_essay: bool = True) -> list[str]:
        warnings: list[str] = []
        counts = self.total_by_type()
        active_total = sum(self.part_points.get(k, 0.0) for k, c in counts.items() if c > 0)
        if abs(active_total - 10.0) > 1e-3:
            warnings.append(f"Tổng điểm hiện tại là {active_total:.2f} (khác 10,0).")
        if strict_essay and counts["TL"] > 0 and abs(self.part_points.get("TL", 0.0) - 3.0) > 1e-3:
            warnings.append(f"Tự luận hiện có {self.part_points.get('TL', 0.0):.2f} điểm (khung CV 7991 là 3,0).")
        return warnings

    @classmethod
    def from_exam_questions(cls, questions: Iterable[Question], name: str = "Ma tran tu de goc") -> "ExamMatrix":
        counter: Counter[tuple[str, str, str]] = Counter()
        for q in questions:
            info = q.id_info()
            if info:
                pat = f"{info.lop}{info.mon}{info.chuong}?{info.bai}*" if info.bai else f"{info.lop}{info.mon}{info.chuong}*"
                md = info.muc_do
            else:
                pat, md = "*", ""
            counter[(q.qtype, pat, md)] += 1
        order = {"TN": 0, "DS": 1, "KQ": 2, "TL": 3}
        rules = [MatrixRule(qt, cnt, pat, md) for (qt, pat, md), cnt in sorted(counter.items(), key=lambda x: (order.get(x[0][0], 9), x[0][1], x[0][2]))]
        m = cls(name=name, rules=rules)
        if m.total_by_type()["TL"] > 0:
            m.set_essay_total_points(m.part_points["TL"])
        return m

    def save_to_excel(self, xlsx_path: str) -> None:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "MaTran_CV7991"
        ws.append(["Loại câu", "Mẫu ID", "Mức độ", "Số câu", "Vùng trộn", "Đơn vị kiến thức", "Năng lực"])
        for r in self.rules:
            ws.append([r.qtype, r.id_glob, r.muc_do, r.count, r.zone, r.topic, r.competency])
        wb.save(xlsx_path)

    @classmethod
    def load_from_excel(cls, xlsx_path: str, name: str = "Ma tran Excel") -> "ExamMatrix":
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)
        ws = wb.active
        rules: list[MatrixRule] = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not row or not row[0]:
                continue
            cnt = int(row[3]) if len(row) > 3 and row[3] is not None else 0
            if cnt > 0:
                rules.append(MatrixRule(
                    str(row[0]).strip().upper(), cnt,
                    str(row[1]).strip() if len(row) > 1 and row[1] else "*",
                    str(row[2]).strip().upper() if len(row) > 2 and row[2] else "",
                    int(row[4]) if len(row) > 4 and row[4] is not None else 0,
                    str(row[5]).strip() if len(row) > 5 and row[5] else "",
                    str(row[6]).strip() if len(row) > 6 and row[6] else "",
                ))
        m = cls(name=name, rules=rules)
        if m.total_by_type()["TL"] > 0:
            m.set_essay_total_points(m.part_points["TL"])
        return m
