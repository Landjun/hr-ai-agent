# 示例产出

这些文件展示系统的真实输出格式，方便在不运行项目的情况下快速了解效果。
均由 [`scripts/generate_examples.py`](../../scripts/generate_examples.py) 在**离线 Mock 模式**下生成（确定性、可复现）。配置真实大模型后，证据与措辞会更丰富。

| 文件 | 内容 |
| --- | --- |
| [ranking_sample.md](ranking_sample.md) | 候选人排序表（医疗AI产品经理岗，3 位候选人） |
| [screening_report_sample.md](screening_report_sample.md) | 头名候选人的分维度初筛报告（含证据/风险/建议面试题） |
| [interview_report_sample.md](interview_report_sample.md) | AI 模拟面试报告（含分维度得分、每题复盘、7 天提升计划） |

重新生成：

```bash
python scripts/generate_examples.py
```
