import requests
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

MLB_STATS_API = "https://statsapi.mlb.com/api/v1"

STAT_KEY_MAP = {
    "batter_total_bases": "totalBases",
    "batter_hits": "hits",
    "batter_runs_batted_in": "rbi",  # Updated to match new API key
    "batter_runs": "runs", 
    "batter_home_runs": "homeRuns",
    "batter_stolen_bases": "stolenBases",
    "batter_walks": "baseOnBalls",
    "batter_strikeouts": "strikeOuts",
    "batter_hits_runs_rbis": "combinedStats",
    "pitcher_strikeouts": "strikeOuts",
    "pitcher_hits_allowed": "hits",
    "pitcher_earned_runs": "earnedRuns",
    "pitcher_walks": "baseOnBalls",
    "pitcher_outs": "outs",
    "batter_fantasy_score": "fantasyPoints",
    "pitcher_fantasy_score": "fantasyPoints"
}

def get_player_id(player_name):
    """Get MLB player ID from name"""
    try:
        resp = requests.get(
            f"{MLB_STATS_API}/people/search", 
            params={"names": player_name},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        
        if data.get("people"):
            return data["people"][0]["id"]
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching player ID for {player_name}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting player ID for {player_name}: {e}")
        return None

def get_opponent_context(player_id):
    """Get opponent context for a player"""
    try:
        stats_resp = requests.get(
            f"{MLB_STATS_API}/people/{player_id}/stats",
            params={
                "stats": "gameLog",
                "season": "2025",
                "group": "hitting"
            },
            timeout=10
        )
        stats_resp.raise_for_status()
        data = stats_resp.json()
        
        stats = data.get("stats", [])
        if not stats:
            return None
        
        logs = stats[0].get("splits", [])
        if not logs:
            return None
        
        latest_game = logs[0]
        return (
            latest_game.get("team", {}).get("id"),
            latest_game.get("opponent", {}).get("id"),
            latest_game.get("pitcher", {}).get("hand", {}).get("code")
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching opponent context for player {player_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting opponent context for player {player_id}: {e}")
        return None

def get_fallback_hit_rate(player_name, stat_type, threshold):
    """Generate realistic fallback hit rate based on MLB averages"""
    fallback_rates = {
        # Batting stats - based on MLB averages
        "hits": 0.35,
        "totalBases": 0.40,
        "rbi": 0.25,
        "runs": 0.30,
        "homeRuns": 0.15,
        "stolenBases": 0.08,
        "baseOnBalls": 0.20,
        "strikeOuts": 0.65,
        "combinedStats": 0.50,
        "fantasyPoints": 0.45,
        
        # Pitching stats - based on MLB averages  
        "pitcher_strikeouts": 0.55,
        "pitcher_hits_allowed": 0.45,
        "pitcher_earned_runs": 0.35,
        "pitcher_walks": 0.20,
        "pitcher_outs": 0.75
    }
    
    # Use the MLB stat key for lookup
    mlb_stat_key = STAT_KEY_MAP.get(stat_type, stat_type)
    base_rate = fallback_rates.get(mlb_stat_key, 0.35)
    
    # Adjust for threshold difficulty
    if threshold >= 5:
        base_rate *= 0.65
    elif threshold >= 3:
        base_rate *= 0.80
    elif threshold >= 1.5:
        base_rate *= 0.90
    
    return {
        "player": player_name,
        "stat": mlb_stat_key,
        "threshold": threshold,
        "hit_rate": round(base_rate, 2),
        "sample_size": 10,
        "confidence": "Low",
        "note": "Fallback calculation based on MLB averages"
    }

def get_contextual_hit_rate(player_name, stat_type, threshold=1):
    """Get contextual hit rate for a player with comprehensive fallback support"""
    try:
        mlb_stat_key = STAT_KEY_MAP.get(stat_type)
        if not mlb_stat_key:
            # For unknown stat types, still provide fallback
            return get_fallback_hit_rate(player_name, stat_type, threshold)

        player_id = get_player_id(player_name)
        if not player_id:
            return get_fallback_hit_rate(player_name, stat_type, threshold)

        context = get_opponent_context(player_id)
        if not context:
            return get_fallback_hit_rate(player_name, stat_type, threshold)

        team_id, opponent_id, pitcher_hand = context

        # Determine group type based on stat type
        group_type = "pitching" if stat_type.startswith("pitcher_") else "hitting"
        
        # Get game logs
        logs_resp = requests.get(
            f"{MLB_STATS_API}/people/{player_id}/stats",
            params={
                "stats": "gameLog",
                "season": "2025",
                "group": group_type
            },
            timeout=10
        )
        logs_resp.raise_for_status()
        logs_data = logs_resp.json()
        
        logs = logs_data.get("stats", [{}])[0].get("splits", [])
        
        # Get recent games (last 10 games regardless of opponent for better sample size)
        recent = logs[:10] if logs else []

        if len(recent) < 2:
            return get_fallback_hit_rate(player_name, stat_type, threshold)

        # Count games where player exceeded threshold
        over_count = 0
        for game in recent:
            game_stat = game.get("stat", {})
            
            # Handle special composite stats
            if mlb_stat_key == "combinedStats":
                # H+R+RBI calculation
                stat_value = (game_stat.get("hits", 0) + 
                            game_stat.get("runs", 0) + 
                            game_stat.get("rbi", 0))
            elif mlb_stat_key == "fantasyPoints":
                # Basic fantasy scoring
                hits = game_stat.get("hits", 0)
                doubles = game_stat.get("doubles", 0)
                triples = game_stat.get("triples", 0)
                hrs = game_stat.get("homeRuns", 0)
                singles = max(0, hits - doubles - triples - hrs)
                
                stat_value = (singles * 1 + doubles * 2 + triples * 3 + hrs * 4 + 
                            game_stat.get("rbi", 0) + game_stat.get("runs", 0) + 
                            game_stat.get("stolenBases", 0) * 2)
            else:
                stat_value = game_stat.get(mlb_stat_key, 0)
            
            if stat_value >= threshold:
                over_count += 1
        
        hit_rate = round(over_count / len(recent), 2) if recent else 0.0
        confidence = "High" if hit_rate >= 0.6 else "Medium" if hit_rate >= 0.4 else "Low"

        return {
            "player": player_name,
            "stat": mlb_stat_key,
            "threshold": threshold,
            "hit_rate": hit_rate,
            "sample_size": len(recent),
            "confidence": confidence,
            "pitcher_hand": pitcher_hand,
            "opponent_id": opponent_id
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching contextual hit rate for {player_name}: {e}")
        return get_fallback_hit_rate(player_name, stat_type, threshold)
    except Exception as e:
        logger.error(f"Unexpected error in contextual hit rate for {player_name}: {e}")
        return get_fallback_hit_rate(player_name, stat_type, threshold)