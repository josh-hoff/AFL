import argparse
import csv
import os
import time
from datetime import datetime

STATS_URL = "https://statsapi.mlb.com/api/v1/people/{person_id}/stats"
AFL_SPORT_ID = 17
PITCHER_POSITION_CODE = "1"

# Fields are not a fixed list -- we capture every stat MLB's gameLog
# response returns for a pitcher's appearance in a game, dynamically, same
# approach as pitcher_stats.csv. Each per-game "stat" object mixes two
# kinds of numbers: single-game counting stats (inningsPitched, hits,
# earnedRuns, strikeOuts, numberOfPitches, ...) AND a handful of fields
# MLB computes cumulatively through that game (era, whip, wins, losses,
# winPercentage, ...). Both kinds are captured as-is; which is which is
# just a fact about what MLB puts in each named field, not something we
# compute ourselves -- that's the whole point (see decisions.csv's
# separately-computed running record, which gets this wrong for
# no-decision appearances).
BASE_FIELDS = [
    "pitcher_id", "pitcher_name", "season", "team", "opponent",
    "date", "is_home", "is_win", "game_pk", "game_type",
]


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def collect_pitcher_ids(output_dir, season):
    """Same collection logic as fetch_afl_pitcher_stats.py -- every pitcher
    who shows up in a decision, a probable-pitcher listing, or the roster."""
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
        if p.get("position_code") == PITCHER_POSITION_CODE:
            pid = p.get("player_id")
            if pid:
                ids[pid] = p.get("full_name", "")

    return ids


def fetch_pitching_gamelog(person_id, season):
    import requests

    # gameType defaults to regular season ("R") only if left off -- the AFL's
    # crossover/championship round uses postseason codes (D = First Round,
    # L = Semifinal, W = Championship), which would otherwise silently be
    # missing from every pitcher's game log. "A" (Fall Stars Game, the
    # exhibition all-star game) is deliberately left out.
    params = {
        "stats": "gameLog", "group": "pitching", "season": season, "sportId": AFL_SPORT_ID,
        "gameType": "R,D,L,W",
    }
    resp = requests.get(STATS_URL.format(person_id=person_id), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def flatten_stat(stat):
    """Same flattening pitcher_stats.csv uses: keep primitives as-is,
    stringify anything nested so nothing breaks the CSV writer."""
    flat = {}
    for k, v in stat.items():
        flat[k] = v if isinstance(v, (str, int, float, type(None))) else str(v)
    return flat


def extract_pitching_rows(data, pitcher_id, pitcher_name):
    stats = data.get("stats", [])
    if not stats:
        return [], set()
    splits = stats[0].get("splits", [])

    rows = []
    all_keys = set()
    for split in splits:
        stat = split.get("stat", {})
        opponent = split.get("opponent", {})
        team = split.get("team", {})
        game = split.get("game", {})

        flat_stat = flatten_stat(stat)
        row = {
            "pitcher_id": pitcher_id,
            "pitcher_name": pitcher_name,
            "season": split.get("season", ""),
            "team": team.get("name", ""),
            "opponent": opponent.get("name", ""),
            "date": split.get("date", ""),
            "is_home": split.get("isHome", ""),
            "is_win": split.get("isWin", ""),
            "game_pk": game.get("gamePk", ""),
            "game_type": split.get("gameType", ""),
        }
        row.update(flat_stat)
        rows.append(row)
        all_keys.update(flat_stat.keys())

    return rows, all_keys


def main():
    parser = argparse.ArgumentParser(
        description="Pull every available per-game pitching stat (box score line "
        "plus MLB's own cumulative-through-that-game numbers) for every pitcher "
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

    all_rows = []
    all_stat_keys = set()

    for i, (pid, name) in enumerate(pitcher_ids.items(), 1):
        print(f"[{i}/{len(pitcher_ids)}] {name} ({pid}) ...", end=" ")
        try:
            data = fetch_pitching_gamelog(pid, args.season)
        except Exception as e:
            print(f"fetch failed ({e}), skipping.")
            continue

        rows, keys = extract_pitching_rows(data, pid, name)
        all_rows.extend(rows)
        all_stat_keys.update(keys)
        print(f"{len(rows)} games.")
        time.sleep(0.3)

    fieldnames = BASE_FIELDS + sorted(all_stat_keys)

    out_path = os.path.join(season_dir, "pitching_gamelogs.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(all_rows)} pitcher-game rows saved to {out_path}")
    print(f"Captured {len(all_stat_keys)} distinct stat fields per row.")


if __name__ == "__main__":
    main()
