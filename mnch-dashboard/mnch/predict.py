"""Facility risk model: which health facilities are likely to fall behind next quarter?

Two outcomes, each defined with the dashboard's own thresholds:

  low_penta3   Penta 3 coverage in the next 3 months below 70%: more than 20 pts
               under the 90% target, the scorecard's red band.
  anc_dropout  ANC 1 to 4 dropout in the next 3 months above 50%: more than half
               of the women who start antenatal care don't reach 4 visits.

Each facility's last 6 months (DHIS2 facility-level analytics) become features:
recent and 6-month coverage or dropout, reporting completeness, size, and the
district's level. (Trend and facility-type features were tried and dropped: they
did not improve the time-split test.) A logistic
regression (L2-regularised, fitted with Newton's method in numpy) turns them
into a probability. It is deliberately simple: every prediction can be
explained as a sum of named contributions.

Validation is a time split, never random: the model is fitted on quarters that
end before the test quarter starts, then scored on that unseen quarter and
compared with the obvious baseline, "same as last quarter".
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

OUTCOMES = {
    "low_penta3": {
        "label": "Low Penta 3 coverage",
        "short": "Low coverage",
        "question": "Will Penta 3 coverage be below 70% next quarter?",
        "definition": "Penta 3 coverage below 70% in the next 3 months (more than 20 pts under the 90% target).",
        "threshold": 0.70,
        "baseline": "penta3_cov",
        "features": ["penta3_cov", "penta3_cov_6m", "penta_dropout", "reporting", "log_u1", "district_penta3"],
    },
    "anc_dropout": {
        "label": "High ANC dropout",
        "short": "ANC dropout",
        "question": "Will more than half of women who start ANC miss their 4th visit next quarter?",
        "definition": "ANC 1 to 4 dropout above 50% in the next 3 months.",
        "threshold": 0.50,
        "baseline": "anc_dropout",
        "features": ["anc_dropout", "anc_dropout_6m", "anc1_cov", "reporting", "log_anc1", "log_u1", "district_anc_dropout"],
    },
}

FEATURES = {
    # name: (label shown to users, value formatter)
    "penta3_cov": ("Penta 3 coverage, last 3 months", "pct"),
    "penta3_cov_6m": ("Penta 3 coverage, last 6 months", "pct"),
    "anc_dropout_6m": ("ANC 1 to 4 dropout, last 6 months", "pct"),
    "penta_dropout": ("Penta 1 to 3 dropout, last 3 months", "pct"),
    "anc_dropout": ("ANC 1 to 4 dropout, last 3 months", "pct"),
    "anc4_cov": ("ANC 4 coverage, last 3 months", "pct"),
    "anc1_cov": ("ANC 1 coverage, last 3 months", "pct"),
    "penta3_change": ("Change in Penta 3 coverage on the quarter before", "pts"),
    "anc_dropout_change": ("Change in ANC dropout on the quarter before", "pts"),
    "reporting": ("Reporting rate, last 3 months", "pct"),
    "months_reported": ("Months with data, last 3", "months"),
    "log_anc1": ("ANC 1 visits, last 3 months", "log"),
    "log_u1": ("Population under 1", "log"),
    "district_penta3": ("District Penta 3 coverage, last 3 months", "pct"),
    "district_anc_dropout": ("District ANC dropout, last 3 months", "pct"),
    "type_hospital": ("Facility type: hospital", "flag"),
    "type_chc": ("Facility type: CHC", "flag"),
    "type_mchp": ("Facility type: MCHP", "flag"),
}
RISK_BANDS = [(0.6, "high"), (0.35, "medium"), (0.0, "low")]


def facility_type(name: str) -> str:
    n = name.upper()
    for pat, t in ((r"\bHOSPITAL\b|\bHOSP\b|\bGH\b", "Hospital"), (r"\bCHC\b", "CHC"), (r"\bMCHP\b", "MCHP"), (r"\bCHP\b", "CHP"), (r"\bCLINIC\b", "Clinic")):
        if re.search(pat, n):
            return t
    return "Other"


def band(p: float) -> str:
    return next(b for cut, b in RISK_BANDS if p >= cut)


# ----------------------------------------------------------------- data


@dataclass
class FacilityData:
    facilities: pd.DataFrame  # id, name, chiefdom, district, lat, lon, type
    monthly: pd.DataFrame  # index (ou, pe) -> numerators, reports, population targets
    months: list[str]

    @classmethod
    def from_snapshot(cls, snap: dict) -> "FacilityData":
        code = {c["id"]: c["code"] for c in snap["catalogue"]}
        fac = pd.DataFrame(snap["facilities"])
        fac["type"] = fac["name"].map(facility_type)
        v = pd.DataFrame(snap["facility_values"])
        v["code"] = v["dx"].map(code)
        num = v.pivot_table(index=["ou", "pe"], columns="code", values="numerator", aggfunc="sum")
        rep = v[v["code"].str.startswith("RR")].pivot_table(index=["ou", "pe"], columns="code", values="denominator", aggfunc="sum").add_suffix("_EXP")
        p = pd.DataFrame(snap["facility_populations"])
        p["target"] = p["value"] * p["pe"].map(lambda pe: calendar.monthrange(int(pe[:4]), int(pe[4:]))[1]) / 365
        pop = p.pivot_table(index=["ou", "pe"], columns="dx", values="target", aggfunc="sum").rename(columns={"h0xKKjijTdI": "PREG", "DTVRnCGamkV": "U1"})
        monthly = num.join(rep, how="outer").join(pop, how="outer")
        months = sorted(monthly.index.get_level_values("pe").unique())
        return cls(fac, monthly, months)

    def window(self, months: list[str]) -> pd.DataFrame:
        """Sums over a set of months, one row per facility, with derived rates."""
        cols = ["ANC1", "ANC4", "PENTA1", "PENTA3", "MEASLES", "RR_RH", "RR_CH", "RR_RH_EXP", "RR_CH_EXP", "PREG", "U1"]
        m = self.monthly[self.monthly.index.get_level_values("pe").isin(months)]
        s = m.reindex(columns=cols).groupby(level="ou").sum(min_count=1)
        s["months_reported"] = m["ANC1"].notna().groupby(level="ou").sum() if "ANC1" in m else 0
        s["anc_dropout"] = (s["ANC1"] - s["ANC4"].fillna(0)) / s["ANC1"].where(s["ANC1"] > 0)
        s["penta_dropout"] = (s["PENTA1"] - s["PENTA3"].fillna(0)) / s["PENTA1"].where(s["PENTA1"] > 0)
        s["penta3_cov"] = s["PENTA3"].fillna(0) / s["U1"].where(s["U1"] > 0)
        s["anc1_cov"] = s["ANC1"].fillna(0) / s["PREG"].where(s["PREG"] > 0)
        s["anc4_cov"] = s["ANC4"].fillna(0) / s["PREG"].where(s["PREG"] > 0)
        exp = s[["RR_RH_EXP", "RR_CH_EXP"]].sum(axis=1, min_count=1)
        s["reporting"] = s[["RR_RH", "RR_CH"]].sum(axis=1, min_count=1).fillna(0) / exp.where(exp > 0)
        return s


def _eligible(w: pd.DataFrame, outcome: str) -> pd.Series:
    """Enough activity for the outcome to mean something."""
    if outcome == "anc_dropout":
        return w["ANC1"].fillna(0) >= 10
    return (w["U1"].fillna(0) >= 5) & (w[["PENTA1", "PENTA3"]].notna().any(axis=1))


def _label(w: pd.DataFrame, outcome: str) -> pd.Series:
    t = OUTCOMES[outcome]["threshold"]
    y = (w["anc_dropout"] > t) if outcome == "anc_dropout" else (w["penta3_cov"] < t)
    return y.astype(float).where(_eligible(w, outcome))


def features(fd: FacilityData, cutoff: int) -> pd.DataFrame:
    """Features for every facility using months up to and including index `cutoff`."""
    ms = fd.months
    recent = fd.window(ms[max(0, cutoff - 2) : cutoff + 1])
    prior = fd.window(ms[max(0, cutoff - 5) : max(0, cutoff - 2)]) if cutoff >= 3 else recent.iloc[0:0]
    six = fd.window(ms[max(0, cutoff - 5) : cutoff + 1])
    f = pd.DataFrame(index=fd.facilities["id"])
    f.index.name = "ou"
    r = recent.reindex(f.index)
    q = prior.reindex(f.index)
    h = six.reindex(f.index)
    f["penta3_cov"] = r["penta3_cov"].clip(0, 2)
    f["penta3_cov_6m"] = h["penta3_cov"].clip(0, 2)
    f["anc_dropout_6m"] = h["anc_dropout"].clip(-1, 1)
    f["penta_dropout"] = r["penta_dropout"].clip(-1, 1)
    f["anc_dropout"] = r["anc_dropout"].clip(-1, 1)
    f["anc4_cov"] = r["anc4_cov"].clip(0, 2)
    f["anc1_cov"] = r["anc1_cov"].clip(0, 3)
    f["penta3_change"] = (r["penta3_cov"].clip(0, 2) - q["penta3_cov"].clip(0, 2)).clip(-1, 1)
    f["anc_dropout_change"] = (r["anc_dropout"].clip(-1, 1) - q["anc_dropout"].clip(-1, 1)).clip(-1, 1)
    f["reporting"] = r["reporting"].clip(0, 1)
    f["months_reported"] = r["months_reported"].fillna(0)
    f["log_anc1"] = np.log1p(r["ANC1"].fillna(0))
    f["log_u1"] = np.log1p((r["U1"].fillna(0) * 4))  # quarterly target x4 = annual population
    fac = fd.facilities.set_index("id")
    dist = fac["district"].reindex(f.index)
    sums = r.assign(district=dist).groupby("district")[["PENTA3", "U1", "ANC1", "ANC4"]].sum(min_count=1)
    f["district_penta3"] = dist.map(sums["PENTA3"] / sums["U1"]).clip(0, 2)
    f["district_anc_dropout"] = dist.map((sums["ANC1"] - sums["ANC4"]) / sums["ANC1"]).clip(-1, 1)
    ftype = fac["type"].reindex(f.index)
    f["type_hospital"] = (ftype == "Hospital").astype(float)
    f["type_chc"] = (ftype == "CHC").astype(float)
    f["type_mchp"] = (ftype == "MCHP").astype(float)
    return f[list(FEATURES)]


def examples(fd: FacilityData, cutoff: int, outcome: str) -> tuple[pd.DataFrame, pd.Series]:
    """(features at cutoff, label over the 3 months after it), for eligible facilities."""
    x = features(fd, cutoff)
    nxt = fd.months[cutoff + 1 : cutoff + 4]
    y = _label(fd.window(nxt).reindex(x.index), outcome)
    keep = y.notna() & _eligible(fd.window(fd.months[max(0, cutoff - 2) : cutoff + 1]).reindex(x.index), outcome)
    return x[keep], y[keep]


# ----------------------------------------------------------------- model


class Logistic:
    """L2-regularised logistic regression on standardised features (Newton's method)."""

    def __init__(self, l2: float = 10.0):
        self.l2 = l2

    def fit(self, x: pd.DataFrame, y: pd.Series) -> "Logistic":
        self.cols = list(x.columns)
        self.median = x.median()
        xi = x.fillna(self.median)
        self.mean, self.sd = xi.mean(), xi.std().replace(0, 1).fillna(1)
        z = ((xi - self.mean) / self.sd).to_numpy()
        a = np.column_stack([np.ones(len(z)), z])
        yy = y.to_numpy()
        w = np.zeros(a.shape[1])
        pen = np.full(a.shape[1], self.l2)
        pen[0] = 0.0  # no penalty on the intercept
        for _ in range(50):
            p = 1 / (1 + np.exp(-np.clip(a @ w, -30, 30)))
            g = a.T @ (p - yy) + pen * w
            h = (a * (p * (1 - p))[:, None]).T @ a + np.diag(pen)
            step = np.linalg.solve(h, g)
            w -= step
            if np.abs(step).max() < 1e-8:
                break
        self.w = w
        return self

    def z(self, x: pd.DataFrame) -> np.ndarray:
        return ((x[self.cols].fillna(self.median) - self.mean) / self.sd).to_numpy()

    def predict(self, x: pd.DataFrame) -> np.ndarray:
        return 1 / (1 + np.exp(-np.clip(self.w[0] + self.z(x) @ self.w[1:], -30, 30)))

    def contributions(self, x: pd.DataFrame) -> np.ndarray:
        """Each feature's push on the log-odds, relative to an average facility."""
        return self.z(x) * self.w[1:]


def auc(y: np.ndarray, s: np.ndarray) -> float | None:
    pos, neg = s[y == 1], s[y == 0]
    if not len(pos) or not len(neg):
        return None
    ranks = pd.Series(np.concatenate([pos, neg])).rank().to_numpy()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _fmt(kind: str, v: float) -> str:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "no data"
    if kind == "pct":
        return f"{v * 100:.0f}%"
    if kind == "pts":
        return f"{v * 100:+.0f} pts"
    if kind == "months":
        return f"{v:.0f} of 3"
    if kind == "log":
        return f"{np.expm1(v):,.0f}"
    return "yes" if v >= 0.5 else "no"


@dataclass
class OutcomeModel:
    outcome: str
    model: Logistic
    validation: dict
    scores: pd.DataFrame  # one row per scored facility


def build(fd: FacilityData, outcome: str) -> OutcomeModel:
    n = len(fd.months)
    if n < 9:
        raise ValueError("At least 9 months of data are needed to train and test the model.")
    test_cut = n - 4  # features to month n-4, label the last 3 months
    first = 2
    train_cuts = [c for c in range(first, test_cut) if c + 3 <= test_cut]  # labels end before the test window starts
    cols = OUTCOMES[outcome]["features"]
    xs, ys = zip(*(examples(fd, c, outcome) for c in train_cuts))
    xtr, ytr = pd.concat(xs)[cols], pd.concat(ys)
    xte, yte = examples(fd, test_cut, outcome)
    m = Logistic().fit(xtr, ytr)
    p = m.predict(xte[cols])
    yv = yte.to_numpy()
    base_feat = OUTCOMES[outcome]["baseline"]
    base_score = xte[base_feat].fillna(xte[base_feat].median()).to_numpy()
    if outcome == "low_penta3":
        base_score = -base_score
    order = np.argsort(-p)
    top = order[: max(1, len(order) // 10)]
    bins = []
    for lo, hi in ((0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
        sel = (p >= lo) & (p < hi)
        if sel.sum():
            bins.append({"from": lo, "to": min(hi, 1), "predicted": float(p[sel].mean()), "observed": float(yv[sel].mean()), "n": int(sel.sum())})
    last_status = (xte[base_feat] < OUTCOMES[outcome]["threshold"]) if outcome == "low_penta3" else (xte[base_feat] > OUTCOMES[outcome]["threshold"])
    validation = {
        "train_quarters": len(train_cuts),
        "train_rows": int(len(xtr)),
        "test_rows": int(len(xte)),
        "test_window": [fd.months[test_cut + 1], fd.months[min(n - 1, test_cut + 3)]],
        "base_rate": float(yv.mean()),
        "auc": auc(yv, p),
        "baseline_auc": auc(yv, base_score),
        "brier": float(np.mean((p - yv) ** 2)),
        "baseline_accuracy": float((last_status.to_numpy() == (yv == 1)).mean()),
        "accuracy": float(((p >= 0.5) == (yv == 1)).mean()),
        "top10_precision": float(yv[top].mean()),
        "top10_n": int(len(top)),
        "calibration": bins,
    }
    # Final model: every quarter whose outcome is known, then score the latest 3 months.
    all_cuts = [c for c in range(first, n - 3)]
    xs, ys = zip(*(examples(fd, c, outcome) for c in all_cuts))
    final = Logistic().fit(pd.concat(xs)[cols], pd.concat(ys))
    validation["final_rows"] = int(sum(len(y) for y in ys))
    validation["coefficients"] = sorted(
        ({"feature": c, "label": FEATURES[c][0], "odds_ratio": float(np.exp(w))} for c, w in zip(final.cols, final.w[1:])), key=lambda r: -abs(np.log(r["odds_ratio"]))
    )
    cut = n - 1
    x_now = features(fd, cut)
    elig = _eligible(fd.window(fd.months[cut - 2 : cut + 1]).reindex(x_now.index), outcome)
    x_all = x_now[elig]
    x_now = x_all[cols]
    prob = final.predict(x_now)
    contrib = final.contributions(x_now)
    fac = fd.facilities.set_index("id").reindex(x_now.index)
    rows = []
    for i, ou in enumerate(x_now.index):
        c = contrib[i]
        idx = np.argsort(-c)[:3]
        drivers = [
            {"feature": final.cols[j], "label": FEATURES[final.cols[j]][0], "value": _fmt(FEATURES[final.cols[j]][1], x_now.iat[i, j]), "effect": float(c[j])}
            for j in idx
            if c[j] > 0.05
        ]
        rows.append(
            {
                "id": ou,
                "name": fac.at[ou, "name"],
                "chiefdom": fac.at[ou, "chiefdom"],
                "district": fac.at[ou, "district"],
                "type": fac.at[ou, "type"],
                "lat": None if pd.isna(fac.at[ou, "lat"]) else float(fac.at[ou, "lat"]),
                "lon": None if pd.isna(fac.at[ou, "lon"]) else float(fac.at[ou, "lon"]),
                "risk": float(prob[i]),
                "band": band(float(prob[i])),
                "now": None if pd.isna(x_all.at[ou, base_feat]) else float(x_all.at[ou, base_feat]),
                "reporting": None if pd.isna(x_all.at[ou, "reporting"]) else float(x_all.at[ou, "reporting"]),
                "drivers": drivers,
            }
        )
    scores = pd.DataFrame(rows).sort_values("risk", ascending=False)
    validation["scored_on"] = [fd.months[cut - 2], fd.months[cut]]
    return OutcomeModel(outcome, final, validation, scores)
