
from flask import Flask, jsonify
from redis import Redis
import os

app = Flask(__name__)

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
redis = Redis.from_url(redis_url)

@app.route("/")
def index():
    redis.incr("hits")
    return jsonify({"message": "Welcome to Mora Bets!", "hits": int(redis.get("hits"))})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
