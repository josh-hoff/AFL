"""Fetch the MLB Pipeline Top 100 prospects list for a season and save it to
data/<season>/top100.csv (rank, player_id, name, position).

The list isn't served from a separate feed: MLB embeds the whole ranking as JSON in the
page itself (a `data-init-state` attribute), so this downloads the page for that year and
reads the JSON. Rankings are as of whenever the script runs (MLB updates the list during
the year), and `pulled_at` records that date.

Usage:
    python fetch_afl_top100.py            # current year
    python fetch_afl_top100.py 2025
    python fetch_afl_top100.py 2025 --from-file saved_page.html   # parse a saved copy (testing)
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
FIELDS = ["season", "rank", "player_id", "player_name", "position", "pulled_at"]
MIN_EXPECTED = 50  # a real list has 100; far fewer means the page layout changed


def download_page(year):
    import requests

    resp = requests.get(
        PAGE_URL.format(year=year),
        headers={"User-Agent": "Mozilla/5.0 (compatible; afl-dashboard-data-pull)"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.text


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


def main():
    parser = argparse.ArgumentParser(description="Fetch the MLB Pipeline Top 100 prospects list.")
    parser.add_argument("year", type=int, nargs="?", default=datetime.now().year)
    parser.add_argument("--from-file", help="Parse a saved copy of the page instead of downloading it.")
    args = parser.parse_args()

    if args.from_file:
        with open(args.from_file, encoding="utf-8") as f:
            page = f.read()
    else:
        page = download_page(args.year)

    rows = parse_rankings(page, args.year)
    if len(rows) < MIN_EXPECTED:
        print(f"Only found {len(rows)} players for {args.year}; expected about 100. "
              f"Leaving any existing file untouched.", file=sys.stderr)
        sys.exit(1)

    pulled = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = os.path.join("data", str(args.year))
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "top100.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            r["pulled_at"] = pulled
            w.writerow(r)
    print(f"Wrote {len(rows)} players to {out_path}")


if __name__ == "__main__":
    main()
