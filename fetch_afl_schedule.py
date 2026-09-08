import argparse
import csv
import json
import os
import re
from datetime import datetime, timedelta, timezone

AFL_SPORT_ID = 17
AFL_LEAGUE_ID = 119
SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule"

ARIZONA_TZ = timezone(timedelta(hours=-7))

GAME_TYPE_LABELS = {
    "R": "Regular Season",
    "A": "Fall Stars Game",
    "D": "First Round",
    "L": "Semifinal",
    "W": "Championship",
}


def fetch_schedule(season):
    import requests

    params = {"sportId": AFL_SPORT_ID, "leagueId": AFL_LEAGUE_ID, "season": season}
    resp = requests.get(SCHEDULE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_schedule(data):
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
    away_info = teams.get("away", {})
    home_info = teams.get("home", {})
    away_team = away_info.get("team", {}).get("name", "TBD")
    home_team = home_info.get("team", {}).get("name", "TBD")
    away_record = away_info.get("leagueRecord", {})
    home_record = home_info.get("leagueRecord", {})
    away_score = away_info.get("score", "")
    home_score = home_info.get("score", "")

    venue = game.get("venue", {}).get("name", "Unknown")
    venue_id = game.get("venue", {}).get("id")
    status_info = game.get("status", {})
    status = status_info.get("detailedState", "")
    status_reason = status_info.get("reason", "")
    description = game.get("description", "")

    original_date_str = original_az_dt.strftime("%Y-%m-%d") if is_rescheduled else ""

    if not is_rescheduled and description:
        makeup_match = re.search(r"[Mm]akeup of (\d{1,2})/(\d{1,2})", description)
        if makeup_match:
            orig_month, orig_day = int(makeup_match.group(1)), int(makeup_match.group(2))
            original_date_str = f"{actual_az_dt.year}-{orig_month:02d}-{orig_day:02d}"
            date_display = f"{date_display} (originally {orig_month}/{orig_day})"
            is_rescheduled = True

    return {
        "date": date_display,
        "time_az": actual_az_dt.strftime("%I:%M %p").lstrip("0"),
        "away_team": away_team,
        "home_team": home_team,
        "away_wins": away_record.get("wins", ""),
        "away_losses": away_record.get("losses", ""),
        "away_ties": away_record.get("ties", ""),
        "home_wins": home_record.get("wins", ""),
        "home_losses": home_record.get("losses", ""),
        "home_ties": home_record.get("ties", ""),
        "away_score": away_score,
        "home_score": home_score,
        "venue": venue,
        "venue_id": venue_id,
        "game_pk": game_pk,
        "game_type": GAME_TYPE_LABELS.get(game_type_code, game_type_code),
        "status": status,
        "status_reason": status_reason,
        "rescheduled": "Y" if is_rescheduled else "N",
        "original_date": original_date_str,
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
    parser.add_argument(
        "season",
        type=int,
        nargs="?",
        default=datetime.now().year,
        help="Season year, e.g. 2025, 2026, 2027 (defaults to the current year if omitted)",
    )
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
