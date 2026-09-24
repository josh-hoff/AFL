import argparse
import csv
import os
import time
from datetime import datetime

STATS_URL = "https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
AFL_SPORT_ID = 17
PITCHER_POSITION_CODE = "1"

HITTING_GAMELOG_FIELDS = [
    "season", "player_id", "player_name", "team", "date", "opponent",
    "is_home", "is_win", "game_pk",
    "at_bats", "plate_appearances", "hits", "doubles", "triples", "home_runs",
    "total_bases", "runs", "rbi", "walks", "intentional_walks", "strikeouts",
    "hit_by_pitch", "stolen_bases", "caught_stealing", "avg", "obp", "slg",
    "ops", "babip", "ground_outs", "air_outs", "ground_into_double_play",
    "sac_bunts", "sac_flies", "left_on_base", "catchers_interference",
]


def load_roster(season, output_dir):
    path = os.path.join(output_dir, str(season), "roster.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No roster found at {path}. Run fetch_afl_roster.py {season} first.")
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def fetch_hitting_gamelog(person_id, season):
    import requests

    params = {"stats": "gameLog", "group": "hitting", "season": season, "sportId": AFL_SPORT_ID}
    resp = requests.get(STATS_URL.format(person_id=person_id), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_hitting_rows(data, player_id, player_name, team):
    stats = data.get("stats", [])
    if not stats:
        return []
    splits = stats[0].get("splits", [])

    rows = []
    for split in splits:
        stat = split.get("stat", {})
        opponent = split.get("opponent", {})
        game = split.get("game", {})
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
            "at_bats": stat.get("atBats", ""),
            "plate_appearances": stat.get("plateAppearances", ""),
            "hits": stat.get("hits", ""),
            "doubles": stat.get("doubles", ""),
            "triples": stat.get("triples", ""),
            "home_runs": stat.get("homeRuns", ""),
            "total_bases": stat.get("totalBases", ""),
            "runs": stat.get("runs", ""),
            "rbi": stat.get("rbi", ""),
            "walks": stat.get("baseOnBalls", ""),
            "intentional_walks": stat.get("intentionalWalks", ""),
            "strikeouts": stat.get("strikeOuts", ""),
            "hit_by_pitch": stat.get("hitByPitch", ""),
            "stolen_bases": stat.get("stolenBases", ""),
            "caught_stealing": stat.get("caughtStealing", ""),
            "avg": stat.get("avg", ""),
            "obp": stat.get("obp", ""),
            "slg": stat.get("slg", ""),
            "ops": stat.get("ops", ""),
            "babip": stat.get("babip", ""),
            "ground_outs": stat.get("groundOuts", ""),
            "air_outs": stat.get("airOuts", ""),
            "ground_into_double_play": stat.get("groundIntoDoublePlay", ""),
            "sac_bunts": stat.get("sacBunts", ""),
            "sac_flies": stat.get("sacFlies", ""),
            "left_on_base": stat.get("leftOnBase", ""),
            "catchers_interference": stat.get("catchersInterference", ""),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description="Fetch AFL hitting game logs for every position player on the roster.")
    parser.add_argument(
        "season", type=int, nargs="?", default=datetime.now().year,
        help="Season year (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    roster = load_roster(args.season, args.output_dir)
    position_players = [p for p in roster if p.get("position_code") != PITCHER_POSITION_CODE]
    print(f"Found {len(position_players)} position players (out of {len(roster)} total roster entries).")

    all_rows = []
    for i, player in enumerate(position_players, 1):
        player_id = player["player_id"]
        player_name = player["full_name"]
        team = player["team"]
        print(f"[{i}/{len(position_players)}] {player_name} ...", end=" ")

        try:
            data = fetch_hitting_gamelog(player_id, args.season)
        except Exception as e:
            print(f"fetch failed ({e}), skipping.")
            continue

        rows = extract_hitting_rows(data, player_id, player_name, team)
        all_rows.extend(rows)
        print(f"{len(rows)} games.")
        time.sleep(0.3)

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)
    out_path = os.path.join(season_dir, "hitting_gamelogs.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=HITTING_GAMELOG_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(all_rows)} game log rows saved to {out_path}")


if __name__ == "__main__":
    main()
