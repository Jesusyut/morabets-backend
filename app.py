from flask import Flask, jsonify, request
from flask_cors import CORS
import json
from redis import Redis
from probability import implied_probability
from combo_optimizer import generate_2_leg_combos

app = Flask(__name__)
CORS(app)

redis = Redis(host='localhost', port=6379, db=0)

def cache_get(key):
    try:
        value = redis.get(key)
        if value:
            return json.loads(value)
    except:
        return None

@app.route("/api/positive_ev_props")
def positive_ev_props():
    props = cache_get("mlb_enriched_props")
    if not props:
        return jsonify({"error": "No enriched props available"}), 503
    ev_props = [p for p in props if p.get("edge", 0) > 0.05]
    return jsonify(ev_props)

@app.route("/api/smart_combos")
def smart_combos():
    props = cache_get("mlb_enriched_props")
    if not props:
        return jsonify({"error": "No props available"}), 503
    combos = generate_2_leg_combos(props)
    return jsonify(combos)

@app.route("/")
def index():
    return jsonify({"message": "Mora Bets Backend Running"})