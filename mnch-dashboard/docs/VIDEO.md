# Video: Shiny tour and the combined LinkedIn film

Two videos, produced from the running applications (no mock-ups):

| File (in `media/`, not committed) | Length | What it is |
|---|---|---|
| `shiny-tour.mp4` | 2:04 | Shiny for Python tour, with title and end cards |
| `dhis2-interoperability-linkedin.mp4` | 3:39 | Intro, Power BI tour (unchanged), Shiny tour, comparison, disclaimer, close |
| `linkedin-thumbnail.png` | | Cover image for the LinkedIn post |

Both are 1920 × 1080, 30 fps, H.264, silent with captions, like the original Power BI tour.
Regenerate with `python docs/video/make_tour.py` (app running on port 8795) and then
`python docs/video/make_linkedin.py`. ffmpeg comes from `pip install imageio-ffmpeg`.

## Harmonised style (taken from the Power BI tour)

| Element | Power BI tour | Shiny tour |
|---|---|---|
| Title and end cards | Navy, blue heart tile, "DHIS2 MNCH Dashboard", "That's the tour" | Same layout in plum with a pink heart tile |
| Caption pill | Navy pill, light-blue section label ("1 · OVERVIEW"), white caption | Same pill in plum, pink section label |
| Spotlight | Page dimmed, blue frame around one visual, gentle zoom | Identical (blue frame, same dimming and zoom) |
| Navigation | Cursor clicks the left menu ("Open Districts") | Same |
| Typeface | Segoe UI | Segoe UI |

Navy always means Power BI and plum always means Shiny, matching each application's sidebar.

## Shiny tour storyboard (captions exactly as shown)

| # | Scene | Caption label | Caption |
|---|---|---|---|
| 0 | Title card | | DHIS2 MNCH Dashboard · Shiny for Python edition · a two-minute tour |
| 1 | Overview, full page | 1 · Overview | Same DHIS2 data and measures as the Power BI report |
| 2 | KPI cards | 1 · Overview | Six indicators against target, each with a 12-month trend |
| 3 | District slicer, then Bo selected | Filters | Filter by district, chiefdom or month: every page follows / District: Bo. The indicators recalculate from the DHIS2 numbers |
| 4 | Hover on the trend chart | 1 · Overview | Hover any chart for the exact values |
| 5 | What needs attention | 1 · Overview | Written findings update with your filters |
| 6 | Penta 3 by district | 1 · Overview | Districts ranked: lowest Penta 3 coverage first |
| 7 | Click Districts | 2 · Districts | Open Districts |
| 8 | Scorecard | 2 · Districts | A scorecard for every chiefdom, shaded against target |
| 9 | Total row | 2 · Districts | A Total row that follows the filters |
| 10 | Missed Penta 3 bars | 2 · Districts | Where most children missed their third Penta dose |
| 11 | Click Actions | 3 · Actions | Open Actions |
| 12 | Recommended actions | 3 · Actions | Recommended actions, with the numbers behind them |
| 13 | Bubble chart | 3 · Actions | Top left needs most help: low coverage and high dropout |
| 14 | Coverage above 100% | 3 · Actions | Coverage above 100%: check the population estimate first |
| 15 | Click Risk forecast | 4 · Risk forecast · new | Which facilities may fall behind next quarter? |
| 16 | Outcome selector | 4 · Risk forecast | Outcome: Penta 3 coverage below 70% in the next 3 months |
| 17 | Summary tiles | 4 · Risk forecast | Risk estimates for the 226 facilities that report Penta doses |
| 18 | Map | 4 · Risk forecast | Each dot is a facility, coloured by its estimated risk |
| 19 | Click the top facility | 4 · Risk forecast | Every estimate comes with the reasons behind it |
| 20 | Switch outcome | 4 · Risk forecast | Second outcome: ANC 1 to 4 dropout above 50% |
| 21 | Model card | 4 · Risk forecast | Tested on an unseen quarter against 'same as last quarter' / A planning aid for follow-up visits, not a verdict |
| 22 | Click Connection, tiles | 5 · Connection | Which DHIS2 server, which version, last refresh |
| 23 | Indicator catalogue | 5 · Connection | The same indicator catalogue as the Power BI model |
| 24 | Sidebar source card | 5 · Connection | Refresh pulls fresh data from DHIS2 on demand |
| 25 | End card | | That's the tour · tools used · educational-use disclaimer |

## Combined LinkedIn film

| Time | Segment | On screen |
|---|---|---|
| 0:00 | Intro card (navy and plum) | From dashboards to risk prediction · DHIS2 interoperability with Power BI and Shiny for Python · One DHIS2 source, two ways to turn routine health data into decisions |
| 0:06 | Part 1 card (navy) | DHIS2 + Power BI · Descriptive analytics: what has happened, and where |
| 0:10 | Power BI tour | The original 70-second tour, unchanged |
| 1:20 | Part 2 card (plum) | DHIS2 + Shiny for Python · The same dashboard, plus risk prediction: where problems may arise next |
| 1:24 | Shiny tour | Scenes 1 to 24 above |
| 3:18 | Comparison card | Power BI: understand what has happened · Shiny for Python: investigate where problems may arise |
| 3:26 | Disclaimer card | Educational-use disclaimer (see DISCLAIMER.md) |
| 3:35 | Close card | Read the full project story: am-datasolution.com/posts/dhis2-interoperability-power-bi-shiny |

## If you want a narrated version

The videos are silent like the original. To add a voice-over, record this script over the
combined film (about 3.5 minutes at a calm pace), then mux it with
`ffmpeg -i film.mp4 -i voice.m4a -c:v copy -c:a aac -shortest out.mp4`.

> **0:00** Routine health data is collected every month in DHIS2. The question is how to turn it into decisions.
> **0:06** First, Power BI. Live from the DHIS2 Web API, it shows antenatal care, immunisation and reporting against targets, by district and chiefdom, with written findings and recommended actions. It answers: what has happened, and where?
> **1:20** Second, the same dashboard rebuilt in Shiny for Python: same queries, same numbers, checked against Power BI. And one new page.
> **2:25** The risk forecast. A logistic regression uses each facility's last six months of DHIS2 data to estimate the chance of low Penta 3 coverage, or high antenatal care dropout, next quarter. Every estimate shows its reasons. It was tested on a quarter it had not seen: for coverage it beat the simple rule "same as last quarter"; for antenatal care it did about as well.
> **3:18** Power BI helps us understand what has happened. Shiny for Python, with a carefully validated model, helps us ask where problems may arise next, and where to look first.
> **3:26** This is a demonstration on DHIS2 demo data, not a validated decision tool.
