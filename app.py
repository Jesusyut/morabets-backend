from flask import Flask, jsonify
from redis import Redis
import os
import json
from apscheduler.schedulers.background import BackgroundScheduler
from odds_api import parse_game_data

app = Flask(__name__)

redis_url = os.environ["REDIS_URL"]
redis = Redis.from_url(redis_url)

@app.route("/")
def index():
    redis.incr("hits")
    return jsonify({"message": "Welcome to Mora Bets!", "hits": int(redis.get("hits"))})

@app.route("/odds")
def get_odds():
    cached = redis.get("mlb_odds")
    if cached:
        return jsonify(json.loads(cached))
    return jsonify({"error": "Odds not cached yet"}), 503

def update_odds():
    odds_data = parse_game_data()
    redis.set("mlb_odds", json.dumps(odds_data))
    print("[INFO] Updated MLB odds cache.")

scheduler = BackgroundScheduler()
scheduler.add_job(update_odds, 'interval', hours=2)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
