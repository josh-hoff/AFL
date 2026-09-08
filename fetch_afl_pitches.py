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

    print()
    print(f"Done. {len(all_rows)} total pitches saved to {out_path}")
    print(f"Games with no data: {skipped_no_plays} (cancelled/postponed)")
    if skipped_missing:
        print(f"Games skipped due to fetch/file errors: {skipped_missing}")


if __name__ == "__main__":
    main()
