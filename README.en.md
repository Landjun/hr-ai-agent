# HR AI Agent

[![CI](https://github.com/Landjun/hr-ai-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Landjun/hr-ai-agent/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

📖 中文版： [README.md](README.md)

> An AI productivity system for **recruiters / hiring managers / interviewers**.
> It reads the JD and resumes, extracts structured data, scores candidates **with evidence**,
> generates screening conclusions and interview guides, and can even act as an **AI interviewer**
> that mock-interviews you and produces an improvement report.
>
> Core principle: **AI only assists — it never makes the final hiring decision; every judgment must be evidence-backed and traceable.**

## ✨ Highlights

- **Runs with zero config** — no API key needed; it falls back to an offline keyword-heuristic mock so the whole pipeline still works for demos.
- **Evidence-based scoring** — 7 weighted dimensions, each returning `score / evidence / risk / reason`.
- **Role-adaptive rules** — scoring rulesets are matched by job role (any "...Product Manager" JD uses PM dimensions); add a new role by dropping a JSON file.
- **Resilient** — real-LLM errors (insufficient balance / auth / timeout) auto-degrade to offline with a circuit breaker; the UI never crashes.
- **Concurrent** — batch resume screening runs in parallel (10 resumes: ~4 min → ~30 s).
- **Two agents** — resume screening + AI interviewing (interviewer guide & one-question-at-a-time mock interview).
- **Integration-ready** — hooks reserved for Feishu Bitable / Coze / WeCom.

## Example output (viewable on GitHub, no run needed)

- [Candidate ranking](docs/examples/ranking_sample.md)
- [Per-candidate screening report](docs/examples/screening_report_sample.md)
- [AI mock-interview report](docs/examples/interview_report_sample.md)

## Tech stack

Python 3.10+ · FastAPI · Streamlit · SQLite · SQLModel · Pydantic ·
python-docx / pdfplumber / pypdf · pandas / openpyxl · OpenAI-compatible SDK (DeepSeek / Qwen / OpenAI) · pytest

## Quick start

```bash
pip install -r requirements.txt
# optional: cp .env.example .env  and set LLM_API_KEY for a real model
streamlit run web/streamlit_app.py        # demo UI (calls services directly)
# or
python run.py                             # REST API at http://127.0.0.1:8000/docs
pytest -q                                 # tests (offline, no key needed)
```

Without an API key the system runs in **offline mock mode** (keyword heuristics).
Set `LLM_API_KEY` in `.env` to switch to a real OpenAI-compatible model.

## How it works

1. **JD parsing** → structured fields (must-have / nice-to-have / hard skills / keywords).
2. **Resume extraction** → contact, education, skills, work & project experience (missing fields are kept as "无", never fabricated).
3. **Scoring** → per-dimension score with evidence & risk (weighted-indicator matching).
4. **Conclusion** → total, level, strengths, risks, gaps, suggested interview questions, manual-review flag.
5. **Ranking & reports** → ranked table + Markdown/Excel/JSON export.
6. **Interview** → interviewer guide (mode A) or one-question-at-a-time AI mock interview (mode B) with a final report.

See [docs/](docs/) for the case study, workflow, DB schema, and prompt design.

## Safety boundaries

- AI assists only; the final hiring decision stays with humans.
- Must provide evidence — never a score without justification; capabilities without evidence are not assumed.
- No negative judgment based on gender, marital/child status, ethnicity, religion, or health.
- Age / education / years of experience count only when the JD explicitly requires them.
- Low-confidence judgments are flagged for manual review; every score is explainable and traceable.

## License

MIT — see [LICENSE](LICENSE).
