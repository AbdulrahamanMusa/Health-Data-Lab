# MNCH Insight: a DHIS2 dashboard in Shiny for Python + React

A rebuild of the **DHIS2 MNCH Dashboard** Power BI report (`.pbip`) with
[shinyreact](https://pypi.org/project/shinyreact/), plus a page the report doesn't
have: a **facility risk forecast**.

- **Same data, same numbers.** The app sends DHIS2 the same Web API requests as the
  Power BI model's Power Query (analytics by chiefdom and month, population
  denominators, org units, system info), and `mnch/metrics.py` ports every DAX
  measure (coverage, dropout, reporting rate, target shading, the written findings
  and actions). Side by side, every KPI, table and chart matches the report.
- **Different look, on purpose.** Green-ink chrome, teal / rust / violet / gold
  series and Manrope, instead of the report's navy rail, blue and Segoe UI, so the
  two can be compared at a glance. Light and dark themes, works on a phone.
- **Five pages:** Overview, Districts (sortable, searchable chiefdom scorecard),
  Actions, **Risk forecast** (new) and Connection.

## Risk forecast

For each health facility, the chance that next quarter it will have:

| Outcome | Definition |
|---|---|
| Low Penta 3 coverage | Penta 3 coverage below 70% (the scorecard's red band: more than 20 pts under the 90% target) |
| High ANC dropout | ANC 1 to 4 dropout above 50% |

Features come from DHIS2 facility-level analytics (level 4): recent and 6-month
coverage or dropout, reporting completeness, size, and the district's level. The
model is an L2-regularised logistic regression written in numpy, so every risk is
explained as a sum of named factors (shown per facility).

Validation is a time split: fitted on quarters that ended before the test quarter,
then scored on that unseen quarter and compared with the rule "same as last quarter".
On the bundled snapshot (test quarter Jul to Sep 2026):

| Outcome | AUC | "Same as last quarter" | Top 10% that fell behind |
|---|---|---|---|
| Low Penta 3 coverage | 0.82 | 0.79 | 82% (base rate 28%) |
| High ANC dropout | 0.85 | 0.86 | 97% (base rate 64%) |

The coverage model adds signal; the ANC model ranks no better than the latest figure
alone, and the app says so. Its value there is a calibrated probability and the reasons.

## Data

Defaults point at the public DHIS2 play demo (Sierra Leone), as in the `.pbip`:

| Variable | Default |
|---|---|
| `DHIS2_BASE_URL` | `https://play.im.dhis2.org/stable-2-42-6` |
| `DHIS2_USERNAME` / `DHIS2_PASSWORD` | No default. Set as secrets (Render: environment variables) or in a local `.env` file, never in the code |
| `DHIS2_ROOT_ORG_UNIT` | `ImspTQPwCqd` (Sierra Leone) |
| `DHIS2_PERIODS` | `LAST_12_MONTHS` |
| `DHIS2_LIVE_ON_START` | `1`: pull live data when the server starts |

The app starts instantly from `data/snapshot.json.gz` (committed), pulls live data in
the background, and pulls again when anyone presses **Refresh**. Play demo URLs change
with each DHIS2 release; if the default stops working, set `DHIS2_BASE_URL`. For a real
server use a read-only account and keep the password in the host's secret settings.

## Develop

```bash
cp .env.example .env              # then put the DHIS2 user name and password in .env
pip install -r requirements.txt
python -m shiny run app.py
npm install && npm run build      # after changing anything in src/
python -m pytest                  # checks the numbers against the Power BI figures
```

## Documentation and media

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): architecture, data flow, indicators, measures and the risk model, with its validation.
- [docs/DISCLAIMER.md](docs/DISCLAIMER.md): educational-use disclaimer (article and video versions).
- [docs/VIDEO.md](docs/VIDEO.md): the Shiny tour storyboard, the combined LinkedIn film and an optional voice-over script.
- [docs/LINKEDIN_POST.md](docs/LINKEDIN_POST.md): post text for LinkedIn.
- `docs/video/`: scripts that record the tour from the running app and build the LinkedIn film into `media/` (not committed).

