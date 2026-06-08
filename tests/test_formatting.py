"""JD / 简历 文本格式化的离线测试。"""
from app.utils.formatting import format_jd, format_resume


def test_format_jd_sections():
    jd = {
        "job_title": "医疗AI产品经理",
        "must_have_requirements": ["5年产品经验", "懂医疗业务"],
        "nice_to_have_requirements": ["医学背景"],
        "hard_skills": ["PRD", "竞品分析"],
    }
    text = format_jd(jd)
    assert "岗位名称：医疗AI产品经理" in text
    assert "【必备要求】" in text and "5年产品经验" in text
    assert "【加分项】" in text
    assert "PRD" in text
    # 不再是 Python 字典原文
    assert "{'" not in text


def test_format_resume_includes_projects_and_raw():
    resume = {
        "name": "王医", "highest_education": "硕士", "skills": ["RAG", "PRD"],
        "project_experiences": [
            {"project_name": "影像辅助诊断", "role": "产品负责人",
             "description": "0到1落地", "achievements": ["营收+2000万"], "tech_stack": ["大模型"]},
        ],
        "raw_text": "完整简历原文……",
    }
    text = format_resume(resume)
    assert "姓名：王医" in text
    assert "影像辅助诊断" in text
    assert "营收+2000万" in text
    assert "简历原文（节选" in text


def test_format_resume_skips_missing_fields():
    text = format_resume({"name": "甲", "expected_salary": "无", "raw_text": ""})
    assert "姓名：甲" in text
    assert "期望薪资" not in text  # 值为“无”不应出现
