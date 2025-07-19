import requests
from datetime import datetime
import logging
import json
import time

logger = logging.getLogger(__name__)

MLB_STATS_API = "https://statsapi.mlb.com/api/v1"

# In-memory cache for player IDs to reduce API calls
player_id_cache = {}
player_context_cache = {}
cache_timeout = 3600  # 1 hour cache timeout

def get_player_id(player_name):
    """Get MLB player ID from name with caching"""
    # Check cache first
    cache_key = f"player_id_{player_name}"
    cached_data = player_id_cache.get(cache_key)
    if cached_data and (time.time() - cached_data['timestamp']) < cache_timeout:
        return cached_data['player_id']
    
    try:
        response = requests.get(
            f"{MLB_STATS_API}/people/search", 
            params={"names": player_name},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        player_id = None
        if data.get("people"):
            player_id = data["people"][0]["id"]
        
        # Cache the result
        player_id_cache[cache_key] = {
            'player_id': player_id,
            'timestamp': time.time()
        }
        
        return player_id
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching player ID for {player_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting player ID for {player_name}: {e}")
        return None

def get_opponent_context(player_id):
    """Get current opponent context for a player"""
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        schedule_resp = requests.get(
            f"{MLB_STATS_API}/people/{player_id}/stats",
            params={
                "stats": "gameLog",
                "season": "2025",
                "group": "hitting"
            },
            timeout=10
        )
        schedule_resp.raise_for_status()
        data = schedule_resp.json()
        
        logs = data.get("stats", [{}])[0].get("splits", [])
        
        for log in logs:
            if log.get("date") == today:
                return (
                    log.get("team", {}).get("id"),
                    log.get("opponent", {}).get("id"),
                    log.get("pitcher", {}).get("hand", {}).get("code")
                )
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching opponent context for player {player_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting opponent context for player {player_id}: {e}")
        return None

def get_stat_mapping(stat_type):
    """Map prop bet stat types to MLB Stats API field names"""
    mapping = {
        # Batting stats
        "batter_hits": "hits",
        "batter_rbi": "rbi", 
        "batter_runs": "runs",
        "batter_home_runs": "homeRuns",
        "batter_total_bases": "totalBases",
        "batter_stolen_bases": "stolenBases",
        "batter_walks": "baseOnBalls",
        "batter_strikeouts": "strikeOuts",
        "batter_hits_runs_rbis": "hits_runs_rbis",  # Custom calculation
        "batter_fantasy_score": "fantasy_score",  # Custom calculation
        
        # Pitching stats
        "pitcher_strikeouts": "strikeOuts",
        "pitcher_hits_allowed": "hits",
        "pitcher_earned_runs": "earnedRuns",
        "pitcher_walks": "baseOnBalls",
        "pitcher_outs": "outs",
        
        # Legacy mappings
        "hits": "hits",
        "rbi": "rbi",
        "runs": "runs",
        "homeRuns": "homeRuns",
        "totalBases": "totalBases",
        "stolenBases": "stolenBases",
        "strikeOuts": "strikeOuts",
        "baseOnBalls": "baseOnBalls"
    }
    return mapping.get(stat_type, stat_type)

def calculate_custom_stat(game_data, stat_type):
    """Calculate custom composite stats"""
    if stat_type == "hits_runs_rbis":
        return game_data.get("hits", 0) + game_data.get("runs", 0) + game_data.get("rbi", 0)
    elif stat_type == "fantasy_score":
        # Basic fantasy scoring: 1B=1, 2B=2, 3B=3, HR=4, RBI=1, R=1, SB=2, BB=1
        hits = game_data.get("hits", 0)
        doubles = game_data.get("doubles", 0)
        triples = game_data.get("triples", 0)
        hrs = game_data.get("homeRuns", 0)
        singles = hits - doubles - triples - hrs
        
        return (singles * 1 + doubles * 2 + triples * 3 + hrs * 4 + 
                game_data.get("rbi", 0) + game_data.get("runs", 0) + 
                game_data.get("stolenBases", 0) * 2 + game_data.get("baseOnBalls", 0))
    return 0

def get_confidence_level(hit_rate, sample_size):
    """Determine confidence level based on hit rate and sample size"""
    if sample_size < 5:
        return "Low"
    elif hit_rate >= 0.60:
        return "High"
    elif hit_rate >= 0.50:
        return "Medium"
    else:
        return "Low"

def get_fallback_hit_rate(player_name, stat_type, threshold):
    """Generate fallback hit rate using basic heuristics"""
    try:
        # Basic fallback rates based on stat type and threshold
        fallback_rates = {
            "batter_hits": 0.35,
            "batter_rbi": 0.25,
            "batter_runs": 0.30,
            "batter_home_runs": 0.15,
            "batter_total_bases": 0.40,
            "batter_stolen_bases": 0.10,
            "batter_walks": 0.20,
            "batter_strikeouts": 0.60,
            "batter_hits_runs_rbis": 0.45,
            "batter_fantasy_score": 0.50,
            "pitcher_strikeouts": 0.55,
            "pitcher_hits_allowed": 0.45,
            "pitcher_earned_runs": 0.30,
            "pitcher_walks": 0.25,
            "pitcher_outs": 0.70,
            # Legacy mappings
            "hits": 0.35,
            "rbi": 0.25,
            "runs": 0.30,
            "homeRuns": 0.15,
            "totalBases": 0.40,
            "stolenBases": 0.10,
            "strikeOuts": 0.60,
            "baseOnBalls": 0.20
        }
        
        base_rate = fallback_rates.get(stat_type, 0.30)
        
        # Adjust based on threshold (higher threshold = lower hit rate)
        if threshold >= 5:
            base_rate *= 0.7
        elif threshold >= 3:
            base_rate *= 0.85
        elif threshold >= 1.5:
            base_rate *= 0.95
        
        return {
            "player": player_name,
            "stat": stat_type,
            "threshold": threshold,
            "hit_rate": round(base_rate, 2),
            "sample_size": 10,  # Assumed sample size for fallback
            "confidence": "Low",
            "note": "Fallback calculation - limited data available"
        }
    except Exception as e:
        logger.error(f"Error in fallback hit rate calculation: {e}")
        return {
            "player": player_name,
            "stat": stat_type,
            "threshold": threshold,
            "hit_rate": 0.30,  # Default fallback
            "sample_size": 0,
            "confidence": "Unknown",
            "error": "Fallback calculation failed"
        }

def get_contextual_hit_rate(player_name, stat_type, threshold=1):
    """Get contextual hit rate with comprehensive stat type support and fallback calculations"""
    try:
        player_id = get_player_id(player_name)
        if not player_id:
            return get_fallback_hit_rate(player_name, stat_type, threshold)

        context = get_opponent_context(player_id)
        if not context:
            return get_fallback_hit_rate(player_name, stat_type, threshold)
        
        team_id, opponent_id, pitcher_hand = context

        # Determine if it's a pitching or batting stat
        is_pitching_stat = stat_type.startswith("pitcher_")
        group = "pitching" if is_pitching_stat else "hitting"

        # Get game logs
        logs_resp = requests.get(
            f"{MLB_STATS_API}/people/{player_id}/stats",
            params={
                "stats": "gameLog",
                "season": "2025",
                "group": group
            },
            timeout=10
        )
        logs_resp.raise_for_status()
        logs_data = logs_resp.json()
        
        logs = logs_data.get("stats", [{}])[0].get("splits", [])

        # Filter for contextual games (same opponent and pitcher handedness)
        filtered = [
            game for game in logs[:10]
            if (game.get("opponent", {}).get("id") == opponent_id and
                game.get("pitcher", {}).get("hand", {}).get("code") == pitcher_hand)
        ]

        if not filtered:
            return get_fallback_hit_rate(player_name, stat_type, threshold)

        # Map stat type to API field name
        api_field = get_stat_mapping(stat_type)
        
        # Count games where player exceeded threshold
        over_count = 0
        for game in filtered:
            game_stat = game.get("stat", {})
            if api_field in ["hits_runs_rbis", "fantasy_score"]:
                stat_value = calculate_custom_stat(game_stat, api_field)
            else:
                stat_value = game_stat.get(api_field, 0)
            
            if stat_value >= threshold:
                over_count += 1
        
        hit_rate = round(over_count / len(filtered), 2) if filtered else 0.0

        return {
            "player": player_name,
            "stat": stat_type,
            "threshold": threshold,
            "hit_rate": hit_rate,
            "sample_size": len(filtered),
            "pitcher_hand": pitcher_hand,
            "opponent_id": opponent_id,
            "confidence": get_confidence_level(hit_rate, len(filtered))
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching contextual hit rate for {player_name}: {e}")
        return get_fallback_hit_rate(player_name, stat_type, threshold)
    except Exception as e:
        logger.error(f"Unexpected error in contextual hit rate for {player_name}: {e}")
        return get_fallback_hit_rate(player_name, stat_type, threshold)

def get_fantasy_hit_rate(player_name, threshold=6):
    """Get fantasy hit rate using total bases as proxy"""
    return get_contextual_hit_rate(player_name, "totalBases", threshold)