import argparse
import csv
import os
import time
from datetime import datetime

PLAYER_STATS_URL = "https://statsapi.mlb.com/api/v1/people/{player_id}/stats"

# Fields are no longer a fixed list -- we capture every stat MLB's API
# returns for a pitcher's season line, dynamically, so no field ever
# has to be added by hand again.
BASE_FIELDS = ["pitcher_id", "pitcher_name"]


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
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

    roster = load_csv(os.path.join(season_dir, "roster.csv"))
    for p in roster:
        if p.get("position_code") == "1":
            pid = p.get("player_id")
            if pid:
                ids[pid] = p.get("full_name", "")

    return ids


def fetch_pitcher_stats(player_id, season):
    import requests

    params = {"stats": "season", "group": "pitching", "season": season, "sportId": 17}
    resp = requests.get(
        PLAYER_STATS_URL.format(player_id=player_id), params=params, timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def extract_pitching_stat(data):
    """Return the raw stat dict as-is, whatever fields MLB includes."""
    stats = data.get("stats", [])
    if not stats:
        return None
    splits = stats[0].get("splits", [])
    if not splits:
        return None
    return splits[0].get("stat", {})


def main():
    parser = argparse.ArgumentParser(
        description="Pull every available season pitching stat for every pitcher "
        "who appears in a season's decisions, probable-pitcher listings, or team roster."
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
    all_stat_keys = set()

    for i, (pid, name) in enumerate(pitcher_ids.items(), 1):
        print(f"[{i}/{len(pitcher_ids)}] {name} ({pid}) ...", end=" ")
        try:
            data = fetch_pitcher_stats(pid, args.season)
        except Exception as e:
            print(f"fetch failed ({e}), skipping.")
            continue

        stat = extract_pitching_stat(data)
        if stat is None:
            print("no pitching stats found, skipping.")
            continue

        # Flatten out any nested value (e.g. a position dict) to a plain string,
        # so nothing breaks the CSV writer.
        flat_stat = {}
        for k, v in stat.items():
            flat_stat[k] = v if isinstance(v, (str, int, float, type(None))) else str(v)

        row = {"pitcher_id": pid, "pitcher_name": name}
        row.update(flat_stat)
        rows.append(row)
        all_stat_keys.update(flat_stat.keys())

        print(f"{stat.get('wins', '?')}-{stat.get('losses', '?')}, {stat.get('era', '?')} ERA.")
        time.sleep(0.3)

    fieldnames = BASE_FIELDS + sorted(all_stat_keys)

    out_path = os.path.join(season_dir, "pitcher_stats.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(rows)} pitchers saved to {out_path}")
    print(f"Captured {len(all_stat_keys)} distinct stat fields.")


if __name__ == "__main__":
    main()
