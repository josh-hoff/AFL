"""
Parse the MLB Stats API schedule response for the Arizona Fall League
(sportId=17, leagueId=119) into a clean list of games.

Usage:
    python parse_afl_schedule.py schedule.json afl_schedule_2026.csv

Input:
    A JSON file containing the raw response from:
    https://statsapi.mlb.com/api/v1/schedule?sportId=17&leagueId=119&season=2026

Output:
    A CSV with one row per game: date, time (Arizona local), away team,
    home team, venue, gamePk, game type, and status.
"""

import csv
import json
import sys
from datetime import datetime, timedelta, timezone

# Arizona does not observe daylight saving time, so it's always UTC-7.
ARIZONA_TZ = timezone(timedelta(hours=-7))

# Game type codes used by the Stats API.
GAME_TYPE_LABELS = {
    "R": "Regular Season",
    "A": "Fall Stars Game",
    "D": "First Round",
    "L": "Semifinal",
    "W": "Championship",
}


def parse_schedule(json_path, output_csv=None):
    """Parse a Stats API schedule JSON file into a list of game dicts."""
    with open(json_path, "r") as f:
        data = json.load(f)

    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            games.append(_parse_game(game))

    # Sort chronologically by the actual UTC start time, not the string date,
    # since a night game can spill into the next UTC calendar day.
    games.sort(key=lambda g: g["_sort_key"])
    for g in games:
        del g["_sort_key"]

    if output_csv:
        _write_csv(games, output_csv)

    return games


def _parse_game(game):
    game_pk = game.get("gamePk")
    game_type_code = game.get("gameType", "")
    utc_str = game.get("gameDate")  # e.g. "2026-10-03T19:30:00Z"
    utc_dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    az_dt = utc_dt.astimezone(ARIZONA_TZ)

    teams = game.get("teams", {})
    away_team = teams.get("away", {}).get("team", {}).get("name", "TBD")
    home_team = teams.get("home", {}).get("team", {}).get("name", "TBD")

    venue = game.get("venue", {}).get("name", "Unknown")
    venue_id = game.get("venue", {}).get("id")
    status = game.get("status", {}).get("detailedState", "")
    description = game.get("description", "")

    return {
        "date": az_dt.strftime("%Y-%m-%d"),
        "time_az": az_dt.strftime("%I:%M %p").lstrip("0"),
        "away_team": away_team,
        "home_team": home_team,
        "venue": venue,
        "venue_id": venue_id,
        "game_pk": game_pk,
        "game_type": GAME_TYPE_LABELS.get(game_type_code, game_type_code),
        "status": status,
        "description": description,
        "_sort_key": utc_dt,
    }


def _write_csv(games, output_csv):
    if not games:
        return
    fieldnames = [k for k in games[0].keys() if not k.startswith("_")]
    with open(output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in games:
            writer.writerow({k: g[k] for k in fieldnames})


if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "schedule.json"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "afl_schedule.csv"
    parsed = parse_schedule(in_path, out_path)
    print(f"Parsed {len(parsed)} games -> {out_path}")
