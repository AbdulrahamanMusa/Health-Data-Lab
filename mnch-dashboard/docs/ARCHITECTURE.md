# DHIS2 interoperability: architecture, data flow and risk model

One DHIS2 source feeds two applications:

1. **DHIS2 + Power BI**: the *DHIS2 MNCH Dashboard* report (`PowerBI_NCD_DHIS2/DHIS2 Demo/*.pbip`).
   Descriptive analytics: what has happened, and where.
2. **DHIS2 + Shiny for Python**: *MNCH Insight* (this folder). The same four report pages,
   rebuilt in Python and React, plus a facility **risk forecast** (logistic regression).

Both read the public DHIS2 play server (`https://play.im.dhis2.org/stable-2-42-6`, DHIS2 2.42.6,
Sierra Leone demo database, org unit `ImspTQPwCqd`, period `LAST_12_MONTHS`).
Everything here is for education and demonstration; see [DISCLAIMER.md](DISCLAIMER.md).

```
                         DHIS2 Web API (HTTPS, basic auth: public demo account)
              api/analytics · api/organisationUnits · api/system/info
                    │                                         │
     Power Query (M): DHIS2Get, AnalyticsTable     Python httpx client: mnch/dhis2.py
     chiefdoms (level 3)                           chiefdoms (level 3) + facilities (level 4)
                    │                                         │                 │
     Semantic model + DAX measures                 pandas port of the DAX     numpy logistic
     (Rate, dropout, shading, findings)            (mnch/metrics.py)          regression
                    │                                         │                (mnch/predict.py)
     Power BI report: Overview · Districts ·       Shiny for Python server (app.py) → JSON outputs
     Actions · Connection                          React + TypeScript UI via shinyreact (src/)
                                                   Overview · Districts · Actions · Risk forecast · Connection
```

## 1. Data access

| | Power BI | Shiny for Python |
|---|---|---|
| Client | Power Query `Web.Contents` in one function, `DHIS2Get` | `httpx` in `mnch/dhis2.py` |
| Settings | Parameters `DHIS2_BaseUrl`, `DHIS2_Username`, `DHIS2_Password`, `DHIS2_RootOrgUnit`, `DHIS2_Periods` | Environment variables `DHIS2_BASE_URL`, `DHIS2_USERNAME`, `DHIS2_PASSWORD`, `DHIS2_ROOT_ORG_UNIT`, `DHIS2_PERIODS` |
| Indicator values | `api/analytics.json`, `dx` = catalogue, `pe` = LAST_12_MONTHS, `ou` = root;LEVEL-3, `includeNumDen=true` | Same request at LEVEL-3, plus the same at LEVEL-4 (facilities) |
| Denominators | Same endpoint for the two population data elements | Same, at LEVEL-3 and LEVEL-4 |
| Org units | `api/organisationUnits` (level 3, with district) | Levels 2 (district boundaries for the map), 3 and 4 (with coordinates) |
| Refresh | Power BI refresh (service: anonymous source with its own auth header, no gateway needed) | On start-up in the background, and on demand with **Refresh data**; starts instantly from `data/snapshot.json.gz` |

A live pull takes about 10 to 30 seconds and returns 12,542 chiefdom values, 3,648 chiefdom
population rows, 55,840 facility values and 24,768 facility population rows (pull of 17 Oct 2026).

## 2. Indicator catalogue (identical in both applications)

| Code | Indicator | DHIS2 ID | Denominator | Target (illustrative) |
|---|---|---|---|---|
| ANC1 | ANC 1 coverage | `Uvn6LCg7dVU` | Expected pregnancies (`h0xKKjijTdI`) | 95% |
| ANC4 | ANC 4 coverage | `AUqdhY4mpvp` | Expected pregnancies | 80% |
| BCG | BCG coverage <1y | `FnYCr2EAzWS` | Population under 1 (`DTVRnCGamkV`) | 90% |
| PENTA1 | Penta 1 coverage <1y | `i7WSgSJpnfu` | Population under 1 | 90% |
| PENTA3 | Penta 3 coverage <1y | `tUIlpyeeX9N` | Population under 1 | 90% |
| MEASLES | Measles coverage <1y | `FbKK4ofIv5R` | Population under 1 | 90% |
| RR_RH | Reproductive health reporting rate | `QX4ZTUbOt3a.REPORTING_RATE` | Expected reports | 90% |
| RR_CH | Child health reporting rate | `BfMAe6Itzgt.REPORTING_RATE` | Expected reports | 90% |

## 3. Measures (DAX in Power BI, pandas in Shiny)

- **Coverage** = numerator ÷ annualised target population, where the monthly target is
  annual population × days in month ÷ 365 (as DHIS2 annualises coverage).
- **Reporting rate** = reports received ÷ reports expected.
- **ANC dropout** = (ANC 1 visits − ANC 4 visits) ÷ ANC 1 visits.
- **Penta dropout** = (Penta 1 doses − Penta 3 doses) ÷ Penta 1 doses (WHO flags > 10%).
- **Shading**: at or above target; within 20 points; more than 20 points below.
- **Findings and recommended actions**: rule-based text from those measures (not from the model).

`mnch/metrics.py` ports each DAX measure. `tests/test_core.py` checks that the Shiny app
reproduces the Power BI figures for the same data: ANC 1 102.3%, ANC 4 41.2%, ANC dropout
59.7% (151,211 women), Penta 3 27.6%, Penta dropout 17.1% (12,822 children), reporting 83.3%,
and the scorecard Total row.

## 4. Risk forecast (Shiny only)

**Question.** For each health facility, how likely is it that next quarter it will have:

| Outcome | Definition | Facilities scored |
|---|---|---|
| Low Penta 3 coverage | Penta 3 coverage < 70% over the next 3 months (more than 20 pts under the 90% target, the scorecard's red band) | 226: only facilities that report Penta doses |
| High ANC dropout | ANC 1 to 4 dropout > 50% over the next 3 months | 990: facilities with 10+ ANC 1 visits in the last quarter |

**Inputs** (facility-level DHIS2 analytics; `mnch/predict.py`):

- Low Penta 3: Penta 3 coverage (last 3 and 6 months), Penta 1 to 3 dropout, reporting rate,
  population under 1 (log), district Penta 3 coverage.
- High ANC dropout: ANC dropout (last 3 and 6 months), ANC 1 coverage, ANC 1 visits (log),
  population under 1 (log), district ANC dropout, reporting rate.

**Model.** L2-regularised logistic regression (λ = 10) on standardised features, fitted with
Newton's method in numpy. Missing values are replaced by the training median. The output is a
**probability** of the outcome; bands are High ≥ 60%, Medium 35 to 60%, Low < 35%.
Each facility's "reasons" are the features that push its log-odds up most compared with an
average facility (coefficient × standardised value). Trend and facility-type features were
tested and dropped because they did not improve the time-split test.

**Validation (time split, never random).** Training examples are facility-quarters whose
outcome window ends before the test quarter. Test quarter: Jul to Sep 2026, scored from data up
to Jun 2026, on facilities the model had not seen in that quarter. Baseline: "same as last quarter".
Results on the committed snapshot (pulled 17 Oct 2026):

| | Low Penta 3 coverage | High ANC dropout |
|---|---|---|
| Training facility-quarters | 877 | 3,736 |
| Test facilities | 225 | 971 |
| Base rate in test quarter | 28% | 64% |
| AUC, model | 0.82 | 0.85 |
| AUC, "same as last quarter" | 0.79 | 0.86 |
| Correct calls, model / baseline | 78% / 72% | 76% / 79% |
| Brier score | 0.155 | 0.159 |
| Top 10% riskiest that did fall behind | 82% (18 of 22) | 97% (94 of 97) |

The coverage model adds signal beyond the latest figure. The ANC model ranks no better than the
latest figure alone; its contribution is a probability and the reasons. Calibration is imperfect
(for ANC, facilities predicted around 50% fell behind about 30% of the time). The live forecast
is refitted on all quarters with a known outcome (1,546 and 6,644 facility-quarters) and scores
Jul to Sep 2026 data to estimate risk for Oct to Dec 2026.

**Three kinds of output, kept separate in the app:**

1. *Observed data*: DHIS2 values and the measures computed from them (Overview, Districts, Actions).
2. *Model estimates*: risk probabilities, bands and reasons (Risk forecast page only).
3. *Suggested follow-up*: the rule-based recommended actions, and the idea that high-risk
   facilities are candidates for a closer look. The model does not recommend actions.

## 5. Known limitations

- Demo data: values such as 629.9% ANC 1 coverage show unrealistic population estimates.
  The ANC model even treats ANC 1 coverage above 100% as a risk signal, because those facilities
  had higher dropout in past quarters: a data artefact, not a cause.
- One year of data gives only four training quarters; results can change from one pull to the next.
- Facility values do not add up exactly to chiefdom totals (some data is entered on chiefdom org units).
- One test quarter is not a validation study. Real use would need external validation over
  several periods, monitoring for drift, governance, and interpretation by programme staff.

## 6. Running and regenerating

```bash
pip install -r requirements.txt && python -m shiny run app.py   # app
python -m pytest                                                # figures vs Power BI, model checks
python docs/video/make_tour.py                                  # Shiny tour video (media/)
python docs/video/make_linkedin.py                              # combined LinkedIn film (media/)
```
