import openpyxl
from nganhangde.core.generator import shuffle_variant
from nganhangde.core.matrix_cv7991 import ExamMatrix, MatrixRule
from nganhangde.core.parser import parse_tex_questions
from nganhangde.core.review import validate_cv1239_shortans
from nganhangde.exporters.omr_excel import check_omr_capacity, export_answer_csv_bom, export_omr_excel
from nganhangde.exporters.online_gas import grade_online_submission
from nganhangde.exporters.spec_docx_xlsx import export_cv7991_excel


def test_cv7991_points_and_spec_excel(tmp_path):
    mat = ExamMatrix(
        name="GK1 Toán 11",
        rules=[
            MatrixRule("TN", 12, "1D1*", "N", topic="Lượng giác | Hàm số lượng giác"),
            MatrixRule("DS", 2, "1D2*", "H", topic="Dãy số | Cấp số cộng"),
            MatrixRule("KQ", 4, "1H4*", "V", topic="Không gian | Song song"),
            MatrixRule("TL", 3, "1D2*", "V", topic="Dãy số | Cấp số nhân"),
        ],
    )
    assert mat.validate_cv7991() == []
    out_xlsx = tmp_path / "cv7991.xlsx"
    export_cv7991_excel(mat, str(out_xlsx))
    wb = openpyxl.load_workbook(out_xlsx)
    assert wb.sheetnames == ["PhuLuc1_MaTran", "PhuLuc2_BanDacTa"]
    ws1 = wb["PhuLuc1_MaTran"]
    assert ws1.cell(ws1.max_row - 1, 19).value == 10.0


def test_cv1239_shortans_and_omr_capacity(tmp_path):
    assert validate_cv1239_shortans("$-1{,}5$") == []
    assert any(i.code == "KQ_TOO_LONG" for i in validate_cv1239_shortans("-12,5"))
    assert any(i.code == "KQ_DOT_DECIMAL" for i in validate_cv1239_shortans("2.5"))
    assert any(i.code == "KQ_INVALID_CHAR" for i in validate_cv1239_shortans("3cm"))

    # Tạo 5 câu DS -> phải cảnh báo khi xuất phiếu QM2025_TOAN_12_4_6 (tối đa 4 câu DS)
    ds_tex = "\n".join(
        f"%[1D1H1-{i}]\n\\begin{{ex}}DS {i}\\choiceTF{{\\True a}}{{b}}{{c}}{{d}}\\end{{ex}}" for i in range(5)
    )
    v = shuffle_variant(parse_tex_questions(ds_tex), "1001", seed=1, shuffle_q=False, shuffle_opt=False)
    warns = check_omr_capacity(v, "QM2025_TOAN_12_4_6")
    assert len(warns) == 1 and "Phần II" in warns[0]

    csv_p = tmp_path / "da.csv"
    export_answer_csv_bom([v], str(csv_p))
    assert csv_p.read_bytes().startswith(b"\xef\xbb\xbf")

    # Kiểm thử thang điểm phi tuyến Phần II (3/4 ý đúng = 0.5 điểm)
    res = grade_online_submission(v, {"P2_1": "ĐSSS", "P2_2": "ĐSSĐ", "P2_3": "ĐSĐĐ", "P2_4": "SSĐĐ", "P2_5": "SSSS"})
    assert res.score_p2 == round(1.0 + 0.5 + 0.25 + 0.1 + 0.5, 2)
