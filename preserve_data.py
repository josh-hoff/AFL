"""Never lose a row of player data.

Every fetch script rebuilds its CSV from whatever MLB returns *right now*. If MLB leaves
something out (a player comes off a roster list, a stat line is corrected away, a request
fails part-way), a plain rewrite would delete it from the site.

This script runs after all the fetches, before the commit. For every data file it compares
the freshly written file with the last committed version and APPENDS any row that existed
before but is missing now. Rows that are still returned are never touched, so fresh values
(new stats, corrected numbers) always win. Nothing is ever deleted.

Usage:  python preserve_data.py [season] [--base-ref HEAD] [--data-dir data] [--dry-run]
"""
import argparse
import csv
import io
import os
import subprocess
import sys
from datetime import datetime

# file name -> columns that identify one row (a row whose key is already in the new file is
# never re-added, so changed values such as pitch speeds or stats are not duplicated).
KEYS = {
    "roster.csv": ["player_id"],
    "batting_lineups.csv": ["game_pk", "player_id", "sub_sequence"],
    "pitcher_appearances.csv": ["game_pk", "pitcher_id", "appearance_order"],
    "decisions.csv": ["game_pk"],
    "hitting_gamelogs.csv": ["player_id", "game_pk"],
    "fielding_gamelogs.csv": ["player_id", "game_pk", "position"],
    "pitching_gamelogs.csv": ["pitcher_id", "game_pk"],
    "pitcher_stats.csv": ["pitcher_id"],
    "schedule.csv": ["game_pk"],
    "transactions.csv": ["date", "player_id", "type_code", "description"],
    "pitches.csv": ["game_pk", "pitcher_id", "batter_id", "inning", "half_inning", "pitch_number"],
}


def git_show(ref, path):
    p = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True)
    if p.returncode != 0:
        return None
    return p.stdout.decode("utf-8", errors="replace")


def read_rows(text):
    return list(csv.DictReader(io.StringIO(text, newline="")))


def preserve_file(path, name, ref, dry_run):
    old_text = git_show(ref, path.replace(os.sep, "/"))
    if old_text is None or not os.path.exists(path):
        return 0
    with open(path, "rb") as f:
        raw = f.read()
    new_text = raw.decode("utf-8", errors="replace")
    new_reader = csv.reader(io.StringIO(new_text, newline=""))
    header = next(new_reader, None)
    if not header:
        return 0
    keys = KEYS[name]
    if any(k not in header for k in keys):
        print(f"  {name}: key columns missing from new file, skipped")
        return 0
    idx = [header.index(k) for k in keys]
    have = set()
    for row in new_reader:
        if len(row) >= len(header):
            have.add(tuple(row[i] for i in idx))

    missing = []
    seen_old = set()
    for r in read_rows(old_text):
        if any(k not in r for k in keys):
            continue
        k = tuple(r.get(c, "") for c in keys)
        if k in have or k in seen_old:
            continue
        seen_old.add(k)
        missing.append([r.get(c, "") or "" for c in header])

    if missing and not dry_run:
        eol = "\r\n" if b"\r\n" in raw[:4000] else "\n"
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator=eol)
        w.writerows(missing)
        add = buf.getvalue().encode("utf-8")
        if raw and not raw.endswith(b"\n"):
            add = eol.encode() + add
        with open(path, "ab") as f:
            f.write(add)
    return len(missing)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("season", type=int, nargs="?", default=datetime.now().year)
    ap.add_argument("--base-ref", default="HEAD", help="git ref holding the last saved data")
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", nargs="*", help="limit to these file names, e.g. fielding_gamelogs.csv")
    args = ap.parse_args()

    season_dir = os.path.join(args.data_dir, str(args.season))
    total = 0
    for name in KEYS:
        if args.only and name not in args.only:
            continue
        path = os.path.join(season_dir, name)
        n = preserve_file(path, name, args.base_ref, args.dry_run)
        total += n
        if n:
            print(f"  {name}: kept {n} row(s) that MLB's latest answer no longer included")
    print(f"preserve_data: {total} row(s) kept" + (" (dry run, nothing written)" if args.dry_run else "."))


if __name__ == "__main__":
    sys.exit(main())
