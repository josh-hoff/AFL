"""
Fetch and parse the Arizona Fall League schedule for any season.

This is the season-agnostic version of the schedule tool: point it at any
year and it fetches, parses, and saves that season's data into its own
folder -- 2025, 2026, 2027, and beyond all work the same way, with no code
changes needed for a new season.

Usage:
    python fetch_afl_schedule.py 2025
    python fetch_afl_schedule.py 2026 --output-dir data

    # If you already have a saved schedule JSON and don't want to re-fetch:
    python fetch_afl_schedule.py 2025 --skip-fetch schedule.json

Requires the 'requests' library (install with: pip install requests)
unless using --skip-fetch, in which case it's not needed.

Output (for season 2025, with default --output-dir):
    data/2025/schedule_raw.json   (the raw API response, kept for reference)
    data/2025/schedule.csv        (the cleaned, parsed schedule)
"""

import argparse
import csv
import json
import os
from datetime import datetime, timedelta, timezone

AFL_SPORT_ID = 17
AFL_LEAGUE_ID = 119
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

# Arizona does not observe daylight saving time, so it's always UTC-7.
ARIZONA_TZ = timezone(timedelta(hours=-7))

GAME_TYPE_LABELS = {
    "R": "Regular Season",
    "A": "Fall Stars Game",
    "D": "First Round",
    "L": "Semifinal",
    "W": "Championship",
}


def fetch_schedule(season):
    """Pull the raw schedule JSON for a given AFL season from the Stats API."""
    import requests  # imported here so --skip-fetch never requires it

    params = {"sportId": AFL_SPORT_ID, "leagueId": AFL_LEAGUE_ID, "season": season}
    resp = requests.get(SCHEDULE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_schedule(data):
    """Turn a raw Stats API schedule response into a list of clean game dicts."""
    games = []
    for date_entry in data.get("dates", []):
        for game in date_entry.get("games", []):
            games.append(_parse_game(game))

    games.sort(key=lambda g: g["_sort_key"])
    for g in games:
        del g["_sort_key"]
    return games


def _parse_utc(iso_str):
    return datetime.strptime(iso_str, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def _fmt_mmdd(dt):
    """M/D format without relying on platform-specific strftime flags."""
    return f"{dt.month}/{dt.day}"


def _parse_game(game):
    game_pk = game.get("gamePk")
    game_type_code = game.get("gameType", "")

    original_utc_str = game.get("gameDate")
    reschedule_utc_str = game.get("rescheduleDate")
    is_rescheduled = reschedule_utc_str is not None

    original_utc_dt = _parse_utc(original_utc_str)
    original_az_dt = original_utc_dt.astimezone(ARIZONA_TZ)

    actual_utc_dt = _parse_utc(reschedule_utc_str) if is_rescheduled else original_utc_dt
    actual_az_dt = actual_utc_dt.astimezone(ARIZONA_TZ)

    if is_rescheduled:
        date_display = (
            f"{actual_az_dt.strftime('%Y-%m-%d')} "
            f"(originally {_fmt_mmdd(original_az_dt)})"
        )
    else:
        date_display = actual_az_dt.strftime("%Y-%m-%d")

    teams = game.get("teams", {})
    away_team = teams.get("away", {}).get("team", {}).get("name", "TBD")
    home_team = teams.get("home", {}).get("team", {}).get("name", "TBD")

    venue = game.get("venue", {}).get("name", "Unknown")
    venue_id = game.get("venue", {}).get("id")
    status_info = game.get("status", {})
    status = status_info.get("detailedState", "")
    status_reason = status_info.get("reason", "")
    description = game.get("description", "")

    return {
        "date": date_display,
        "time_az": actual_az_dt.strftime("%I:%M %p").lstrip("0"),
        "away_team": away_team,
        "home_team": home_team,
        "venue": venue,
        "venue_id": venue_id,
        "game_pk": game_pk,
        "game_type": GAME_TYPE_LABELS.get(game_type_code, game_type_code),
        "status": status,
        "status_reason": status_reason,
        "rescheduled": "Y" if is_rescheduled else "N",
        "original_date": original_az_dt.strftime("%Y-%m-%d") if is_rescheduled else "",
        "description": description,
        "_sort_key": actual_utc_dt,
    }


def write_csv(games, path):
    if not games:
        return
    fieldnames = [k for k in games[0].keys() if not k.startswith("_")]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for g in games:
            writer.writerow({k: g[k] for k in fieldnames})


def main():
    parser = argparse.ArgumentParser(
        description="Fetch and parse the AFL schedule for a given season."
    )
    parser.add_argument("season", type=int, help="Season year, e.g. 2025, 2026, 2027")
    parser.add_argument(
        "--output-dir",
        default="data",
        help="Base folder to organize output under (default: data)",
    )
    parser.add_argument(
        "--skip-fetch",
        metavar="JSON_FILE",
        help="Skip the live API call and parse an existing schedule JSON file instead",
    )
    args = parser.parse_args()

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)

    if args.skip_fetch:
        with open(args.skip_fetch, "r") as f:
            raw = json.load(f)
    else:
        print(f"Fetching {args.season} AFL schedule from the MLB Stats API...")
        raw = fetch_schedule(args.season)

    raw_path = os.path.join(season_dir, "schedule_raw.json")
    with open(raw_path, "w") as f:
        json.dump(raw, f, indent=2)

    games = parse_schedule(raw)
    csv_path = os.path.join(season_dir, "schedule.csv")
    write_csv(games, csv_path)

    print(f"Parsed {len(games)} games for the {args.season} season.")
    print(f"  Raw JSON saved to: {raw_path}")
    print(f"  Schedule CSV saved to: {csv_path}")


if __name__ == "__main__":
    main()
