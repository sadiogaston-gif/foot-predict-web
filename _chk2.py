import sys, collections
sys.path.insert(0, ".")
from backend.service import service
data = service.get_upcoming()
c = collections.Counter()
q = collections.Counter()
for m in data["matches"]:
    for v in m["value_bets"]:
        c[v["market"]] += 1
        if v["qualifies"]:
            q[v["market"]] += 1
print("all markets:", dict(c))
print("qualifying:", dict(q))
print("matches with 1x2 value:", sum(1 for m in data["matches"] if any(v["qualifies"] and v["market"] in ("home","draw","away") for v in m["value_bets"])))
evs = sorted([v["ev_percent"] for m in data["matches"] for v in m["value_bets"] if v["qualifies"]], reverse=True)
print("n ev:", len(evs), "max", evs[:5], "median", evs[len(evs)//2])
