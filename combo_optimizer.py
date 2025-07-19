from itertools import combinations

def generate_2_leg_combos(props):
    valid_props = [p for p in props if p.get("edge", 0) > 0.05]
    combos = []

    for a, b in combinations(valid_props, 2):
        combo = {
            "players": [a["player"], b["player"]],
            "props": [a["label"], b["label"]],
            "edges": [round(a["edge"] * 100, 2), round(b["edge"] * 100, 2)],
            "avg_edge": round(((a["edge"] + b["edge"]) / 2) * 100, 2)
        }
        combos.append(combo)

    return sorted(combos, key=lambda x: x["avg_edge"], reverse=True)[:15]