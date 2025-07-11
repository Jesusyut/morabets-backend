from flask import Flask, jsonify
from redis import Redis
import os

app = Flask(__name__)

try:
    redis_url = os.environ["REDIS_URL"]
    redis = Redis.from_url(redis_url)
except KeyError:
    raise RuntimeError("REDIS_URL environment variable is not set.")

@app.route("/")
def index():
    try:
        redis.incr("hits")
        hits = int(redis.get("hits"))
    except Exception as e:
        return jsonify({"error": "Failed to connect to Redis", "details": str(e)}), 500

    return jsonify({"message": "Welcome to Mora Bets!", "hits": hits})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
