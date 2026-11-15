import json, sys
sys.path.insert(0, ".")
from backend.service import service

info = service.model_info()
print("MODEL:", info)

data = service.get_upcoming()
print("SOURCE:", data["slate"])
print("COUNT:", data["count"], "VALUE:", data["slate"].get("value_bets"))
for m in data["matches"][:3]:
    print(m["id"], m["league"], m["date"], m["time"], m["home_team"], "vs", m["away_team"])
    print("   probs", m["probabilities"], "elo", m["elo"])
    print("   odds", m["odds"], "best", m["best_value"])
json.dumps(data)  # verifie la serialisation
print("JSON OK")
