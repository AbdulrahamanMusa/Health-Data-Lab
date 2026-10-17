"""DHIS2 MNCH dashboard, rebuilt in Shiny for Python + shinyreact.

A replica of the "DHIS2 MNCH Dashboard" Power BI report (same DHIS2 queries,
same measures, same numbers) plus a facility risk forecast the .pbip doesn't
have. Python does the data work (metrics.py is the DAX, ported); the UI is a
React client in src/ (built to www/ui.js).
"""

import asyncio

from shiny import reactive
from shiny.express import input, session
from shinyreact import reactive_output, send_message, set_react_page

from mnch import metrics, predict
from mnch.store import STORE

set_react_page()

PAGES = {"overview", "districts", "actions", "risk", "connection"}


@reactive.poll(lambda: (STORE.version, STORE.refreshing), interval_secs=1.5)
def state():
    return STORE.state


async def toast(title, text="", level="ok"):
    await send_message(session, "toast", {"title": title, "text": text, "level": level})


def _filters() -> metrics.Filters:
    return metrics.Filters.parse(input.filters() if "filters" in input else None)


@reactive_output
def meta():
    st = state()
    m = st.model
    src = m.source
    return {
        "source": {
            "host": src.get("host"),
            "server": src.get("server"),
            "version": src.get("version"),
            "data_to": metrics.month_label(m.values["pe"].max(), long=True) if len(m.values) else None,
            "refreshed_at": src.get("refreshed_at"),
            "live": bool(src.get("live")),
            "refreshing": STORE.refreshing,
            "error": STORE.last_error,
        },
        "districts": sorted(m.org["district"].dropna().unique().tolist()),
        "chiefdoms": [{"id": r.ou, "name": r.chiefdom, "district": r.district} for r in m.org.itertuples()],
        "months": [{"id": pe, "label": metrics.month_label(pe, long=True)} for pe in m.months],
        "outcomes": [{"id": k, **{x: v[x] for x in ("label", "short", "question", "definition", "threshold")}} for k, v in predict.OUTCOMES.items()],
        "version": st.version,
    }


@reactive_output
def view():
    st = state()
    page = input.page() if "page" in input else "overview"
    page = page if page in PAGES else "overview"
    f = _filters()
    m = st.model
    if page == "overview":
        return {"page": page, **m.overview(f)}
    if page == "districts":
        return {"page": page, **m.districts(f)}
    if page == "actions":
        return {"page": page, **m.actions(f)}
    if page == "connection":
        return {"page": page, **m.connection()}
    return {"page": page, **_risk(st, f)}


def _risk(st, f: metrics.Filters) -> dict:
    outcome = input.outcome() if "outcome" in input else "low_penta3"
    outcome = outcome if outcome in predict.OUTCOMES else "low_penta3"
    om = st.risk[outcome]
    s = om.scores
    if f.district:
        s = s[s["district"] == f.district]
    if f.chiefdom:
        name = st.model.org.set_index("ou")["chiefdom"].get(f.chiefdom)
        s = s[s["chiefdom"] == name]
    v = om.validation
    rows = s.to_dict("records")
    for r in rows:  # JSON has no NaN
        for k in ("lat", "lon", "now", "reporting"):
            if r[k] is not None and r[k] != r[k]:
                r[k] = None
    return {
        "outcome": outcome,
        "definition": predict.OUTCOMES[outcome],
        "scored_on": [metrics.month_label(x, long=True) for x in v["scored_on"]],
        "summary": {
            "scored": len(rows),
            "high": int((s["band"] == "high").sum()),
            "medium": int((s["band"] == "medium").sum()),
            "expected": float(s["risk"].sum()) if len(s) else 0.0,
        },
        "validation": {
            **{k: v[k] for k in ("train_rows", "test_rows", "base_rate", "auc", "baseline_auc", "brier", "accuracy", "baseline_accuracy", "top10_precision", "top10_n", "calibration", "final_rows")},
            "test_window": [metrics.month_label(x, long=True) for x in v["test_window"]],
            "coefficients": v["coefficients"],
        },
        "facilities": rows,
        "map": st.districts,
    }


@reactive.extended_task
async def run_refresh():
    return await asyncio.to_thread(STORE.refresh)


@reactive.effect
@reactive.event(input.refresh)
def _refresh():
    if not input.refresh():
        return
    if STORE.refreshing or run_refresh.status() == "running":
        return
    run_refresh()


@reactive.effect
async def _refresh_done():
    if run_refresh.status() != "success":
        return
    ok, message = run_refresh.result()
    await toast("Data refreshed" if ok else "Refresh failed", message, "ok" if ok else "warn")
