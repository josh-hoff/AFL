"""Track the MLB Pipeline Top 100 prospects list for a season in ONE csv:
data/<season>/top100.csv

Layout: one row per player who was ever on that year's list, one column per saved version
of the list (the column header is the date, e.g. 2027-03-01) holding that player's rank on
that date -- blank if he wasn't on that version.

    player_id,player_name,position,2027-01-25,2027-03-01,2027-06-14
    111111,Player X,SS,8,5,12

A new date column is added ONLY when the list actually changed (different players or a
different order) since the newest saved column; if nothing changed the file isn't touched,
so the workflow has nothing to commit. Players who leave the list (graduate, etc.) keep
their row and all their earlier ranks, so their badge survives. The site works out each
player's current rank (rightmost filled-in cell) and peak rank (smallest number) itself.

The list isn't served from a separate feed: MLB embeds the whole ranking as JSON in the
page itself (a `data-init-state` attribute), so this downloads the page for that year and
reads the JSON.

Usage:
    python fetch_afl_top100.py                       # current year, column dated today
    python fetch_afl_top100.py 2025                  # a past year (adds a column dated today)
    python fetch_afl_top100.py 2026 --wayback 20260215
        # backfill: use the Wayback Machine snapshot closest to that date; the column is
        # dated with the snapshot's own date
    python fetch_afl_top100.py 2026 --from-file saved.html --date 2026-02-15
        # backfill from a page you saved yourself
    --soft   exit quietly (code 0) if the list isn't published yet / can't be read
"""
import argparse
import csv
import html
import json
import os
import re
import sys
from datetime import datetime, timezone

PAGE_URL = "https://www.mlb.com/milb/prospects/{year}/top100"
BASE_FIELDS = ["player_id", "player_name", "position"]
MIN_EXPECTED = 50  # a real list has 100; far fewer means the page layout changed
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PAGE_URL = "https://www.mlb.com/milb/prospects/{year}/top100"


def download_page(year):
    import requests

    resp = requests.get(
        PAGE_URL.format(year=year),
        headers={"User-Agent": "Mozilla/5.0 (compatible; afl-dashboard-data-pull)"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.text


def wayback_raw_url(snapshot_url):
    """Turn a Wayback snapshot URL into its raw-HTML form (the `id_` flavor), which skips the
    toolbar/rewritten links Wayback normally injects into the page."""
    m = re.search(r"/web/(\d{14})(?:[a-z]{2}_)?/(https?://.+)$", snapshot_url)
    if not m:
        raise ValueError(f"Unrecognized Wayback URL: {snapshot_url}")
    return f"https://web.archive.org/web/{m.group(1)}id_/{m.group(2)}", m.group(1)


def download_wayback(year, target):
    """Closest Wayback snapshot of the year's page to `target` (YYYYMMDD). Returns (html, 'YYYY-MM-DD')."""
    import requests

    headers = {"User-Agent": "Mozilla/5.0 (compatible; afl-dashboard-data-pull)"}
    api = requests.get(
        "https://archive.org/wayback/available",
        params={"url": PAGE_URL.format(year=year), "timestamp": target},
        headers=headers,
        timeout=60,
    )
    api.raise_for_status()
    closest = (api.json().get("archived_snapshots") or {}).get("closest")
    if not closest or not closest.get("available"):
        raise ValueError(f"Wayback has no snapshot of the {year} page near {target}.")
    raw_url, ts = wayback_raw_url(closest["url"])
    resp = requests.get(raw_url, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.text, f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}"

def parse_rankings(page_html, year):
    m = re.search(r'data-init-state="([^"]*)"', page_html)
    if not m:
        raise ValueError("Couldn't find the embedded data (data-init-state) in the page.")
    state = json.loads(html.unescape(m.group(1)))
    payload = state["payload"]
    root = payload["ROOT_QUERY"]
    key = next((k for k in root if k.startswith("getPlayerRankingsFromSelection")), None)
    if key is None:
        raise ValueError("Couldn't find the rankings list inside the page data.")

    page_year = str(state.get("context", {}).get("year", ""))
    if page_year and page_year != str(year):
        raise ValueError(f"Page returned the {page_year} list, not {year}.")

    rows = []
    for entry in root[key]:
        ref = entry["playerEntity"]["player"]["__ref"]  # e.g. "Person:808963"
        person = payload[ref]
        name = f"{person.get('useName', '')} {person.get('useLastName', '')}".strip()
        rows.append({
            "season": year,
            "rank": entry["rank"],
            "player_id": person["id"],
            "player_name": name,
            "position": entry["playerEntity"].get("position", ""),
        })
    return sorted(rows, key=lambda r: r["rank"])



def read_table(path):
    """Existing file -> (rows keyed by player_id, sorted list of date columns).
    Also upgrades the old one-list-per-year layout (season,rank,player_id,...,pulled_at)."""
    players, dates = {}, []
    if not os.path.exists(path):
        return players, dates
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if "rank" in fields and "pulled_at" in fields:  # old layout
            for r in reader:
                d = r["pulled_at"]
                if d not in dates:
                    dates.append(d)
                p = players.setdefault(r["player_id"], {"player_id": r["player_id"],
                                                        "player_name": r["player_name"],
                                                        "position": r["position"]})
                p[d] = r["rank"]
            return players, sorted(dates)
        dates = sorted(c for c in fields if DATE_RE.match(c))
        for r in reader:
            players[r["player_id"]] = r
    return players, dates


def newest_ranks(players, date):
    return {pid: int(p[date]) for pid, p in players.items() if p.get(date)}


def write_table(path, players, dates):
    newest = dates[-1]

    def sort_key(p):
        on_newest = bool(p.get(newest))
        last = next((int(p[d]) for d in reversed(dates) if p.get(d)), 999)
        return (0 if on_newest else 1, last, p["player_name"])

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BASE_FIELDS + dates, extrasaction="ignore")
        w.writeheader()
        for p in sorted(players.values(), key=sort_key):
            w.writerow({k: p.get(k, "") for k in BASE_FIELDS + dates})


def main():
    parser = argparse.ArgumentParser(description="Track the MLB Pipeline Top 100 prospects list.")
    parser.add_argument("year", type=int, nargs="?", default=datetime.now().year)
    parser.add_argument("--from-file", help="Parse a saved copy of the page instead of downloading it.")
    parser.add_argument("--date", help="Column date (YYYY-MM-DD) for --from-file. Default: today.")
    parser.add_argument("--wayback", metavar="YYYYMMDD", help="Use the Wayback Machine snapshot closest to this date.")
    parser.add_argument("--soft", action="store_true", help="Exit 0 (no change) if the list can't be fetched/read.")
    args = parser.parse_args()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    col_date = args.date or today
    try:
        if args.from_file:
            with open(args.from_file, encoding="utf-8") as f:
                page = f.read()
        elif args.wayback:
            page, col_date = download_wayback(args.year, args.wayback)
        else:
            page = download_page(args.year)
        rows = parse_rankings(page, args.year)
    except Exception as e:  # network, 404 before the list is published, layout change...
        if args.soft:
            print(f"Could not read the {args.year} list ({e}); leaving data untouched.")
            return
        raise
    if not DATE_RE.match(col_date):
        sys.exit(f"Bad date {col_date!r}; use YYYY-MM-DD.")
    if len(rows) < MIN_EXPECTED:
        print(f"Only found {len(rows)} players for {args.year}; expected about 100. "
              f"Leaving any existing file untouched.", file=sys.stderr)
        sys.exit(1)

    out_dir = os.path.join("data", str(args.year))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "top100.csv")
    players, dates = read_table(out_path)
    new_ranks = {str(r["player_id"]): int(r["rank"]) for r in rows}

    # Old one-list-per-year file? Upgrade it to the new layout first (no new column needed if
    # the live list is the same as the saved one).
    old_layout = os.path.exists(out_path) and "pulled_at" in open(out_path, encoding="utf-8").readline()

    # Is this version already saved? Compare with the saved column just before (or on) this date.
    earlier = [d for d in dates if d <= col_date]
    if earlier and newest_ranks(players, earlier[-1]) == new_ranks:
        if old_layout:
            write_table(out_path, players, dates)
            print(f"Upgraded {out_path} to the one-column-per-version layout; the list hasn't changed.")
        else:
            print(f"No change in the {args.year} list since {earlier[-1]}; nothing written.")
        return
    if col_date in dates:  # re-run on the same date after a change: replace that column
        for p in players.values():
            p.pop(col_date, None)
    else:
        dates = sorted(dates + [col_date])

    for r in rows:
        pid = str(r["player_id"])
        p = players.setdefault(pid, {"player_id": pid})
        p["player_name"], p["position"] = r["player_name"], r["position"]
        p[col_date] = str(r["rank"])
    write_table(out_path, players, dates)
    print(f"Saved {args.year} list for {col_date}: {len(rows)} ranked, {len(players)} players in file, {len(dates)} version(s).")


if __name__ == "__main__":
    main()
