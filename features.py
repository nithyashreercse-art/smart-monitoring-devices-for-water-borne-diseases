"""Turns raw records (health reports, water quality, rainfall) into model features."""
from datetime import date, timedelta

TYPE_CODE = {"rural": 0, "semi-urban": 1, "urban": 2}

# Guideline values used for the human-readable "why was this flagged" list
ECOLI_GUIDELINE = 0        # WHO: E. coli must not be detectable in 100 mL of drinking water
TURBIDITY_LIMIT = 5.0      # NTU (WHO acceptability guidance)
CHLORINE_MIN = 0.2         # mg/L residual chlorine at point of delivery
PH_RANGE = (6.5, 8.5)
HEAVY_RAIN_7D = 100.0      # mm in 7 days (demo threshold)

DEFAULTS = {"ecoli": 0.0, "turbidity": 2.0, "ph": 7.3, "chlorine": 0.4}


def _d(x):
    return x.isoformat()


def compute_features(conn, community_id, as_of=None):
    """Features for one community using the 7 days ending on `as_of` (inclusive)."""
    as_of = as_of or date.today()
    com = conn.execute("SELECT * FROM communities WHERE id=?", (community_id,)).fetchone()
    if com is None:
        raise ValueError("unknown community")
    d0 = _d(as_of - timedelta(days=6))
    d1 = _d(as_of)
    d3 = _d(as_of - timedelta(days=2))   # last 3 days: as_of-2 .. as_of

    # --- health reports -------------------------------------------------
    rows = conn.execute(
        "SELECT report_date, cases, deaths FROM health_reports "
        "WHERE community_id=? AND report_date BETWEEN ? AND ?", (community_id, d0, d1)).fetchall()
    cases_7d = sum(r["cases"] for r in rows)
    deaths_7d = sum(r["deaths"] for r in rows)
    c3 = sum(r["cases"] for r in rows if r["report_date"] >= d3)
    p4 = cases_7d - c3
    trend = (c3 / 3.0) / ((p4 / 4.0) + 0.3)
    trend = min(trend, 8.0)
    pop = max(com["population"], 1)
    cases_per_1000 = cases_7d / pop * 1000.0

    # --- water quality --------------------------------------------------
    wq = conn.execute(
        "SELECT * FROM water_quality WHERE community_id=? AND read_date BETWEEN ? AND ? "
        "ORDER BY read_date", (community_id, d0, d1)).fetchall()
    water_note = "last 7 days"
    if not wq:  # fall back to the most recent reading in the 7 days before that
        wq = conn.execute(
            "SELECT * FROM water_quality WHERE community_id=? AND read_date BETWEEN ? AND ? "
            "ORDER BY read_date DESC LIMIT 1",
            (community_id, _d(as_of - timedelta(days=13)), _d(as_of - timedelta(days=7)))).fetchall()
        water_note = "older reading (8-14 days)" if wq else "no reading (defaults used)"
    if wq:
        ecoli_max = max(r["ecoli"] for r in wq)
        turb_mean = sum(r["turbidity"] for r in wq) / len(wq)
        chl_min = min(r["chlorine"] for r in wq)
        ph_dev = max(max(0.0, PH_RANGE[0] - r["ph"], r["ph"] - PH_RANGE[1]) for r in wq)
    else:
        ecoli_max, turb_mean = DEFAULTS["ecoli"], DEFAULTS["turbidity"]
        chl_min, ph_dev = DEFAULTS["chlorine"], 0.0

    # --- rainfall -------------------------------------------------------
    rr = conn.execute(
        "SELECT rain_date, mm FROM rainfall WHERE community_id=? AND rain_date BETWEEN ? AND ?",
        (community_id, d0, d1)).fetchall()
    rain_7d = sum(r["mm"] for r in rr)
    rain_3d = sum(r["mm"] for r in rr if r["rain_date"] >= d3)

    return {
        # model inputs
        "cases_per_1000": round(cases_per_1000, 3),
        "case_trend": round(trend, 3),
        "deaths_7d": deaths_7d,
        "ecoli_max": round(ecoli_max, 2),
        "turbidity_mean": round(turb_mean, 2),
        "chlorine_min": round(chl_min, 3),
        "ph_dev": round(ph_dev, 3),
        "rain_7d": round(rain_7d, 1),
        "rain_3d": round(rain_3d, 1),
        "type_code": TYPE_CODE.get(com["type"], 0),
        # extras (shown to the user, not used by the model)
        "cases_7d": cases_7d,
        "water_note": water_note,
    }


def explain(f):
    """Plain-language reasons why a community looks risky."""
    out = []
    if f["cases_7d"] > 0:
        out.append(f"{f['cases_7d']} diarrhoeal case(s) reported in 7 days "
                   f"({f['cases_per_1000']:.1f} per 1000 people)")
    if f["case_trend"] >= 1.5 and f["cases_7d"] >= 3:
        out.append(f"Cases rising: last-3-day daily average is {f['case_trend']:.1f}x the previous 4 days")
    if f["deaths_7d"] > 0:
        out.append(f"{f['deaths_7d']} death(s) reported in 7 days")
    if f["ecoli_max"] > ECOLI_GUIDELINE:
        out.append(f"E. coli detected: {f['ecoli_max']:g} CFU/100 mL (guideline: 0)")
    if f["turbidity_mean"] > TURBIDITY_LIMIT:
        out.append(f"High turbidity: {f['turbidity_mean']:.1f} NTU (limit {TURBIDITY_LIMIT:g})")
    if f["chlorine_min"] < CHLORINE_MIN:
        out.append(f"Low residual chlorine: {f['chlorine_min']:.2f} mg/L (minimum {CHLORINE_MIN})")
    if f["ph_dev"] > 0:
        out.append("Water pH outside 6.5-8.5")
    if f["rain_7d"] >= HEAVY_RAIN_7D:
        out.append(f"Heavy rainfall: {f['rain_7d']:.0f} mm in 7 days")
    elif f["rain_3d"] >= 50:
        out.append(f"Recent heavy rain: {f['rain_3d']:.0f} mm in 3 days")
    if not out:
        out.append("No risk factor above guideline levels")
    return out
