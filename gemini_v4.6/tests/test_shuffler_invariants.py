from collections import Counter
from nganhangde.core.generator import generate_exam_batch, shuffle_variant
from nganhangde.core.parser import parse_tex_questions


def test_balanced_abcd_lock_groups_and_solution_sync():
    blocks = []
    for i in range(12):
        blocks.append(
            f"%[1D1N1-{i+1}]\n\\begin{{ex}}\nCâu TN {i+1}.\n"
            "\\choice{\\True Đáp án đúng}{Sai 1}{Sai 2}{Sai 3}\n"
            "\\loigiai{Suy ra \\textbf{Chọn A}.}\n\\end{ex}"
        )
    # 1 câu khóa trộn (LOCK_RE)
    blocks.append(
        "%[1D1H1-1]\n\\begin{ex}\nCâu khóa trộn.\n"
        "\\choice{A}{B}{\\True Cả A và B đều đúng}{D}\n\\end{ex}"
    )
    # 2 câu chùm
    blocks.append("%[1D1V1-1]%[group:G1]\n\\begin{ex}\nChùm 1.\n\\choice{\\True 1}{2}{3}{4}\n\\end{ex}")
    blocks.append("%[1D1V1-2]%[group:G1]\n\\begin{ex}\nChùm 2.\n\\choice{\\True 1}{2}{3}{4}\n\\end{ex}")
    # 1 câu Đ/S có \itemch
    blocks.append(
        "%[1D2H1-1]\n\\begin{ex}\nCâu ĐS.\n\\choiceTF{\\True M1}{M2}{\\True M3}{M4}\n"
        "\\loigiai{\\begin{itemchoice}\\itemch G1\\itemch G2\\itemch G3\\itemch G4\\end{itemchoice}}\\end{ex}"
    )

    qs = parse_tex_questions("\n\n".join(blocks))
    variants = generate_exam_batch(4, seed=2026, base_questions=qs, code_digits=4, start_code=1001, balance_abcd=True)
    assert [v.code for v in variants] == ["1001", "1002", "1003", "1004"]

    for v in variants:
        unlocked_ans = [ans for q, (_, ans) in zip([x for x in v.questions if x.qtype == "TN"], v.key_tn) if not q.lock_shuffle]
        cnt = Counter(unlocked_ans)
        assert max(cnt.values()) - min(cnt.values()) <= 1

        # Kiểm tra câu chùm G1 luôn đi liền nhau
        g_idx = [i for i, q in enumerate(v.questions) if q.group_id == "G1"]
        assert len(g_idx) == 2 and g_idx[1] - g_idx[0] == 1

        # Kiểm tra câu khóa trộn vẫn giữ vị trí C (index 2)
        locked = [q for q in v.questions if q.lock_shuffle and q.qtype == "TN"][0]
        assert locked.correct[2] is True

        # Kiểm tra đồng bộ chữ cái trong \loigiai của câu TN
        for q, (_, ans) in zip([x for x in v.questions if x.qtype == "TN"], v.key_tn):
            if "Chọn" in q.solution:
                assert f"Chọn {ans}" in q.solution
