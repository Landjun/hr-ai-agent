"""面试提纲 + AI 模拟面试流程的离线测试。"""
from app.services.interview_agent import (ask_next, build_transcript,
                                         finish_mock, start_mock, submit_answer)

JD = "招聘岗位：AI 应用工程师\n要求：精通 Python，掌握 RAG、Agent。"


def test_mock_one_question_at_a_time():
    res = start_mock(jd_text=JD, interview_round="技术面", duration_minutes=15)
    sid = res["session_id"]
    assert res["question"]["index"] == 1
    assert res["max_questions"] == 3

    # 一次只问一个问题：start 后只产生了 1 个面试官问题
    transcript = build_transcript(sid)
    assert transcript == []  # 还没作答

    out = submit_answer(sid, "我用 Python + FastAPI 做过 RAG 系统，准确率提升 30%，难点是召回优化。")
    assert 0 <= out["feedback"]["score"] <= 10
    assert out["answered"] == 1


def test_empty_answer_scores_low_and_followups():
    res = start_mock(jd_text=JD, interview_round="技术面", duration_minutes=30)
    sid = res["session_id"]
    out = submit_answer(sid, "不知道")
    assert out["feedback"]["score"] <= 3
    assert out["feedback"]["move_on"] is False


def test_full_mock_generates_report():
    res = start_mock(jd_text=JD, interview_round="初面", duration_minutes=15)
    sid = res["session_id"]
    finished = False
    guard = 0
    while not finished and guard < 10:
        guard += 1
        out = submit_answer(sid, "我负责过一个 Python RAG 项目，结果是工单下降 45%，复盘后优化了召回。")
        finished = out["should_finish"]
        if not finished:
            ask_next(sid)
    report = finish_mock(sid)
    assert report["final_score"] >= 0
    assert "JD 模拟面试报告" in report["report_markdown"]
