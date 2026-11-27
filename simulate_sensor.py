"""Pretends to be an ESP32 + water sensor and posts readings to the running server.

Usage:  python simulate_sensor.py            (clean water, community 1)
        python simulate_sensor.py 12 bad     (contaminated readings for community 12)
"""
import json
import random
import sys
import time
import urllib.request

URL = "http://127.0.0.1:5000/api/sensor"
cid = int(sys.argv[1]) if len(sys.argv) > 1 else 1
bad = len(sys.argv) > 2 and sys.argv[2].lower() == "bad"

for i in range(3):
    reading = ({"ecoli": random.randint(40, 150), "turbidity": round(random.uniform(7, 13), 1),
                "ph": round(random.uniform(6.5, 7.0), 2), "chlorine": round(random.uniform(0.02, 0.1), 2)}
               if bad else
               {"ecoli": 0, "turbidity": round(random.uniform(1, 3), 1),
                "ph": round(random.uniform(7.0, 7.6), 2), "chlorine": round(random.uniform(0.4, 0.6), 2)})
    reading["community_id"] = cid
    req = urllib.request.Request(URL, data=json.dumps(reading).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        print("sent", reading, "->", json.loads(r.read())["results"])
    time.sleep(1)
