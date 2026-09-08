import argparse
import csv
import os
import time
from datetime import datetime

PLAYER_STATS_URL = "https://statsapi.mlb.com/api/v1/people/{player_id}/stats"

PITCHER_STATS_FIELDS = [
    "pitcher_id", "pitcher_name", "wins", "losses", "era", "saves",
]


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def collect_pitcher_ids(output_dir, season):
    season_dir = os.path.join(output_dir, str(season))
    ids = {}

    decisions = load_csv(os.path.join(season_dir, "decisions.csv"))
    for d in decisions:
        for id_key, name_key in [
            ("winning_pitcher_id", "winning_pitcher_name"),
            ("losing_pitcher_id", "losing_pitcher_name"),
            ("save_pitcher_id", "save_pitcher_name"),
        ]:
            pid = d.get(id_key)
            if pid:
                ids[pid] = d.get(name_key, "")

    schedule = load_csv(os.path.join(season_dir, "schedule.csv"))
    for g in schedule:
        for id_key, name_key in [
            ("away_probable_pitcher_id", "away_probable_pitcher"),
            ("home_probable_pitcher_id", "home_probable_pitcher"),
        ]:
            pid = g.get(id_key)
            if pid:
                ids[pid] = g.get(name_key, "")

    return ids


def fetch_pitcher_stats(player_id, season):
    import requests

    params = {"stats": "season", "group": "pitching", "season": season, "sportId": 17}
    resp = requests.get(
        PLAYER_STATS_URL.format(player_id=player_id), params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def extract_pitching_line(data):
    stats = data.get("stats", [])
    if not stats:
        return None
    splits = stats[0].get("splits", [])
    if not splits:
        return None
    stat = splits[0].get("stat", {})
    return {
        "wins": stat.get("wins", ""),
        "losses": stat.get("losses", ""),
        "era": stat.get("era", ""),
        "saves": stat.get("saves", ""),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pull season pitching stats (W-L, ERA, saves) for every pitcher "
        "who appears in a season's decisions or probable-pitcher listings."
    )
    parser.add_argument(
        "season",
        type=int,
        nargs="?",
        default=datetime.now().year,
        help="Season year (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data", help="Base data folder (default: data)")
    args = parser.parse_args()

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)

    pitcher_ids = collect_pitcher_ids(args.output_dir, args.season)
    print(f"Found {len(pitcher_ids)} unique pitchers to look up.")

    rows = []
    for i, (pid, name) in enumerate(pitcher_ids.items(), 1):
        print(f"[{i}/{len(pitcher_ids)}] {name} ({pid}) ...", end=" ")
        try:
            data = fetch_pitcher_stats(pid, args.season)
        except Exception as e:
            print(f"fetch failed ({e}), skipping.")
            continue

        line = extract_pitching_line(data)
        if not line:
            print("no pitching stats found.")
            continue

        rows.append({
            "pitcher_id": pid,
            "pitcher_name": name,
            "wins": line["wins"],
            "losses": line["losses"],
            "era": line["era"],
            "saves": line["saves"],
        })
        print(f"{line['wins']}-{line['losses']}, {line['era']} ERA, {line['saves']} SV.")
        time.sleep(0.3)

    out_path = os.path.join(season_dir, "pitcher_stats.csv")
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PITCHER_STATS_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(rows)} pitchers saved to {out_path}")


if __name__ == "__main__":
    main()
