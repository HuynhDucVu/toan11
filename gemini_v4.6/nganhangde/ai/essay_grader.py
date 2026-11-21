"""Chấm bài tự luận hỗ trợ AI theo thang điểm từng bước."""
from pydantic import BaseModel
from .providers import AIConfig, AIProviderClient


class EssayGradeReport(BaseModel):
    suggested_score: float
    max_score: float
    step_feedback: list[str]
    summary_comment: str


def grade_essay_with_ai(
    question_tex: str,
    rubric_tex: str,
    student_work: str,
    max_score: float,
    ai_config: AIConfig,
) -> EssayGradeReport:
    client = AIProviderClient(ai_config)
    prompt = (
        f"Bạn là giáo viên Toán THPT chấm bài tự luận (thang tối đa {max_score} điểm).\n"
        f"Đề bài:\n{question_tex}\n\n"
        f"Hướng dẫn chấm / Thang điểm:\n{rubric_tex}\n\n"
        f"Bài làm học sinh:\n{student_work}\n\n"
        "Hãy chấm điểm chi tiết từng bước, chỉ rõ lỗi sai (nếu có) và đề xuất điểm số công bằng."
    )
    res = client.generate_structured(prompt, EssayGradeReport)
    if res.parsed is None:
        raise RuntimeError("AI không trả về dữ liệu chấm điểm hợp lệ.")
    return res.parsed
