# Health Data Lab

One health-data management problem, one working tool, every week.
Each folder is a self-contained app (Shiny for Python + React via shinyreact)
that shows *why* a data management practice matters for decisions, with a
synthetic dataset you can explore and room to try your own.

| Week | App | Practice | Live |
|---|---|---|---|
| 1 | [Raw → Ready](week01-raw-to-ready/) | Never overwrite raw data: the cleaning log | see the blog post |
| — | [Histopathology Screener](histo-screener/) | AI-assisted slide screening for research and education (Claude + Gemini) | see the blog post |

All bundled data is synthetic. Do not upload identifiable health data to a
public deployment without your organisation's approval (Nigeria Data
Protection Act 2023).

## Deploy on Render

`render.yaml` defines one web service per week. In Render choose
**New → Blueprint**, connect this repository and apply. Each service builds
from its own folder (`rootDir`), installs `requirements.txt` and runs
`shiny run app.py --host 0.0.0.0 --port $PORT`.

## Run locally

```bash
cd week01-raw-to-ready
pip install -r requirements.txt
python -m shiny run app.py
```
