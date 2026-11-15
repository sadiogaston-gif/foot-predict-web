import json, sys, time
sys.path.insert(0, ".")
from backend.service import service

t0 = time.time()
data = service.get_upcoming()
print("load+predict %d ms" % int((time.time()-t0)*1000))
print("slate:", {k: data["slate"][k] for k in ("projected","shift_days","first_date","last_date","value_bets")})
print("count:", data["count"])
for m in data["matches"][:4]:
    print(f'{m["league"]:<15} {m["date"]} {m["time"]} {m["home_team"]} vs {m["away_team"]}')
    print("   probs", m["probabilities"], "over", m["over_2_5"], "btts", m["btts_yes"])
    print("   odds", {k: v for k, v in m["odds"].items() if v}, "| best:", m["best_value"] and (m["best_value"]["label"], m["best_value"]["ev_percent"]))

mid = data["matches"][0]["id"]
t0 = time.time()
detail = service.get_match(mid)
print("detail %d ms" % int((time.time()-t0)*1000))
print("detail keys:", sorted(detail.keys()))
print("matrix rows:", len(detail["score_matrix"]["rows"]), "cols:", len(detail["score_matrix"]["rows"][0]["probabilities"]))
print("elo hist:", len(detail["elo_history"]["home"]["points"]), len(detail["elo_history"]["away"]["points"]))
print("recent home:", [(r["date"], r["opponent"], r["result"]) for r in detail["recent"]["home"]["matches"]])
print("summary:", detail["recent"]["home"]["summary"])

t0 = time.time()
stats = service.backtest_stats()
print("backtest %d ms" % int((time.time()-t0)*1000))
print("kpis:", {k: stats[k] for k in ("season","matches","bets","win_rate","brier_model","brier_bookmaker","accuracy_1x2")})
print("flat:", stats["strategy_flat"])
print("kelly:", stats["strategy_kelly"])
print("leagues:", len(stats["by_league"]), "curve points:", len(stats["bankroll_curve"]))
print("by_market:", [(m["label"], m["bets"], m["roi_flat"]) for m in stats["by_market"]])
json.dumps(detail); json.dumps(stats); print("JSON OK")
