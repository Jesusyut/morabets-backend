import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

MLB_STATS_API = "https://statsapi.mlb.com/api/v1"

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
    except Exception as e:
        logger.error(f"Error fetching player ID for {player_name}: {e}")
        return None

def calculate_fantasy_points(game_stats):
    """Calculate fantasy points based on standard scoring system"""
    try:
        # Standard fantasy scoring
        points = 0
        
        # Hitting stats
        points += game_stats.get("hits", 0) * 3
        points += game_stats.get("doubles", 0) * 2  # +2 bonus for doubles
        points += game_stats.get("triples", 0) * 5  # +5 bonus for triples
        points += game_stats.get("homeRuns", 0) * 4  # +4 bonus for home runs
        points += game_stats.get("runs", 0) * 2
        points += game_stats.get("rbi", 0) * 2
        points += game_stats.get("stolenBases", 0) * 5
        points += game_stats.get("baseOnBalls", 0) * 2
        points += game_stats.get("hitByPitch", 0) * 2
        
        return points
    except Exception as e:
        logger.error(f"Error calculating fantasy points: {e}")
        return 0

def get_fantasy_hit_rate(player_name, threshold=6):
    """Get fantasy hit rate for a player based on real MLB stats"""
    try:
        player_id = get_player_id(player_name)
        if not player_id:
            return {"error": f"Player '{player_name}' not found"}

        # Get game logs
        logs_resp = requests.get(
            f"{MLB_STATS_API}/people/{player_id}/stats",
            params={
                "stats": "gameLog",
                "season": "2025",
                "group": "hitting"
            },
            timeout=10
        )
        logs_resp.raise_for_status()
        logs_data = logs_resp.json()
        
        logs = logs_data.get("stats", [{}])[0].get("splits", [])
        
        if not logs:
            return {
                "error": "No recent game data found",
                "player": player_name,
                "threshold": threshold
            }

        # Calculate fantasy points for each game
        games_over_threshold = 0
        total_games = 0
        
        for game in logs[:15]:  # Last 15 games
            game_stats = game.get("stat", {})
            fantasy_points = calculate_fantasy_points(game_stats)
            
            if fantasy_points >= threshold:
                games_over_threshold += 1
            total_games += 1
        
        hit_rate = round(games_over_threshold / total_games, 2) if total_games > 0 else 0.0
        
        return {
            "player": player_name,
            "threshold": threshold,
            "fantasy_hit_rate": hit_rate,
            "sample_size": total_games,
            "games_over": games_over_threshold
        }
        
    except Exception as e:
        logger.error(f"Error calculating fantasy hit rate for {player_name}: {e}")
        return {"error": f"Failed to calculate fantasy hit rate: {str(e)}"}
