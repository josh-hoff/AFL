import argparse
import csv
import os
import time
from datetime import datetime

STATS_URL = "https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
AFL_SPORT_ID = 17

FIELDING_GAMELOG_FIELDS = [
    "season", "player_id", "player_name", "team", "date", "opponent",
    "is_home", "is_win", "game_pk", "position",
    "innings", "putouts", "assists", "errors", "throwing_errors",
    "chances", "fielding_pct", "double_plays", "triple_plays",
    "range_factor_per_game", "range_factor_per_9",
]


def load_roster(season, output_dir):
    path = os.path.join(output_dir, str(season), "roster.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No roster found at {path}. Run fetch_afl_roster.py {season} first.")
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def fetch_fielding_gamelog(person_id, season):
    import requests

    params = {"stats": "gameLog", "group": "fielding", "season": season, "sportId": AFL_SPORT_ID}
    resp = requests.get(STATS_URL.format(person_id=person_id), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_fielding_rows(data, player_id, player_name, team):
    stats = data.get("stats", [])
    if not stats:
        return []
    splits = stats[0].get("splits", [])

    rows = []
    for split in splits:
        stat = split.get("stat", {})
        opponent = split.get("opponent", {})
        game = split.get("game", {})
        position = split.get("position", {})
        rows.append({
            "season": split.get("season", ""),
            "player_id": player_id,
            "player_name": player_name,
            "team": team,
            "date": split.get("date", ""),
            "opponent": opponent.get("name", ""),
            "is_home": split.get("isHome", ""),
            "is_win": split.get("isWin", ""),
            "game_pk": game.get("gamePk", ""),
            "position": position.get("abbreviation", ""),
            "innings": stat.get("innings", ""),
            "putouts": stat.get("putOuts", ""),
            "assists": stat.get("assists", ""),
            "errors": stat.get("errors", ""),
            "throwing_errors": stat.get("throwingErrors", ""),
            "chances": stat.get("chances", ""),
            "fielding_pct": stat.get("fielding", ""),
            "double_plays": stat.get("doublePlays", ""),
            "triple_plays": stat.get("triplePlays", ""),
            "range_factor_per_game": stat.get("rangeFactorPerGame", ""),
            "range_factor_per_9": stat.get("rangeFactorPer9Inn", ""),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Fetch AFL fielding game logs for every player on the roster.")
    parser.add_argument(
        "season", type=int, nargs="?", default=datetime.now().year,
        help="Season year (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    roster = load_roster(args.season, args.output_dir)
    print(f"Found {len(roster)} players on the roster.")

    all_rows = []
    for i, player in enumerate(roster, 1):
        player_id = player["player_id"]
        player_name = player["full_name"]
        team = player["team"]
        print(f"[{i}/{len(roster)}] {player_name} ...", end=" ")

        try:
            data = fetch_fielding_gamelog(player_id, args.season)
        except Exception as e:
            print(f"fetch failed ({e}), skipping.")
            continue

        rows = extract_fielding_rows(data, player_id, player_name, team)
        all_rows.extend(rows)
        print(f"{len(rows)} fielding appearances.")
        time.sleep(0.3)

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)
    out_path = os.path.join(season_dir, "fielding_gamelogs.csv")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDING_GAMELOG_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(all_rows)} fielding game log rows saved to {out_path}")


if __name__ == "__main__":
    main()
