import argparse
import csv
import json
import os
import re
import time
from datetime import datetime, timedelta

STANDINGS_URL = "https://statsapi.mlb.com/api/v1/standings"
AFL_LEAGUE_ID = 119

TEAM_ID_TO_NAME = {
    490: "Peoria Javelinas",
    454: "Glendale Desert Dogs",
    542: "Surprise Saguaros",
    544: "Scottsdale Scorpions",
    555: "Mesa Solar Sox",
    527: "Salt River Rafters",
}


def load_schedule_dates(season, output_dir):
    path = os.path.join(output_dir, str(season), "schedule.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No schedule found at {path}. Run fetch_afl_schedule.py {season} first."
        )
    dates = []
    with open(path, "r", newline="") as f:
        for row in csv.DictReader(f):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", row.get("date", ""))
            if m:
                dates.append(m.group(1))
    if not dates:
        raise ValueError("No valid dates found in schedule.csv")
    return min(dates), max(dates)


def daterange(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    current = start
    while current <= end:
        yield current.strftime("%Y-%m-%d")
        current += timedelta(days=1)


def fetch_standings(season, date_str):
    import requests

    params = {"leagueId": AFL_LEAGUE_ID, "season": season, "date": date_str}
    resp = requests.get(STANDINGS_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_standings(data):
    records = data.get("records", [])
    if not records:
        return []
    team_records = records[0].get("teamRecords", [])
    teams = []
    for tr in team_records:
        team_id = tr.get("team", {}).get("id")
        name = TEAM_ID_TO_NAME.get(team_id, tr.get("team", {}).get("name", ""))
        splits = {s["type"]: s for s in tr.get("records", {}).get("splitRecords", [])}
        last_ten = splits.get("lastTen", {})
        home = splits.get("home", {})
        away = splits.get("away", {})
        league_rank_raw = tr.get("leagueRank", "")
        league_rank = int(league_rank_raw) if str(league_rank_raw).isdigit() else 999

        teams.append({
            "team_id": team_id,
            "team_name": name,
            "wins": tr.get("wins"),
            "losses": tr.get("losses"),
            "pct": tr.get("leagueRecord", {}).get("pct"),
            "games_back": tr.get("gamesBack"),
            "streak": tr.get("streak", {}).get("streakCode", ""),
            "last_ten_wins": last_ten.get("wins"),
            "last_ten_losses": last_ten.get("losses"),
            "runs_scored": tr.get("runsScored"),
            "runs_allowed": tr.get("runsAllowed"),
            "run_diff": tr.get("runDifferential"),
            "home_wins": home.get("wins"),
            "home_losses": home.get("losses"),
            "away_wins": away.get("wins"),
            "away_losses": away.get("losses"),
            "league_rank": league_rank,
        })

    teams.sort(key=lambda t: t["league_rank"])
    return teams


def main():
    parser = argparse.ArgumentParser(
        description="Fetch daily AFL standings snapshots for a season."
    )
    parser.add_argument(
        "season", type=int, nargs="?", default=datetime.now().year,
        help="Season year (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data")
    parser.add_argument(
        "--end-buffer-days", type=int, default=3,
        help="Extra days to fetch past the season's last scheduled game",
    )
    parser.add_argument(
        "--only-missing", action="store_true",
        help="Skip dates that already have a saved file (today's date is always refetched)",
    )
    args = parser.parse_args()

    start_date, last_game_date = load_schedule_dates(args.season, args.output_dir)

    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    today_dt = datetime.now()

    if today_dt < start_dt:
        print(f"The {args.season} season hasn't started yet (opens {start_date}). Nothing to fetch.")
        return

    end_dt = datetime.strptime(last_game_date, "%Y-%m-%d") + timedelta(days=args.end_buffer_days)
    if end_dt > today_dt:
        end_dt = today_dt
    end_date = end_dt.strftime("%Y-%m-%d")

    standings_dir = os.path.join(args.output_dir, str(args.season), "standings")
    os.makedirs(standings_dir, exist_ok=True)

    dates = list(daterange(start_date, end_date))
    today_str = today_dt.strftime("%Y-%m-%d")
    print(f"Fetching standings for {len(dates)} dates ({start_date} to {end_date})...")

    fetched = 0
    skipped = 0
    for i, date_str in enumerate(dates, 1):
        out_path = os.path.join(standings_dir, f"{date_str}.json")

        if args.only_missing and os.path.exists(out_path) and date_str != today_str:
            skipped += 1
            continue

        print(f"[{i}/{len(dates)}] {date_str} ...", end=" ")
        try:
            data = fetch_standings(args.season, date_str)
        except Exception as e:
            print(f"fetch failed ({e}), skipping.")
            continue

        teams = extract_standings(data)
        with open(out_path, "w") as f:
            json.dump({"date": date_str, "teams": teams}, f)

        print(f"{len(teams)} teams.")
        fetched += 1
        time.sleep(0.3)

    print()
    print(f"Done. {fetched} days fetched, {skipped} already existed and were skipped.")

    available_dates = sorted(
        f[:-5] for f in os.listdir(standings_dir)
        if f.endswith(".json") and f != "dates.json"
    )
    manifest_path = os.path.join(standings_dir, "dates.json")
    with open(manifest_path, "w") as f:
        json.dump(available_dates, f)
    print(f"Manifest updated: {manifest_path} ({len(available_dates)} dates available)")


if __name__ == "__main__":
    main()
