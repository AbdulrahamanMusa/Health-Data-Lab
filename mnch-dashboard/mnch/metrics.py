"""The Power BI semantic model, ported from DAX to pandas.

Every measure keeps the .pbip's definition, so a figure here matches the same
figure in the Power BI report for the same slicer selection:

  Rate        = numerator / annualised population (coverage), or
                reports received / expected (reporting rates)
  Dropout %   = (first contact - last contact) / first contact
  Shading     = at or above target / within 20 pts / more than 20 pts below
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
COVERAGE = ["ANC1", "ANC4", "BCG", "PENTA1", "PENTA3", "MEASLES"]
REPORTING = ["RR_RH", "RR_CH"]


def month_label(pe: str, long: bool = False) -> str:
    y, m = int(pe[:4]), int(pe[4:])
    return f"{MONTH_ABBR[m - 1]} {y if long else str(y)[2:]}"


def pct(x: float | None, digits: int = 0) -> str:
    return "–" if x is None else f"{x * 100:.{digits}f}%"


def num(x: float | None) -> str:
    return "–" if x is None else f"{x:,.0f}"


def _clean(x) -> float | None:
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(x) or np.isinf(x) else x


def _div(a, b) -> float | None:
    a, b = _clean(a), _clean(b)
    return None if a is None or not b else a / b


@dataclass
class Filters:
    district: str | None = None
    chiefdom: str | None = None  # chiefdom org unit id
    month: str | None = None  # "YYYYMM"

    @classmethod
    def parse(cls, d: dict | None) -> "Filters":
        d = d or {}
        clean = lambda v: v if isinstance(v, str) and v and v != "All" else None  # noqa: E731
        return cls(clean(d.get("district")), clean(d.get("chiefdom")), clean(d.get("month")))


@dataclass
class Model:
    """The semantic model: dimension tables plus the two fact tables, as DataFrames."""

    catalogue: pd.DataFrame
    org: pd.DataFrame  # chiefdom id, name, district
    values: pd.DataFrame  # ou, pe, code, numerator, denominator
    pop: pd.DataFrame  # ou, pe, dx, population, target
    source: dict
    months: list[str] = field(default_factory=list)

    @classmethod
    def from_snapshot(cls, snap: dict) -> "Model":
        cat = pd.DataFrame(snap["catalogue"])
        code = dict(zip(cat["id"], cat["code"]))
        org = pd.DataFrame(snap["chiefdoms"]).rename(columns={"id": "ou", "name": "chiefdom"}).sort_values(["district", "chiefdom"])
        v = pd.DataFrame(snap["values"])
        v["code"] = v["dx"].map(code)
        v = v.dropna(subset=["code"])[["ou", "pe", "code", "value", "numerator", "denominator"]]
        p = pd.DataFrame(snap["populations"]).rename(columns={"value": "population"})
        days = p["pe"].map(lambda pe: calendar.monthrange(int(pe[:4]), int(pe[4:]))[1])
        p["target"] = p["population"] * days / 365  # as DHIS2 annualises coverage
        p = p[["ou", "pe", "dx", "population", "target"]]
        months = sorted(set(v["pe"]) | set(p["pe"]))
        return cls(cat, org, v, p, snap["source"], months)

    # ------------------------------------------------------------- filtering

    def _units(self, f: Filters) -> pd.DataFrame:
        o = self.org
        if f.district:
            o = o[o["district"] == f.district]
        if f.chiefdom:
            o = o[o["ou"] == f.chiefdom]
        return o

    def select(self, f: Filters, ignore_month: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
        ous = set(self._units(f)["ou"])
        v = self.values[self.values["ou"].isin(ous)]
        p = self.pop[self.pop["ou"].isin(ous)]
        if f.month and not ignore_month:
            v, p = v[v["pe"] == f.month], p[p["pe"] == f.month]
        return v, p

    # ------------------------------------------------------------- measures

    def _den_id(self, code: str) -> str:
        return self.catalogue.set_index("code").at[code, "denominator_id"]

    def target(self, code: str) -> float:
        return float(self.catalogue.set_index("code").at[code, "target"])

    def measures(self, v: pd.DataFrame, p: pd.DataFrame) -> dict:
        """All headline measures for one filter context (one row of DAX evaluation)."""
        n = v.groupby("code")["numerator"].sum(min_count=1)
        d = v.groupby("code")["denominator"].sum(min_count=1)
        t = p.groupby("dx")["target"].sum(min_count=1)
        has = lambda c: c in n.index and not pd.isna(n[c])  # noqa: E731
        N = lambda c: float(n[c]) if has(c) else None  # noqa: E731
        m = {}
        for c in COVERAGE:
            m[c] = _div(N(c), t.get(self._den_id(c))) if has(c) else None
        for c in REPORTING:
            m[c] = _div(N(c), d.get(c)) if has(c) else None
        rr_n = sum(N(c) or 0 for c in REPORTING)
        rr_d = sum(_clean(d.get(c)) or 0 for c in REPORTING)
        m["REPORTING"] = _div(rr_n, rr_d) if any(has(c) for c in REPORTING) else None
        a1, a4, p1, p3 = N("ANC1"), N("ANC4"), N("PENTA1"), N("PENTA3")
        m["anc1_visits"], m["anc4_visits"], m["penta1_doses"], m["penta3_doses"] = a1, a4, p1, p3
        m["anc_drop_women"] = None if a1 is None else a1 - (a4 or 0)
        m["anc_dropout"] = _div(m["anc_drop_women"], a1)
        m["penta_drop_children"] = None if p1 is None else p1 - (p3 or 0)
        m["penta_dropout"] = _div(m["penta_drop_children"], p1)
        return m

    def by(self, v: pd.DataFrame, p: pd.DataFrame, key: str) -> pd.DataFrame:
        """Measures for each value of key ('district', 'ou' or 'pe'): DAX evaluated per row."""
        if key == "pe":
            groups_v, groups_p = v.groupby("pe"), p.groupby("pe")
        else:
            look = self.org.set_index("ou")[key] if key != "ou" else None
            vk = v.assign(k=v["ou"].map(look) if look is not None else v["ou"])
            pk = p.assign(k=p["ou"].map(look) if look is not None else p["ou"])
            groups_v, groups_p = vk.groupby("k"), pk.groupby("k")
        empty_p = p.iloc[0:0]
        rows = []
        pmap = {k: g for k, g in groups_p}
        for k, g in groups_v:
            rows.append({"key": k, **self.measures(g, pmap.get(k, empty_p))})
        return pd.DataFrame(rows)

    # ------------------------------------------------------------- shading and notes

    @staticmethod
    def shade(value: float | None, target: float) -> str | None:
        if value is None:
            return None
        return "on" if value >= target else "far" if value < target - 0.2 else "near"

    @staticmethod
    def dropout_shade(value: float | None) -> str | None:
        if value is None:
            return None
        return "far" if value > 0.1 else "near" if value < 0 else "on"

    def note(self, value: float | None, code: str) -> str:
        if value is None:
            return "No data in selection"
        tgt = self.target(code)
        gap = (value - tgt) * 100
        return (f"▲ {gap:.1f} pts above " if gap >= 0 else f"▼ {-gap:.1f} pts below ") + f"{tgt:.0%} target"

    # ------------------------------------------------------------- pages

    def overview(self, f: Filters) -> dict:
        v, p = self.select(f)
        m = self.measures(v, p)
        rr_target = self.target("RR_RH")
        kpis = [
            {"id": "anc1", "label": "ANC 1 coverage", "value": m["ANC1"], "note": self.note(m["ANC1"], "ANC1"), "status": self.shade(m["ANC1"], self.target("ANC1")), "icon": "heart"},
            {"id": "anc4", "label": "ANC 4 coverage", "value": m["ANC4"], "note": self.note(m["ANC4"], "ANC4"), "status": self.shade(m["ANC4"], self.target("ANC4")), "icon": "calendar"},
            {"id": "ancdrop", "label": "ANC 1 to 4 dropout", "value": m["anc_dropout"], "note": f"{num(m['anc_drop_women'] or 0)} women left early", "status": self.dropout_shade(m["anc_dropout"]), "icon": "userx"},
            {"id": "penta3", "label": "Penta 3 coverage", "value": m["PENTA3"], "note": self.note(m["PENTA3"], "PENTA3"), "status": self.shade(m["PENTA3"], self.target("PENTA3")), "icon": "syringe"},
            {"id": "pentadrop", "label": "Penta 1 to 3 dropout", "value": m["penta_dropout"], "note": f"{num(m['penta_drop_children'] or 0)} children missed dose 3", "status": self.dropout_shade(m["penta_dropout"]), "icon": "alert"},
            {"id": "reporting", "label": "Reporting rate", "value": m["REPORTING"], "note": self.note(m["REPORTING"], "RR_RH"), "status": self.shade(m["REPORTING"], rr_target), "icon": "file"},
        ]
        bym = self.by(v, p, "pe").set_index("key") if len(v) else pd.DataFrame()
        # 12-month sparkline per KPI for the selected places (all months, so a month filter is shown in context).
        va, pa = self.select(f, ignore_month=True)
        allm = self.by(va, pa, "pe").set_index("key") if len(va) else pd.DataFrame()
        spark_col = {"anc1": "ANC1", "anc4": "ANC4", "ancdrop": "anc_dropout", "penta3": "PENTA3", "pentadrop": "penta_dropout", "reporting": "REPORTING"}
        for k in kpis:
            col = spark_col[k["id"]]
            k["spark"] = [_clean(allm.at[pe, col]) if pe in allm.index and col in allm.columns else None for pe in self.months]
            k["spark_on"] = self.months.index(f.month) if f.month in self.months else None
        trend = [
            {"month": pe, "label": month_label(pe), **{c: _clean(bym.at[pe, c]) if pe in bym.index else None for c in ("ANC1", "ANC4", "PENTA3", "MEASLES")}}
            for pe in self.months
            if (not f.month or pe == f.month)
        ]
        dist = self.by(v, p, "district")
        p3 = sorted(({"name": r.key, "value": _clean(r.PENTA3)} for r in dist.itertuples() if _clean(r.PENTA3) is not None), key=lambda r: (r["value"], r["name"]))
        return {"kpis": kpis, "trend": trend, "penta3_by_district": p3, "penta3_target": self.target("PENTA3"), "findings": self.findings(f, m, dist)}

    def _trend(self, f: Filters) -> float | None:
        """Penta 3 coverage in the latest 3 selected months minus the 3 months before."""
        v, p = self.select(f)
        if not len(v):
            return None
        end = self.months.index(v["pe"].max())
        recent, prior = self.months[max(0, end - 2) : end + 1], self.months[max(0, end - 5) : max(0, end - 2)]
        if f.month or not prior:
            return None
        vv, pp = self.select(f, ignore_month=True)
        r = self.measures(vv[vv["pe"].isin(recent)], pp[pp["pe"].isin(recent)])["PENTA3"]
        q = self.measures(vv[vv["pe"].isin(prior)], pp[pp["pe"].isin(prior)])["PENTA3"]
        return None if r is None or q is None else r - q

    def findings(self, f: Filters, m: dict, dist: pd.DataFrame) -> list[dict]:
        if m["penta1_doses"] is None and m["anc1_visits"] is None:
            return []
        out = [
            {"topic": "Antenatal care", "text": f"{pct(m['ANC1'])} of expected pregnancies started ANC, but only {pct(m['ANC4'])} reached 4 visits: {num(m['anc_drop_women'] or 0)} women ({pct(m['anc_dropout'])}) dropped out."},
            {"topic": "Immunisation", "text": f"Penta 3 coverage is {pct(m['PENTA3'])} against a {pct(self.target('PENTA3'))} target. {num(m['penta_drop_children'] or 0)} children started Penta but missed dose 3 ({pct(m['penta_dropout'])} dropout; WHO limit 10%)."},
        ]
        d = dist.dropna(subset=["PENTA3"]).sort_values(["PENTA3", "key"])
        if len(d):
            out.append({"topic": "Weakest district", "text": f"{d.iloc[0]['key']} has the lowest Penta 3 coverage: {pct(d.iloc[0]['PENTA3'])}."})
        tr = self._trend(f)
        out.append({"topic": "Trend", "text": "Not enough months selected to show a trend." if tr is None else f"Penta 3 coverage in the latest 3 months is {'up' if tr >= 0 else 'down'} {abs(tr) * 100:.1f} pts on the 3 months before."})
        r = dist.dropna(subset=["REPORTING"]).sort_values(["REPORTING", "key"])
        if len(r):
            out.append({"topic": "Reporting", "text": f"Reporting rate is {pct(m['REPORTING'])}. Lowest district: {r.iloc[0]['key']} ({pct(r.iloc[0]['REPORTING'])})."})
        return out

    def districts(self, f: Filters) -> dict:
        v, p = self.select(f)
        ch = self.by(v, p, "ou")
        if not len(ch):
            return {"rows": [], "top_missed": [], "total": None}
        # The table's Total row: the same measures over the whole selection (not an average of rows).
        t = self.measures(v, p)
        total = {
            "anc1": t["ANC1"],
            "anc4": t["ANC4"],
            "anc_dropout": t["anc_dropout"],
            "penta3": t["PENTA3"],
            "penta_dropout": t["penta_dropout"],
            "measles": t["MEASLES"],
            "reporting": t["REPORTING"],
            "missed": t["penta_drop_children"],
        }
        ch = ch.merge(self.org, left_on="key", right_on="ou")
        rows = []
        for r in ch.itertuples():
            g = lambda c: _clean(getattr(r, c))  # noqa: E731
            rows.append(
                {
                    "id": r.ou,
                    "district": r.district,
                    "chiefdom": r.chiefdom,
                    "anc1": g("ANC1"),
                    "anc4": g("ANC4"),
                    "anc_dropout": g("anc_dropout"),
                    "penta3": g("PENTA3"),
                    "penta_dropout": g("penta_dropout"),
                    "measles": g("MEASLES"),
                    "reporting": g("REPORTING"),
                    "missed": g("penta_drop_children"),
                    "shade": {
                        "anc1": self.shade(g("ANC1"), self.target("ANC1")),
                        "anc4": self.shade(g("ANC4"), self.target("ANC4")),
                        "anc_dropout": self.dropout_shade(g("anc_dropout")),
                        "penta3": self.shade(g("PENTA3"), self.target("PENTA3")),
                        "penta_dropout": self.dropout_shade(g("penta_dropout")),
                        "measles": self.shade(g("MEASLES"), self.target("MEASLES")),
                        "reporting": self.shade(g("REPORTING"), self.target("RR_RH")),
                    },
                }
            )
        rows.sort(key=lambda r: (-(r["missed"] or -1e9), r["district"], r["chiefdom"]))
        top = [{"name": r["chiefdom"], "district": r["district"], "value": r["missed"]} for r in rows if (r["missed"] or 0) > 0][:15]
        return {"rows": rows, "top_missed": top, "total": total}

    def actions(self, f: Filters) -> dict:
        v, p = self.select(f)
        m = self.measures(v, p)
        dist = self.by(v, p, "district")
        ch = self.by(v, p, "ou")
        rr_t = self.target("RR_RH")
        acts = []
        if m["penta1_doses"] is not None or m["anc1_visits"] is not None:
            miss = dist[dist["penta_drop_children"] > 0].sort_values(["penta_drop_children", "key"], ascending=[False, True])
            acts.append({"topic": "1. Trace defaulters", "text": f"Trace the {num(m['penta_drop_children'] or 0)} children who missed Penta 3. Start in {', '.join(miss['key'].head(3))}."})
            anc = dist.dropna(subset=["anc_dropout"]).sort_values(["anc_dropout", "key"], ascending=[False, True])
            if len(anc):
                acts.append({"topic": "2. Keep women in ANC", "text": f"Follow up the {num(m['anc_drop_women'] or 0)} women who left ANC before 4 visits. Highest dropout: {anc.iloc[0]['key']} ({pct(anc.iloc[0]['anc_dropout'])})."})
            rep = dist.dropna(subset=["REPORTING"])
            below = int((rep["REPORTING"] < rr_t).sum())
            low = rep.sort_values(["REPORTING", "key"])
            if len(low):
                acts.append({"topic": "3. Chase reports", "text": f"{below} districts report below the {pct(rr_t)} target. Start with {low.iloc[0]['key']}."})
            over = int(((ch["ANC1"] > 1) | (ch["PENTA1"] > 1)).sum()) if len(ch) else 0
            acts.append({"topic": "4. Check denominators", "text": f"{over} chiefdoms show coverage above 100%, which usually means the population estimate is too low. Review them before using their numbers."})
        quad = [
            {"name": r.key, "x": _clean(r.PENTA3), "y": _clean(r.penta_dropout), "size": _clean(r.penta_drop_children) or 0}
            for r in dist.itertuples()
            if _clean(r.PENTA3) is not None and _clean(r.penta_dropout) is not None
        ]
        rep = sorted(({"name": r.key, "value": _clean(r.REPORTING)} for r in dist.itertuples() if _clean(r.REPORTING) is not None), key=lambda r: (r["value"], r["name"]))
        over = []
        if len(ch):
            chx = ch.merge(self.org, left_on="key", right_on="ou")
            o = chx[(chx["ANC1"] > 1) | (chx["PENTA1"] > 1)].sort_values("PENTA1", ascending=False)
            over = [{"district": r.district, "chiefdom": r.chiefdom, "anc1": _clean(r.ANC1), "penta1": _clean(r.PENTA1), "penta1_doses": _clean(r.penta1_doses)} for r in o.itertuples()]
        return {"actions": acts, "quadrant": quad, "reporting_by_district": rep, "reporting_target": rr_t, "penta3_target": self.target("PENTA3"), "over100": over}

    def connection(self) -> dict:
        cnt = self.values.groupby("pe").size()
        s = self.source
        return {
            "source": {
                "host": s.get("host"),
                "server": s.get("server"),
                "version": f"DHIS2 {s.get('version')}",
                "data_to": month_label(self.values["pe"].max(), long=True) if len(self.values) else "–",
                "refreshed_at": s.get("refreshed_at"),
                "live": s.get("live", False),
                "rows": int(len(self.values) + len(self.pop)),
                "chiefdoms": int(len(self.org)),
                "periods": s.get("periods"),
                "seconds": s.get("seconds"),
            },
            "catalogue": [
                {"code": r.code, "name": r.name, "id": r.id, "area": r.area, "target": r.target, "denominator": r.denominator} for r in self.catalogue.itertuples()
            ],
            "rows_by_month": [{"month": pe, "label": month_label(pe), "value": int(cnt.get(pe, 0))} for pe in self.months],
        }
