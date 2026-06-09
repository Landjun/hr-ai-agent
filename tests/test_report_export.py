"""报告导出（HTML / PDF）离线测试。"""
from app.services.report_exporter import (
    markdown_to_html,
    markdown_to_pdf_bytes,
    title_from_markdown,
)

SAMPLE_MD = """# 候选人初筛报告

## 1. 基本信息
- 姓名：王医
- 学历：硕士

## 2. 分维度评分

| 维度 | 得分 | 满分 |
| --- | --- | --- |
| 医疗行业理解 | 19 | 20 |
| AI产品能力 | 23 | 25 |

**总分：92 / 100**

> 仅供 HR 辅助参考，最终由人工确认。
"""


def test_title_extraction():
    assert title_from_markdown(SAMPLE_MD) == "候选人初筛报告"


def test_html_export_contains_table_and_chinese():
    html = markdown_to_html(SAMPLE_MD, "测试")
    assert "<table>" in html
    assert "医疗行业理解" in html
    assert html.strip().startswith("<!doctype html>")


def test_pdf_export_is_valid_pdf():
    pdf = markdown_to_pdf_bytes(SAMPLE_MD, "测试")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000


def test_docx_export_is_valid():
    from app.services.report_exporter import markdown_to_docx_bytes
    data = markdown_to_docx_bytes(SAMPLE_MD, "测试")
    assert data[:2] == b"PK"  # docx 是 zip 容器
    assert len(data) > 1000


def test_job_package_zip_contains_reports():
    import io
    import zipfile

    from app.database import session_scope
    from app.models import Job, Resume
    from app.services.report_generator import export_job_package
    from app.services.screening_agent import screen

    with session_scope() as s:
        job = Job(job_title="通用", jd_text="x", hard_skills=["python"], keywords=["python"])
        r1 = Resume(candidate_name="甲", raw_text="熟悉 Python",
                    structured_json={"name": "甲", "skills": ["python"], "raw_text": "熟悉 Python"})
        r2 = Resume(candidate_name="乙", raw_text="熟悉 Java",
                    structured_json={"name": "乙", "skills": ["java"], "raw_text": "熟悉 Java"})
        s.add(job)
        s.add(r1)
        s.add(r2)
        s.flush()
        jid, r1id, r2id = job.id, r1.id, r2.id
    screen(jid, r1id)
    screen(jid, r2id)

    data = export_job_package(jid, "pdf")
    assert data[:2] == b"PK"  # zip magic
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        names = z.namelist()
    assert any("排序表" in n for n in names)
    assert sum(n.startswith("reports/") for n in names) == 2
