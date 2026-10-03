"""A synthetic KoboToolbox export: child-health household survey in a fictional "Demo State".

Shaped like a real Kobo export (group prefixes, `_uuid`, `_submission_time`,
`_gps_latitude`) and seeded with the defects real fieldwork produces. Names and
phone numbers are fabricated, and the state, LGAs, codes and coordinates are
invented. No real people or places are represented.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import cache

import numpy as np
import pandas as pd

# Master list: the codes are what joins should use, never the names.
LGAS = {
    "DS-ALA": ("Alaro", 9.410, 6.210),
    "DS-BEN": ("Benin-Ofu", 9.400, 6.250),
    "DS-DUT": ("Dutse Kofa", 9.390, 6.190),
    "DS-EGB": ("Egbeda Nla", 9.380, 6.230),
    "DS-IJE": ("Ijebu Tuntun", 9.300, 6.210),
    "DS-KAU": ("Kaura Sabo", 9.400, 6.270),
    "DS-LAF": ("Lafia Ora", 9.370, 6.260),
    "DS-MBA": ("Mbano Ukwu", 9.490, 6.210),
}
LGA_NAME_TO_CODE = {name: code for code, (name, _, _) in LGAS.items()}

# How enumerators actually type LGA names in free-text fields.
_VARIANTS = {
    "Dutse Kofa": ["Dutse Kofa", "Dutse-Kofa", "dutse kofa ", "DUTSE KOFA"],
    "Egbeda Nla": ["Egbeda Nla", "Egbeda", "Egbeda N.", "egbeda nla"],
    "Kaura Sabo": ["Kaura Sabo", "Kaura Sabo ", "kaura sabo"],
}

_FIRST = "Aisha Amina Fatima Hauwa Zainab Hadiza Maryam Bilkisu Safiya Rukayya Halima Asma'u Khadija Hafsat Jamila".split()
_LAST = "Abubakar Musa Sani Bello Ibrahim Yusuf Usman Lawal Aliyu Garba Haruna Idris Danladi Shehu".split()
FORM_TITLE = "Child Health Household Survey 2026 (synthetic)"


@cache
def sample_export() -> pd.DataFrame:
    rng = np.random.default_rng(2026)
    enumerators = [f"enum_{i:02d}" for i in range(1, 13)]
    # Two enumerators fill some forms from one spot ("desk interviews"): every
    # child vaccinated and well nourished, which inflates coverage and hides
    # malnutrition. That is the bias cleaning must remove.
    desk_spots = {"enum_07": (9.396512, 6.227843), "enum_11": (9.441207, 6.238114)}
    digit_pref = "enum_04"  # rounds every MUAC to .0 or .5
    start_day = datetime(2026, 9, 14)
    rows = []
    hh = 1000
    codes = list(LGAS)
    for i in range(1180):
        enum = enumerators[i % len(enumerators)]
        code = codes[(i // 3) % len(codes)]
        name, lat0, lon0 = LGAS[code]
        day = start_day + timedelta(days=int(rng.integers(0, 14)))
        start = day + timedelta(hours=float(rng.uniform(8, 17.5)))
        rushed = enum in desk_spots and rng.random() < 0.7
        dur = float(rng.uniform(4, 7)) if rushed else max(10.0, rng.normal(26, 6))
        end = start + timedelta(minutes=dur)
        age = int(rng.integers(6, 60))
        # True coverage is modest; the desk interviews report everyone vaccinated.
        p1 = rng.random() < 0.84
        p3 = p1 and rng.random() < 0.76
        muac = float(np.clip(rng.normal(14.0, 1.25), 9.5, 19.5))
        if rushed:
            p1 = p3 = True
            muac = float(rng.uniform(14.5, 16.0))
        muac = round(muac * 2) / 2 if enum == digit_pref else round(muac, 1)
        anc_att = rng.random() < 0.85
        anc_vis = int(np.clip(rng.poisson(4.2), 1, 12)) if anc_att else 0
        lat = round(lat0 + rng.normal(0, 0.03), 6)
        lon = round(lon0 + rng.normal(0, 0.03), 6)
        if rushed:
            lat, lon = desk_spots[enum]  # the same spot, again and again
        lga_text = rng.choice(_VARIANTS.get(name, [name])) if rng.random() < 0.35 else name
        hh += 1
        rows.append(
            {
                "start": start.isoformat(timespec="seconds"),
                "end": end.isoformat(timespec="seconds"),
                "today": day.date().isoformat(),
                "username": enum,
                "deviceid": f"collect:{int(enum[-2:]) * 7919331 % 10**8:08d}",
                "consent": "yes",
                "respondent/respondent_name": f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
                "respondent/phone": f"080{rng.integers(10**7, 10**8)}",
                "location/state": "Demo State",
                "location/lga": lga_text,
                "location/ward": f"{name} Ward {int(rng.integers(1, 9))}",
                "location/hh_id": f"HH{hh:05d}",
                "_gps_latitude": lat,
                "_gps_longitude": lon,
                "child/child_age_months": age,
                "child/child_sex": rng.choice(["male", "female"]),
                "child/muac_cm": muac,
                "child/oedema": "no" if rng.random() > 0.004 else "yes",
                "immunization/card_seen": "yes" if rng.random() < 0.55 else "no",
                "immunization/penta1": "yes" if p1 else "no",
                "immunization/penta3": "yes" if p3 else "no",
                "mother/anc_attended": "yes" if anc_att else "no",
                "mother/anc_visits": anc_vis,
                "_uuid": f"{rng.integers(16**8):08x}-{rng.integers(16**4):04x}-4{rng.integers(16**3):03x}-{rng.integers(16**4):04x}",
                "_submission_time": (end + timedelta(minutes=float(rng.uniform(2, 300)))).isoformat(timespec="seconds"),
            }
        )
    df = pd.DataFrame(rows)
    n = len(df)
    pick = lambda k: rng.choice(n, size=k, replace=False)  # noqa: E731

    df.loc[pick(14), "consent"] = "no"  # data recorded without consent
    for i in pick(18):  # interviews logged at night
        s = datetime.fromisoformat(df.at[i, "start"]).replace(hour=int(rng.choice([21, 22, 23, 4, 5])))
        df.at[i, "start"] = s.isoformat(timespec="seconds")
        df.at[i, "end"] = (s + timedelta(minutes=24)).isoformat(timespec="seconds")
    df.loc[pick(22), ["_gps_latitude", "_gps_longitude"]] = np.nan  # GPS not captured
    for i in pick(9):  # age typed in years, or a sibling's age
        df.at[i, "child/child_age_months"] = int(rng.choice([72, 84, 96, 120]))
    for i in pick(11):  # MUAC typed in millimetres
        df.at[i, "child/muac_cm"] = round(df.at[i, "child/muac_cm"] * 10)
    for i in pick(5):  # MUAC decimal slip: 11.5 entered as 1.15
        df.at[i, "child/muac_cm"] = round(df.at[i, "child/muac_cm"] / 10, 2)
    for i in pick(10):  # Penta3 recorded without Penta1
        df.at[i, "immunization/penta1"] = "no"
        df.at[i, "immunization/penta3"] = "yes"
    for i in pick(8):  # ANC visits recorded, but "never attended ANC"
        df.at[i, "mother/anc_attended"] = "no"
        df.at[i, "mother/anc_visits"] = int(rng.integers(2, 6))
    df.loc[pick(4), "mother/anc_visits"] = 25  # impossible
    for i in pick(3):  # an LGA that is not in the master list
        df.at[i, "location/lga"] = "Central"
    for i in pick(30):  # stray whitespace from tablets
        df.at[i, "location/ward"] = "  " + df.at[i, "location/ward"] + " "

    # The same household interviewed twice by two teams.
    for a, b in zip(pick(5), pick(5)):
        if a != b:
            df.at[b, "location/hh_id"] = df.at[a, "location/hh_id"]

    # Re-sent submissions (identical content) and edited resubmissions (same _uuid).
    resent = df.iloc[pick(24)].copy()
    resent["_submission_time"] = [
        (datetime.fromisoformat(t) + timedelta(hours=6)).isoformat(timespec="seconds") for t in resent["_submission_time"]
    ]
    resent["_uuid"] = [f"{rng.integers(16**8):08x}-{rng.integers(16**4):04x}-4{rng.integers(16**3):03x}-{rng.integers(16**4):04x}" for _ in range(len(resent))]
    edited = df.iloc[pick(7)].copy()
    edited["child/muac_cm"] = edited["child/muac_cm"] + 0.3
    edited["_submission_time"] = [
        (datetime.fromisoformat(t) + timedelta(days=1)).isoformat(timespec="seconds") for t in edited["_submission_time"]
    ]
    out = pd.concat([df, resent, edited], ignore_index=True)
    out = out.sort_values("_submission_time").reset_index(drop=True)
    out.insert(len(out.columns), "_id", np.arange(500_001, 500_001 + len(out)))
    return out
