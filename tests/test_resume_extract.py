"""简历抽取与 JD 解析的离线测试。"""
from app.services.jd_parser import parse_jd
from app.services.resume_extractor import extract_resume

SAMPLE_RESUME = """
姓名：张伟
联系方式：13800001111  zhangwei@example.com
最高学历：硕士
毕业院校：北京航空航天大学
工作年限：6年
专业技能：精通 Python，熟悉 FastAPI、RAG、Agent、LangChain
项目经历：
2022.03 - 2023.06  企业级 RAG 智能客服系统
项目成果：客服工单量下降 45%，准确率提升 30%。
"""

SAMPLE_JD = """
招聘岗位：AI 应用工程师
任职要求：精通 Python，熟悉 FastAPI，掌握 RAG、Agent。本科及以上，3 年经验。
加分项：熟悉 LangChain。
"""


def test_extract_basic_fields():
    data = extract_resume(SAMPLE_RESUME)
    assert data["phone"] == "13800001111"
    assert data["email"] == "zhangwei@example.com"
    assert data["highest_education"] in ("硕士", "研究生")
    assert "python" in [s.lower() for s in data["skills"]]
    assert data["raw_text"]  # 原文保留


def test_extract_no_fabrication():
    # 没有写期望薪资，应为 "无"，不能编造
    data = extract_resume("姓名：王五\n熟悉 Python")
    assert data["expected_salary"] == "无"


def test_jd_parse_skills():
    jd = parse_jd(SAMPLE_JD)
    skills = [s.lower() for s in jd["hard_skills"]]
    assert "python" in skills
    assert "rag" in skills
    assert jd["job_title"]
