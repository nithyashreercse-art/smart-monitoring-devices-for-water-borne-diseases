"""Creates the demo communities and 30 days of SIMULATED health / water / rainfall data.

Everything is generated relative to today's date, so the demo always looks "live".
Locations are approximate and the numbers are simulated for demonstration only.
"""
import random
from datetime import date, datetime, timedelta

import numpy as np

# id, name, district, state, type, population, lat, lon
COMMUNITIES = [
    (1,  "Yelahanka (Bengaluru)",       "Bengaluru Urban", "Karnataka", "urban",      52000, 13.1007, 77.5963),
    (2,  "Jayanagar (Bengaluru)",       "Bengaluru Urban", "Karnataka", "urban",      48000, 12.9299, 77.5838),
    (3,  "Vijayanagar (Mysuru)",        "Mysuru",          "Karnataka", "urban",      38000, 12.3375, 76.6190),
    (4,  "Tumakuru Town",               "Tumakuru",        "Karnataka", "semi-urban", 22000, 13.3392, 77.1140),
    (5,  "Kolar Town",                  "Kolar",           "Karnataka", "semi-urban", 19000, 13.1357, 78.1294),
    (6,  "Doddaballapur",               "Bengaluru Rural", "Karnataka", "semi-urban", 17000, 13.2937, 77.5376),
    (7,  "Hosahalli Village",           "Kolar",           "Karnataka", "rural",       3200, 13.2000, 78.0500),
    (8,  "Kyathasandra Village",        "Tumakuru",        "Karnataka", "rural",       2800, 13.3800, 77.0700),
    (9,  "Channapatna",                 "Ramanagara",      "Karnataka", "semi-urban", 16000, 12.6515, 77.2067),
    (10, "Madhugiri Village",           "Tumakuru",        "Karnataka", "rural",       5000, 13.6600, 77.2100),
    (11, "Dibrugarh Town",              "Dibrugarh",       "Assam",     "urban",      45000, 27.4728, 94.9120),
    (12, "Tea Garden Village",          "Dibrugarh",       "Assam",     "rural",       2400, 27.4000, 95.0000),
    (13, "Naharkatia",                  "Dibrugarh",       "Assam",     "semi-urban", 15000, 27.2900, 95.3200),
    (14, "Khowang Village",             "Dibrugarh",       "Assam",     "rural",       3000, 27.3300, 94.9100),
]

SCENARIO_COMMUNITY_OUTBREAK = 12   # Tea Garden Village (mirrors the Dibrugarh case study [3])
SCENARIO_MEDIUM = (7, 5)           # Hosahalli Village, Kolar Town


def _iso(offset, today):
    return (today + timedelta(days=offset)).isoformat()


def seed(conn, today=None, rng_seed=7):
    today = today or date.today()
    rng = random.Random(rng_seed)
    nprng = np.random.default_rng(rng_seed)
    now = datetime.now().isoformat(timespec="seconds")

    conn.executemany("INSERT INTO communities VALUES (?,?,?,?,?,?,?,?)", COMMUNITIES)

    health, water, rain = [], [], []
    for cid, name, dist, state, ctype, pop, lat, lon in COMMUNITIES:
        for off in range(-29, 1):
            # --- baseline rainfall: light, occasional ---
            mm = float(nprng.exponential(7)) if rng.random() < 0.25 else 0.0
            rain.append((cid, _iso(off, today), round(mm, 1), "IMD / local gauge (simulated)", now))
            # --- baseline sporadic diarrhoeal cases ---
            lam = max(0.04, pop / 100000.0 * 0.35)
            cases = int(nprng.poisson(lam))
            health.append((cid, _iso(off, today), cases, 0, "ASHA worker (simulated)", "ASHA", now))
            # --- baseline water tests every 2nd day ---
            if off % 2 == 0:
                ecoli = 0.0 if rng.random() < 0.85 else float(nprng.poisson(2))
                water.append((cid, _iso(off, today), ecoli,
                              round(max(0.3, rng.gauss(2.0, 0.7)), 2),
                              round(rng.gauss(7.4, 0.2), 2),
                              round(max(0.25, rng.gauss(0.5, 0.08)), 2),
                              "Field kit (simulated)", now))

    def set_rain(cid, off, mm):
        for i, r in enumerate(rain):
            if r[0] == cid and r[1] == _iso(off, today):
                rain[i] = (cid, r[1], mm, r[3], r[4])
                return

    def set_cases(cid, off, cases, deaths=0):
        for i, r in enumerate(health):
            if r[0] == cid and r[1] == _iso(off, today):
                health[i] = (cid, r[1], cases, deaths, r[4], r[5], r[6])
                return

    def add_water(cid, off, ecoli, turb, ph, chl, src="Field kit (simulated)"):
        water[:] = [w for w in water if not (w[0] == cid and w[1] == _iso(off, today))]
        water.append((cid, _iso(off, today), float(ecoli), float(turb), float(ph), float(chl), src, now))

    # ===== Scenario 1: outbreak building in Tea Garden Village (HIGH risk) =====
    c = SCENARIO_COMMUNITY_OUTBREAK
    for off, mm in {-12: 82, -11: 64, -10: 47, -9: 12}.items():
        set_rain(c, off, mm)
    for off, e, t, ph, ch in [(-11, 8, 6.5, 7.1, 0.15), (-9, 25, 8.2, 6.9, 0.10),
                              (-7, 60, 9.6, 6.8, 0.06), (-5, 110, 11.0, 6.7, 0.05),
                              (-3, 140, 12.4, 6.6, 0.04), (-1, 160, 12.0, 6.6, 0.04)]:
        add_water(c, off, e, t, ph, ch)
    for off, n, d in [(-9, 1, 0), (-8, 1, 0), (-7, 2, 0), (-6, 2, 0), (-5, 3, 0),
                      (-4, 4, 0), (-3, 5, 0), (-2, 6, 1), (-1, 4, 0), (0, 3, 0)]:
        set_cases(c, off, n, d)

    # ===== Scenario 2: moderate concern in Hosahalli Village and Kolar Town (MEDIUM) =====
    c = 7
    for off, mm in {-5: 55, -4: 38, -3: 10}.items():
        set_rain(c, off, mm)
    add_water(c, -4, 6, 5.8, 7.2, 0.14)
    add_water(c, -2, 9, 6.4, 7.1, 0.12)
    for off, n in [(-3, 1), (-2, 2), (-1, 2), (0, 1)]:
        set_cases(c, off, n)
    c = 5
    for off, mm in {-4: 42, -3: 30}.items():
        set_rain(c, off, mm)
    add_water(c, -3, 4, 5.6, 7.3, 0.15)
    add_water(c, -1, 6, 6.0, 7.2, 0.12)
    for off, n in [(-3, 2), (-2, 3), (-1, 4), (0, 3)]:
        set_cases(c, off, n)

    conn.executemany("INSERT INTO health_reports (community_id,report_date,cases,deaths,source,reporter,created_at) "
                     "VALUES (?,?,?,?,?,?,?)", health)
    conn.executemany("INSERT INTO water_quality (community_id,read_date,ecoli,turbidity,ph,chlorine,source,created_at) "
                     "VALUES (?,?,?,?,?,?,?,?)", water)
    conn.executemany("INSERT INTO rainfall (community_id,rain_date,mm,source,created_at) VALUES (?,?,?,?,?)", rain)
    conn.commit()
