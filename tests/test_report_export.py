"""报告导出（HTML / PDF）离线测试。"""
from app.services.report_exporter import (markdown_to_html, markdown_to_pdf_bytes,
                                         title_from_markdown)

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
