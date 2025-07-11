import requests
import os

ODDS_API_KEY = os.environ.get("ODDS_API_KEY")
ODDS_URL = "https://api.the-odds-api.com/v4/sports/baseball_mlb/odds/"

def parse_game_data():
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "h2h,spreads,totals",
        "oddsFormat": "decimal"
    }
    try:
        response = requests.get(ODDS_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        results = []

        for game in data:
            game_info = {
                "teams": game.get("teams"),
                "commence_time": game.get("commence_time"),
                "bookmakers": []
            }
            for bm in game.get("bookmakers", []):
                bookmaker_data = {
                    "title": bm.get("title"),
                    "markets": []
                }
                for market in bm.get("markets", []):
                    market_data = {
                        "key": market.get("key"),
                        "outcomes": market.get("outcomes", [])
                    }
                    bookmaker_data["markets"].append(market_data)
                game_info["bookmakers"].append(bookmaker_data)
            results.append(game_info)

        return results
    except Exception as e:
        print(f"[ERROR] Failed to fetch odds: {e}")
        return []
