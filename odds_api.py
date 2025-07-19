import requests
from datetime import datetime, timedelta
import os
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextual import get_contextual_hit_rate
from fantasy import get_fantasy_hit_rate

logger = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
ODDS_API_KEY = os.getenv("ODDS_API_KEY")

# Preferred sportsbooks for filtering
PREFERRED_SPORTSBOOKS = ["draftkings", "fanduel", "betmgm"]
VALID_BOOKS = {"DraftKings", "FanDuel", "BetMGM"}

def parse_game_data():
    """Fetch moneylines with preferred sportsbooks first, fallback to all if needed"""
    now = datetime.utcnow()
    future = now + timedelta(hours=48)
    start_time = now.replace(microsecond=0).isoformat() + "Z"
    end_time = future.replace(microsecond=0).isoformat() + "Z"

    if not ODDS_API_KEY:
        print("[ERROR] ODDS_API_KEY is not set")
        return []

    # Try preferred sportsbooks first
    try:
        print(f"[DEBUG] Fetching moneylines from preferred sportsbooks: {PREFERRED_SPORTSBOOKS}")
        response = requests.get(
            f"{BASE_URL}/sports/baseball_mlb/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
                "commenceTimeFrom": start_time,
                "commenceTimeTo": end_time,
                "bookmakers": ",".join(PREFERRED_SPORTSBOOKS)
            },
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        print(f"[INFO] Retrieved {len(data)} moneyline matchups from preferred sportsbooks")
        
        # If we got good data, return it
        if data and len(data) > 0:
            return data
        else:
            print("[WARNING] No moneylines from preferred sportsbooks, falling back to all sportsbooks")
            
    except Exception as e:
        print(f"[ERROR] Failed to fetch odds from preferred sportsbooks: {e}, falling back to all sportsbooks")

    # Fallback to all sportsbooks
    try:
        print("[DEBUG] Fetching moneylines from all sportsbooks")
        response = requests.get(
            f"{BASE_URL}/sports/baseball_mlb/odds",
            params={
                "apiKey": ODDS_API_KEY,
                "regions": "us",
                "markets": "h2h",
                "oddsFormat": "american",
                "commenceTimeFrom": start_time,
                "commenceTimeTo": end_time
            },
            timeout=20
        )
        response.raise_for_status()
        data = response.json()
        print(f"[INFO] Retrieved {len(data)} moneyline matchups from all sportsbooks")
        return data
    except Exception as e:
        print(f"[ERROR] Failed to fetch odds from all sportsbooks: {e}")
        return []

def fetch_player_props():
    """Fetch player props with preferred sportsbooks first, fallback to all if needed"""
    now = datetime.utcnow()
    future = now + timedelta(hours=48)
    start_time = now.replace(microsecond=0).isoformat() + "Z"
    end_time = future.replace(microsecond=0).isoformat() + "Z"

    if not ODDS_API_KEY:
        print("[ERROR] ODDS_API_KEY is not set")
        return []

    try:
        event_resp = requests.get(
            f"{BASE_URL}/sports/baseball_mlb/events",
            params={
                "apiKey": ODDS_API_KEY,
                "commenceTimeFrom": start_time,
                "commenceTimeTo": end_time
            },
            timeout=20
        )
        event_resp.raise_for_status()
        events = event_resp.json()
        print(f"[INFO] Found {len(events)} events")
    except Exception as e:
        print(f"[ERROR] Failed to fetch MLB events: {e}")
        return []

    props = []
    print(f"[DEBUG] Starting prop collection for {len(events)} events")
    
    # Define targeted markets only (7 markets total)
    markets_batch_1 = ["batter_hits", "batter_home_runs", "batter_total_bases"]
    markets_batch_2 = ["pitcher_strikeouts", "pitcher_earned_runs", "pitcher_outs", "pitcher_hits_allowed"]
    
    print(f"[DEBUG] Using targeted markets: {markets_batch_1 + markets_batch_2}")
    
    all_markets = [markets_batch_1, markets_batch_2]

    for event in events:
        eid = event.get("id")
        if not eid:
            continue

        # Process each market batch to avoid rate limiting
        for batch_idx, markets in enumerate(all_markets):
            try:
                # Add delay between batches to respect rate limits
                if batch_idx > 0:
                    time.sleep(1)
                
                odds_resp = requests.get(
                    f"{BASE_URL}/sports/baseball_mlb/events/{eid}/odds",
                    params={
                        "apiKey": ODDS_API_KEY,
                        "regions": "us",
                        "markets": ",".join(markets),
                        "oddsFormat": "american",
                        "bookmakers": ",".join(PREFERRED_SPORTSBOOKS)
                    },
                    timeout=20
                )
                odds_resp.raise_for_status()
                data = odds_resp.json()
                
                # Log successful market response
                if data.get("bookmakers"):
                    successful_markets = [m.get('key') for m in data.get('bookmakers', [])[0].get('markets', [])]
                    print(f"[DEBUG] Event {eid} batch {batch_idx} fetched props for markets: {successful_markets}")
                
                for book in data.get("bookmakers", []):
                    book_title = book.get("title", "Unknown")
                    
                    # Filter to only valid sportsbooks
                    if book_title not in VALID_BOOKS:
                        continue
                    
                    for market in book.get("markets", []):
                        stat = market.get("key")
                        for outcome in market.get("outcomes", []):
                            player = outcome.get("description") or outcome.get("name")
                            price = outcome.get("price")
                            point = outcome.get("point")

                            if player and price is not None:
                                props.append({
                                    "player": player,
                                    "stat": stat,
                                    "line": point,
                                    "odds": price,
                                    "bookmaker": book_title
                                })
                                
            except Exception as e:
                print(f"[ERROR] Failed to fetch props for event {eid} batch {batch_idx}: {e}")
                continue
        
        print(f"[DEBUG] Event {eid}: Collected {len(props)} props so far")

    print(f"[INFO] Final count of player props: {len(props)}")
    print(f"[DEBUG] Final props fetched: {len(props)}")
    print(f"🔍 DEBUG: Fetched {len(props)} raw props from API")
    
    # Debug: Show stat type breakdown
    stat_counts = {}
    for prop in props:
        stat = prop.get('stat', 'unknown')
        stat_counts[stat] = stat_counts.get(stat, 0) + 1
    
    print(f"[DEBUG] Props by stat type: {stat_counts}")
    return props

def deduplicate_props(props):
    """Deduplicate props: keep one prop per unique player+stat+line combination"""
    unique_props = {}
    
    for prop in props:
        # Create unique key for each player+stat+line combination
        key = f"{prop['player']}_{prop['stat']}_{prop['line']}"
        
        # If this is the first occurrence or has better odds, keep it
        if key not in unique_props:
            unique_props[key] = prop
        else:
            # Keep the prop with better odds (higher absolute value for positive odds)
            current_odds = unique_props[key]['odds']
            new_odds = prop['odds']
            
            # For positive odds, higher is better; for negative odds, closer to 0 is better
            if (current_odds > 0 and new_odds > current_odds) or (current_odds < 0 and new_odds > current_odds):
                unique_props[key] = prop
    
    deduplicated = list(unique_props.values())
    print(f"[INFO] Deduplication: {len(props)} props -> {len(deduplicated)} unique props")
    return deduplicated

def enrich_prop(prop):
    """Enrich a single prop with contextual and fantasy hit rates - with robust error handling"""
    try:
        # Get contextual hit rate with fallback
        contextual = None
        try:
            contextual = get_contextual_hit_rate(
                prop["player"], 
                stat_type=prop["stat"], 
                threshold=prop["line"]
            )
        except Exception as e:
            print(f"[WARN] Contextual hit rate error for {prop['player']}: {e}")
            contextual = {
                "player": prop["player"],
                "stat": prop["stat"],
                "threshold": prop["line"],
                "hit_rate": None,
                "confidence": "Unknown",
                "error": f"Contextual calculation failed: {str(e)}"
            }
        
        # Ensure we always have a contextual object
        if not contextual or contextual.get("error"):
            contextual = {
                "player": prop["player"],
                "stat": prop["stat"],
                "threshold": prop["line"],
                "hit_rate": 0.30,  # Default fallback
                "confidence": "Low",
                "note": "Using fallback hit rate"
            }
        
        # Get fantasy hit rate with fallback
        fantasy = None
        try:
            fantasy = get_fantasy_hit_rate(prop["player"], threshold=prop["line"])
        except Exception as e:
            print(f"[WARN] Fantasy hit rate error for {prop['player']}: {e}")
            fantasy = {
                "player": prop["player"],
                "threshold": prop["line"],
                "hit_rate": 0.35,  # Default fallback
                "confidence": "Low",
                "note": "Using fallback fantasy rate"
            }
        
        # Ensure we always have a fantasy object
        if not fantasy:
            fantasy = {
                "player": prop["player"],
                "threshold": prop["line"],
                "hit_rate": 0.35,  # Default fallback
                "confidence": "Low",
                "note": "Using fallback fantasy rate"
            }
        
        # Return enriched prop
        return {
            **prop,
            "contextual_hit_rate": contextual,
            "fantasy_hit_rate": fantasy,
            "enriched": True
        }
    except Exception as e:
        print(f"[ERROR] Failed to enrich prop for {prop.get('player', 'Unknown')}: {e}")
        # Return original prop with error indication
        return {
            **prop,
            "contextual_hit_rate": {
                "hit_rate": 0.30,
                "confidence": "Low",
                "error": "Enrichment failed"
            },
            "fantasy_hit_rate": {
                "hit_rate": 0.35,
                "confidence": "Low",
                "error": "Enrichment failed"
            },
            "enriched": False,
            "error": str(e)
        }

def enrich_player_props(props):
    """Enrich player props with contextual and fantasy hit rates using parallel processing"""
    if not props:
        return []
    
    print(f"[INFO] Starting enrichment for {len(props)} props")
    
    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=10) as executor:
        enriched_props = list(executor.map(enrich_prop, props))
    
    # Count successful enrichments
    successful_enrichments = sum(1 for prop in enriched_props if prop.get("enriched", False))
    print(f"[INFO] Enrichment complete: {successful_enrichments}/{len(props)} props successfully enriched")
    
    return enriched_props