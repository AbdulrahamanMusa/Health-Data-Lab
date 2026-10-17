"""DHIS2 Web API client: the same queries as the Power BI model's Power Query.

Like the Power BI report, the dashboard pages use DHIS2 analytics by chiefdom
(level 3), so every figure matches the .pbip exactly. The same indicators are also
pulled by health facility (level 4): those rows are what the predictive model scores.
(Facility rows don't add up to the chiefdom totals exactly, because some data is
entered directly on chiefdom org units.)

Connection settings mirror the Power BI parameters and come from the environment:
DHIS2_BASE_URL, DHIS2_USERNAME, DHIS2_PASSWORD, DHIS2_ROOT_ORG_UNIT, DHIS2_PERIODS.
The server defaults are the public DHIS2 play demo (Sierra Leone), as in the .pbip.
Credentials have no defaults and are never stored in the code: set them as
environment variables (on Render: secret environment variables) or, locally, in
a .env file next to app.py (git ignores it; see .env.example).
"""

from __future__ import annotations

import gzip
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import httpx


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from a local .env file; real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Same catalogue as the Power BI 'Indicator Catalogue' table (targets are illustrative).
CATALOGUE = [
    {"code": "ANC1", "id": "Uvn6LCg7dVU", "name": "ANC 1 coverage", "area": "Antenatal care", "target": 0.95, "denominator": "Expected pregnancies", "denominator_id": "h0xKKjijTdI"},
    {"code": "ANC4", "id": "AUqdhY4mpvp", "name": "ANC 4 coverage", "area": "Antenatal care", "target": 0.80, "denominator": "Expected pregnancies", "denominator_id": "h0xKKjijTdI"},
    {"code": "BCG", "id": "FnYCr2EAzWS", "name": "BCG coverage <1y", "area": "Immunisation", "target": 0.90, "denominator": "Population under 1", "denominator_id": "DTVRnCGamkV"},
    {"code": "PENTA1", "id": "i7WSgSJpnfu", "name": "Penta 1 coverage <1y", "area": "Immunisation", "target": 0.90, "denominator": "Population under 1", "denominator_id": "DTVRnCGamkV"},
    {"code": "PENTA3", "id": "tUIlpyeeX9N", "name": "Penta 3 coverage <1y", "area": "Immunisation", "target": 0.90, "denominator": "Population under 1", "denominator_id": "DTVRnCGamkV"},
    {"code": "MEASLES", "id": "FbKK4ofIv5R", "name": "Measles coverage <1y", "area": "Immunisation", "target": 0.90, "denominator": "Population under 1", "denominator_id": "DTVRnCGamkV"},
    {"code": "RR_RH", "id": "QX4ZTUbOt3a.REPORTING_RATE", "name": "Reproductive health reporting rate", "area": "Reporting", "target": 0.90, "denominator": "Expected reports", "denominator_id": ""},
    {"code": "RR_CH", "id": "BfMAe6Itzgt.REPORTING_RATE", "name": "Child health reporting rate", "area": "Reporting", "target": 0.90, "denominator": "Expected reports", "denominator_id": ""},
]


@dataclass(frozen=True)
class Settings:
    base_url: str
    username: str
    password: str
    root: str
    periods: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            base_url=os.environ.get("DHIS2_BASE_URL", "https://play.im.dhis2.org/stable-2-42-6").rstrip("/"),
            username=os.environ.get("DHIS2_USERNAME", ""),
            password=os.environ.get("DHIS2_PASSWORD", ""),
            root=os.environ.get("DHIS2_ROOT_ORG_UNIT", "ImspTQPwCqd"),
            periods=os.environ.get("DHIS2_PERIODS", "LAST_12_MONTHS"),
        )

    @property
    def host(self) -> str:
        return self.base_url.split("://", 1)[-1].split("/", 1)[0]


class DHIS2Error(Exception):
    pass


def _simplify_ring(ring: list, tol: float = 0.01) -> list:
    """Douglas-Peucker on one polygon ring, rounded to ~100 m: enough for a district map."""
    pts = [(round(x, 3), round(y, 3)) for x, y in ring]

    def dp(a: int, b: int, keep: set) -> None:
        (x1, y1), (x2, y2) = pts[a], pts[b]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, idx = 0.0, None
        for i in range(a + 1, b):
            d = abs(dy * pts[i][0] - dx * pts[i][1] + x2 * y1 - y2 * x1) / norm
            if d > best:
                best, idx = d, i
        if idx is not None and best > tol:
            keep.add(idx)
            dp(a, idx, keep)
            dp(idx, b, keep)

    if len(pts) < 4:
        return pts
    # A closed ring starts and ends on the same point: split it at the point farthest from the start.
    far = max(range(len(pts)), key=lambda i: (pts[i][0] - pts[0][0]) ** 2 + (pts[i][1] - pts[0][1]) ** 2)
    keep = {0, far, len(pts) - 1}
    dp(0, far, keep)
    dp(far, len(pts) - 1, keep)
    out = [pts[i] for i in sorted(keep)]
    return out if len(out) >= 4 else pts


def _polygons(geometry: dict | None) -> list:
    """Outer rings only, simplified: a list of [[lon, lat], ...]."""
    if not geometry:
        return []
    polys = geometry["coordinates"] if geometry.get("type") == "MultiPolygon" else [geometry.get("coordinates", [])]
    return [[list(p) for p in _simplify_ring(poly[0])] for poly in polys if poly and len(poly[0]) >= 4]


def _get(client: httpx.Client, s: Settings, path: str, params: dict) -> dict:
    try:
        r = client.get(f"{s.base_url}/{path}", params=params)
    except httpx.HTTPError as e:
        raise DHIS2Error(f"Could not reach {s.host} ({type(e).__name__}).") from e
    if r.status_code == 401:
        raise DHIS2Error("DHIS2 rejected the user name or password.")
    if r.status_code >= 400:
        raise DHIS2Error(f"DHIS2 returned {r.status_code} for {path}.")
    return r.json()


def _analytics(client: httpx.Client, s: Settings, ids: list[str], with_numden: bool, level: int) -> list[dict]:
    raw = _get(
        client,
        s,
        "api/analytics.json",
        {
            "dimension": [f"dx:{';'.join(ids)}", f"pe:{s.periods}", f"ou:{s.root};LEVEL-{level}"],
            "includeNumDen": "true" if with_numden else "false",
            "skipMeta": "true",
        },
    )
    cols = [h["name"] for h in raw["headers"]]
    num = lambda v: None if v in (None, "") else float(v)  # noqa: E731
    out = []
    for row in raw["rows"]:
        d = dict(zip(cols, row))
        out.append({"dx": d["dx"], "pe": d["pe"], "ou": d["ou"], "value": num(d.get("value")), "numerator": num(d.get("numerator")), "denominator": num(d.get("denominator"))})
    return out


def fetch(s: Settings | None = None) -> dict:
    """Pull everything the dashboard needs. Returns a JSON-serialisable snapshot."""
    s = s or Settings.from_env()
    if not s.username or not s.password:
        raise DHIS2Error("DHIS2 credentials are not set. Add DHIS2_USERNAME and DHIS2_PASSWORD to the environment (or to a local .env file).")
    started = time.monotonic()
    with httpx.Client(auth=(s.username, s.password), timeout=httpx.Timeout(300, connect=20), headers={"Accept": "application/json"}) as client:
        info = _get(client, s, "api/system/info", {})
        units = lambda level, fields: _get(  # noqa: E731
            client, s, "api/organisationUnits.json", {"level": level, "fields": fields, "paging": "false", "filter": f"path:like:{s.root}"}
        )["organisationUnits"]
        district_units = units(2, "id,name,geometry")
        chiefdom_units = units(3, "id,name,parent[id,name]")
        ous = units(4, "id,name,geometry,parent[id,name,parent[id,name]]")
        ind_ids = [c["id"] for c in CATALOGUE]
        pop_ids = sorted({c["denominator_id"] for c in CATALOGUE if c["denominator_id"]})
        values = _analytics(client, s, ind_ids, True, 3)
        pops = _analytics(client, s, pop_ids, False, 3)
        fvalues = _analytics(client, s, ind_ids, True, 4)
        fpops = _analytics(client, s, pop_ids, False, 4)
    districts = [{"id": o["id"], "name": o["name"], "polygons": _polygons(o.get("geometry"))} for o in district_units]
    chiefdoms = [{"id": o["id"], "name": o["name"], "district": (o.get("parent") or {}).get("name")} for o in chiefdom_units]
    facilities = []
    for o in ous:
        chiefdom = o.get("parent") or {}
        district = chiefdom.get("parent") or {}
        geo = o.get("geometry") or {}
        point = geo.get("coordinates") if geo.get("type") == "Point" else None
        facilities.append({"id": o["id"], "name": o["name"], "chiefdom": chiefdom.get("name"), "district": district.get("name"), "lon": point[0] if point else None, "lat": point[1] if point else None})
    return {
        "source": {
            "server": s.base_url,
            "host": s.host,
            "version": info.get("version"),
            "server_date": info.get("serverDate"),
            "periods": s.periods,
            "refreshed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "seconds": round(time.monotonic() - started, 1),
            "live": True,
        },
        "catalogue": CATALOGUE,
        "districts": districts,
        "chiefdoms": chiefdoms,
        "values": values,
        "populations": pops,
        "facilities": facilities,
        "facility_values": fvalues,
        "facility_populations": fpops,
    }


def save(snapshot: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(snapshot, f, separators=(",", ":"))


def load(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        snap = json.load(f)
    snap["source"]["live"] = False
    return snap
