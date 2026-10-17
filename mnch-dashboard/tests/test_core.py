"""Checks against the committed DHIS2 snapshot (pulled 17 Oct 2026, data Oct 2025-Sep 2026).

The reference figures are the ones the Power BI report shows for the same data,
so these tests prove the pandas port of the DAX gives the same numbers.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from mnch import dhis2, metrics, predict

SNAP = dhis2.load(Path(__file__).resolve().parents[1] / "data" / "snapshot.json.gz")


@pytest.fixture(scope="module")
def model():
    return metrics.Model.from_snapshot(SNAP)


@pytest.fixture(scope="module")
def facilities():
    return predict.FacilityData.from_snapshot(SNAP)


def test_headline_kpis_match_power_bi(model):
    k = {x["id"]: x for x in model.overview(metrics.Filters())["kpis"]}
    assert round(k["anc1"]["value"] * 100, 1) == 102.3
    assert round(k["anc4"]["value"] * 100, 1) == 41.2
    assert round(k["ancdrop"]["value"] * 100, 1) == 59.7
    assert round(k["penta3"]["value"] * 100, 1) == 27.6
    assert round(k["pentadrop"]["value"] * 100, 1) == 17.1
    assert round(k["reporting"]["value"] * 100, 1) == 83.3
    assert k["ancdrop"]["note"] == "151,211 women left early"
    assert k["pentadrop"]["note"] == "12,822 children missed dose 3"
    assert k["anc1"]["note"] == "▲ 7.3 pts above 95% target" and k["anc1"]["status"] == "on"
    assert k["reporting"]["status"] == "near" and k["penta3"]["status"] == "far"


def test_findings_actions_and_tables_match_power_bi(model):
    ov = model.overview(metrics.Filters())
    texts = " ".join(f["text"] for f in ov["findings"])
    assert "Kono has the lowest Penta 3 coverage: 11%." in texts
    assert ov["penta3_by_district"][0]["name"] == "Kono"
    acts = " ".join(a["text"] for a in model.actions(metrics.Filters())["actions"])
    assert "Start in Western Area, Bombali, Bo." in acts
    assert "Highest dropout: Tonkolili (81%)." in acts
    assert "8 districts report below the 90% target. Start with Kono." in acts
    assert "56 chiefdoms show coverage above 100%" in acts
    rows = model.districts(metrics.Filters())["rows"]
    assert rows[0]["chiefdom"] == "Freetown" and rows[0]["missed"] == 2548 and round(rows[0]["anc1"] * 100, 1) == 109.4
    by_month = [r["value"] for r in model.connection()["rows_by_month"][:3]]
    assert by_month == [868, 924, 856]


def test_filters_narrow_the_data(model):
    allk = model.overview(metrics.Filters())["kpis"]
    bo = model.overview(metrics.Filters(district="Bo"))["kpis"]
    sep = model.overview(metrics.Filters(district="Bo", month="202609"))
    assert [k["value"] for k in allk] != [k["value"] for k in bo]
    assert len(sep["trend"]) == 1 and sep["trend"][0]["month"] == "202609"
    rows = model.districts(metrics.Filters(district="Bo"))["rows"]
    assert rows and {r["district"] for r in rows} == {"Bo"}
    nothing = model.overview(metrics.Filters(district="Nowhere"))
    assert all(k["value"] is None for k in nothing["kpis"]) and nothing["findings"] == []


def test_shading_follows_the_report_rules(model):
    assert model.shade(0.95, 0.95) == "on" and model.shade(0.80, 0.95) == "near" and model.shade(0.70, 0.95) == "far"
    assert model.dropout_shade(0.11) == "far" and model.dropout_shade(-0.01) == "near" and model.dropout_shade(0.05) == "on"


def test_logistic_regression_learns_a_known_signal():
    rng = np.random.default_rng(0)
    x = pd.DataFrame({"a": rng.normal(size=600), "b": rng.normal(size=600)})
    y = pd.Series((x["a"] * 2 + rng.normal(size=600) > 0).astype(float))
    m = predict.Logistic(l2=1).fit(x, y)
    assert m.w[1] > 1 and abs(m.w[2]) < 0.3
    assert predict.auc(y.to_numpy(), m.predict(x)) > 0.9
    assert predict.auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == 1.0


def test_facility_types():
    assert predict.facility_type("Ngelehun CHC") == "CHC"
    assert predict.facility_type("Kunya MCHP") == "MCHP"
    assert predict.facility_type("Bo Govt. Hospital") == "Hospital"


@pytest.mark.parametrize("outcome", list(predict.OUTCOMES))
def test_risk_model_is_time_split_and_scores_every_eligible_facility(facilities, outcome):
    om = predict.build(facilities, outcome)
    v = om.validation
    months = facilities.months
    # The test window is the last 3 months with known outcomes; training labels end before it.
    assert v["test_window"] == [months[-3], months[-1]]
    assert v["train_rows"] > 500 and v["test_rows"] > 100
    assert 0.6 < v["auc"] <= 1 and 0 < v["base_rate"] < 1
    s = om.scores
    assert len(s) > 100 and s["risk"].between(0, 1).all()
    assert set(s["band"]) <= {"high", "medium", "low"}
    assert s["risk"].is_monotonic_decreasing
    top = s.iloc[0]
    assert top["band"] == "high" and top["drivers"], "the riskiest facility should come with reasons"


def test_scorecard_total_row_matches_power_bi(model):
    t = model.districts(metrics.Filters())["total"]
    assert [round(t[k] * 100, 1) for k in ("anc1", "anc4", "anc_dropout", "penta3", "penta_dropout", "measles", "reporting")] == [102.3, 41.2, 59.7, 27.6, 17.1, 26.3, 83.3]
    assert t["missed"] == 12822
