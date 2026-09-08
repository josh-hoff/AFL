import argparse
import csv
import json
import os
import time
from datetime import datetime

LIVE_FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"

PITCH_FIELDS = [
    "game_pk", "date", "venue", "inning", "half_inning",
    "pitcher_id", "pitcher_name", "batter_id", "batter_name",
    "pitch_number", "pitch_type_code", "pitch_type_desc", "call",
    "start_speed", "end_speed", "extension",
    "release_x", "release_y", "release_z",
    "spin_rate", "spin_direction",
    "break_angle", "break_length", "break_vertical",
    "break_vertical_induced", "break_horizontal",
    "zone", "plate_time", "type_confidence",
    "launch_speed", "launch_angle", "total_distance",
    "trajectory", "hardness", "hit_location",
]


DECISION_FIELDS = [
    "game_pk", "date",
    "winning_pitcher_id", "winning_pitcher_name",
    "winning_pitcher_wins", "winning_pitcher_losses", "winning_pitcher_era",
    "losing_pitcher_id", "losing_pitcher_name",
    "losing_pitcher_wins", "losing_pitcher_losses", "losing_pitcher_era",
    "save_pitcher_id", "save_pitcher_name", "save_pitcher_saves",
]


def load_schedule(season, output_dir):
    path = os.path.join(output_dir, str(season), "schedule.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No schedule found at {path}. "
            f"Run fetch_afl_schedule.py {season} first."
        )
    with open(path, "r", newline="") as f:
        return list(csv.DictReader(f))


def fetch_game_feed(game_pk):
    import requests

    url = LIVE_FEED_URL.format(game_pk=game_pk)
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def load_game_feed_from_file(feeds_dir, game_pk):
    path = os.path.join(feeds_dir, f"{game_pk}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r") as f:
        return json.load(f)


def extract_pitches(feed, game_info):
    rows = []
    plays = feed.get("liveData", {}).get("plays", {}).get("allPlays", [])

    for play in plays:
        about = play.get("about", {})
        matchup = play.get("matchup", {})
        batter = matchup.get("batter", {})
        pitcher = matchup.get("pitcher", {})

        for event in play.get("playEvents", []):
            if not event.get("isPitch"):
                continue

            details = event.get("details", {})
            pitch_type = details.get("type", {})
            call = details.get("call", {})
            pitch_data = event.get("pitchData", {})
            coords = pitch_data.get("coordinates", {})
            breaks = pitch_data.get("breaks", {})
            hit_data = event.get("hitData", {})

            rows.append({
                "game_pk": game_info.get("game_pk"),
                "date": game_info.get("date"),
                "venue": game_info.get("venue"),
                "inning": about.get("inning"),
                "half_inning": about.get("halfInning"),
                "pitcher_id": pitcher.get("id"),
                "pitcher_name": pitcher.get("fullName"),
                "batter_id": batter.get("id"),
                "batter_name": batter.get("fullName"),
                "pitch_number": event.get("pitchNumber"),
                "pitch_type_code": pitch_type.get("code"),
                "pitch_type_desc": pitch_type.get("description"),
                "call": call.get("description"),
                "start_speed": pitch_data.get("startSpeed"),
                "end_speed": pitch_data.get("endSpeed"),
                "extension": pitch_data.get("extension"),
                "release_x": coords.get("x0"),
                "release_y": coords.get("y0"),
                "release_z": coords.get("z0"),
                "spin_rate": breaks.get("spinRate"),
                "spin_direction": breaks.get("spinDirection"),
                "break_angle": breaks.get("breakAngle"),
                "break_length": breaks.get("breakLength"),
                "break_vertical": breaks.get("breakVertical"),
                "break_vertical_induced": breaks.get("breakVerticalInduced"),
                "break_horizontal": breaks.get("breakHorizontal"),
                "zone": pitch_data.get("zone"),
                "plate_time": pitch_data.get("plateTime"),
                "type_confidence": pitch_data.get("typeConfidence"),
                "launch_speed": hit_data.get("launchSpeed"),
                "launch_angle": hit_data.get("launchAngle"),
                "total_distance": hit_data.get("totalDistance"),
                "trajectory": hit_data.get("trajectory"),
                "hardness": hit_data.get("hardness"),
                "hit_location": hit_data.get("location"),
            })

    return rows


def extract_decisions(feed, game_info):
    decisions = feed.get("liveData", {}).get("decisions", {})
    winner = decisions.get("winner", {})
    loser = decisions.get("loser", {})
    save = decisions.get("save", {})

    if not winner and not loser:
        return None

    return {
        "game_pk": game_info.get("game_pk"),
        "date": game_info.get("date"),
        "winning_pitcher_id": winner.get("id", ""),
        "winning_pitcher_name": winner.get("fullName", ""),
        "winning_pitcher_wins": "",
        "winning_pitcher_losses": "",
        "winning_pitcher_era": "",
        "losing_pitcher_id": loser.get("id", ""),
        "losing_pitcher_name": loser.get("fullName", ""),
        "losing_pitcher_wins": "",
        "losing_pitcher_losses": "",
        "losing_pitcher_era": "",
        "save_pitcher_id": save.get("id", ""),
        "save_pitcher_name": save.get("fullName", ""),
        "save_pitcher_saves": "",
    }


def innings_pitched_to_outs(ip_str):
    if not ip_str:
        return 0
    whole, _, frac = str(ip_str).partition(".")
    whole_outs = int(whole) * 3 if whole else 0
    frac_outs = int(frac) if frac else 0
    return whole_outs + frac_outs


def get_pitcher_game_stats(feed, pitcher_id):
    teams = feed.get("liveData", {}).get("boxscore", {}).get("teams", {})
    for side in ("away", "home"):
        players = teams.get(side, {}).get("players", {})
        player = players.get(f"ID{pitcher_id}")
        if player:
            return player.get("stats", {}).get("pitching", {})
    return {}


def apply_running_record(decision, feed, pitcher_records):
    def record_for(pid):
        return pitcher_records.setdefault(
            pid, {"wins": 0, "losses": 0, "saves": 0, "earned_runs": 0, "outs": 0}
        )

    def update_era_stats(pid, rec):
        game_stats = get_pitcher_game_stats(feed, pid)
        rec["earned_runs"] += int(game_stats.get("earnedRuns", 0) or 0)
        rec["outs"] += innings_pitched_to_outs(game_stats.get("inningsPitched", ""))

    def era_display(rec):
        if rec["outs"] == 0:
            return ""
        era = rec["earned_runs"] * 9 / (rec["outs"] / 3)
        return f"{era:.2f}"

    w_id = decision["winning_pitcher_id"]
    if w_id:
        rec = record_for(w_id)
        rec["wins"] += 1
        update_era_stats(w_id, rec)
        decision["winning_pitcher_wins"] = rec["wins"]
        decision["winning_pitcher_losses"] = rec["losses"]
        decision["winning_pitcher_era"] = era_display(rec)

    l_id = decision["losing_pitcher_id"]
    if l_id:
        rec = record_for(l_id)
        rec["losses"] += 1
        update_era_stats(l_id, rec)
        decision["losing_pitcher_wins"] = rec["wins"]
        decision["losing_pitcher_losses"] = rec["losses"]
        decision["losing_pitcher_era"] = era_display(rec)

    s_id = decision["save_pitcher_id"]
    if s_id:
        rec = record_for(s_id)
        rec["saves"] += 1
        decision["save_pitcher_saves"] = rec["saves"]


def main():
    parser = argparse.ArgumentParser(
        description="Pull per-pitch Statcast data for an AFL season's games."
    )
    parser.add_argument(
        "season",
        type=int,
        nargs="?",
        default=datetime.now().year,
        help="Season year, e.g. 2025, 2026, 2027 (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data", help="Base data folder (default: data)")
    parser.add_argument("--game-pk", type=int, help="Pull just this one game instead of the whole season")
    parser.add_argument("--limit", type=int, help="Only process the first N games (for testing)")
    parser.add_argument(
        "--feeds-dir",
        help="Read game feeds from local {gamePk}.json files here instead of calling the live API",
    )
    args = parser.parse_args()

    schedule = load_schedule(args.season, args.output_dir)

    if args.game_pk:
        schedule = [g for g in schedule if str(g["game_pk"]) == str(args.game_pk)]
        if not schedule:
            print(f"gamePk {args.game_pk} not found in the {args.season} schedule.")
            return
    elif args.limit:
        schedule = schedule[: args.limit]

    all_rows = []
    all_decisions = []
    pitcher_records = {}
    skipped_no_plays = 0
    skipped_missing = 0

    for i, game in enumerate(schedule, 1):
        game_pk = game["game_pk"]
        print(f"[{i}/{len(schedule)}] gamePk {game_pk} ({game.get('date')}) ...", end=" ")

        if args.feeds_dir:
            feed = load_game_feed_from_file(args.feeds_dir, game_pk)
            if feed is None:
                print("no saved feed file found, skipping.")
                skipped_missing += 1
                continue
        else:
            try:
                feed = fetch_game_feed(game_pk)
            except Exception as e:
                print(f"fetch failed ({e}), skipping.")
                skipped_missing += 1
                continue
            time.sleep(0.5)

        rows = extract_pitches(feed, game)
        decision = extract_decisions(feed, game)
        if decision:
            apply_running_record(decision, feed, pitcher_records)
            all_decisions.append(decision)

        if not rows:
            print("no pitches (likely cancelled/postponed).")
            skipped_no_plays += 1
            continue

        all_rows.extend(rows)
        print(f"{len(rows)} pitches.")

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)
    out_path = os.path.join(season_dir, "pitches.csv")

    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=PITCH_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    decisions_path = os.path.join(season_dir, "decisions.csv")
    with open(decisions_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DECISION_FIELDS)
        writer.writeheader()
        for row in all_decisions:
            writer.writerow(row)

    print()
    print(f"Done. {len(all_rows)} total pitches saved to {out_path}")
    print(f"{len(all_decisions)} game decisions saved to {decisions_path}")
    print(f"Games with no data: {skipped_no_plays} (cancelled/postponed)")
    if skipped_missing:
        print(f"Games skipped due to fetch/file errors: {skipped_missing}")


if __name__ == "__main__":
    main()
