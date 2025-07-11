def calculate_probability(values, threshold):
    over_count = sum(1 for v in values if v > threshold)
    return over_count / len(values) if values else 0.0

def calculate_parlay_probability(probabilities, payout_multiplier):
    from functools import reduce
    import math

    implied_prob = round((1 / payout_multiplier) * 100, 2)
    combined_prob = reduce(lambda x, y: x * y, probabilities)
    edge = round((combined_prob * 100) - implied_prob, 2)

    return {
        "combined_probability": round(combined_prob * 100, 2),
        "implied_probability": implied_prob,
        "edge": edge
    }
