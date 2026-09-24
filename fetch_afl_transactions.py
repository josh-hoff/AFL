import argparse
import csv
import os
import re
import time
from datetime import datetime, timedelta

TRANSACTIONS_URL = "https://statsapi.mlb.com/api/v1/transactions"
AFL_SPORT_ID = 17

AFL_TEAMS = {
    490: "Peoria Javelinas",
    454: "Glendale Desert Dogs",
    542: "Surprise Saguaros",
    544: "Scottsdale Scorpions",
    555: "Mesa Solar Sox",
    527: "Salt River Rafters",
}

TRANSACTION_FIELDS = [
    "season", "team", "date", "player_id", "player_name",
    "type_code", "type_desc", "from_team", "to_team", "description",
]


def load_schedule_dates(season, output_dir):
    path = os.path.join(output_dir, str(season), "schedule.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No schedule found at {path}. Run fetch_afl_schedule.py {season} first."
        )
    dates = []
    with open(path, "r", newline="") as f:
        for row in csv.DictReader(f):
            m = re.match(r"(\d{4}-\d{2}-\d{2})", row.get("date", ""))
            if m:
                dates.append(m.group(1))
    if not dates:
        raise ValueError("No valid dates found in schedule.csv")
    return min(dates), max(dates)


def to_mmddyyyy(iso_date):
    year, month, day = iso_date.split("-")
    return f"{month}/{day}/{year}"


def fetch_transactions(team_id, start_date_mmddyyyy, end_date_mmddyyyy):
    import requests

    params = {
        "teamId": team_id,
        "startDate": start_date_mmddyyyy,
        "endDate": end_date_mmddyyyy,
        "sportId": AFL_SPORT_ID,
    }
    resp = requests.get(TRANSACTIONS_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("transactions", [])


def extract_transaction(season, team_name, txn):
    person = txn.get("person", {})
    from_team = txn.get("fromTeam", {})
    to_team = txn.get("toTeam", {})
    return {
        "season": season,
        "team": team_name,
        "date": txn.get("date", ""),
        "player_id": person.get("id", ""),
        "player_name": person.get("fullName", ""),
        "type_code": txn.get("typeCode", ""),
        "type_desc": txn.get("typeDesc", ""),
        "from_team": from_team.get("name", ""),
        "to_team": to_team.get("name", ""),
        "description": txn.get("description", ""),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch AFL roster transactions (assignments, releases, etc.) for a season."
    )
    parser.add_argument(
        "season", type=int, nargs="?", default=datetime.now().year,
        help="Season year (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data")
    parser.add_argument(
        "--lead-days", type=int, default=45,
        help="Days before the season's first game to start searching for transactions "
        "(roster assignments typically begin well before opening day)",
    )
    args = parser.parse_args()

    start_date, end_date = load_schedule_dates(args.season, args.output_dir)
    search_start_dt = datetime.strptime(start_date, "%Y-%m-%d") - timedelta(days=args.lead_days)
    start_mmddyyyy = to_mmddyyyy(search_start_dt.strftime("%Y-%m-%d"))
    end_mmddyyyy = to_mmddyyyy(end_date)

    all_rows = []

    for team_id, team_name in AFL_TEAMS.items():
        print(f"Fetching transactions for {team_name} ({search_start_dt.strftime('%Y-%m-%d')} to {end_date}) ...", end=" ")
        try:
            transactions = fetch_transactions(team_id, start_mmddyyyy, end_mmddyyyy)
        except Exception as e:
            print(f"failed ({e}), skipping team.")
            continue

        for txn in transactions:
            all_rows.append(extract_transaction(args.season, team_name, txn))

        print(f"{len(transactions)} transactions.")
        time.sleep(0.3)

    all_rows.sort(key=lambda r: (r["team"], r["date"]))

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)
    out_path = os.path.join(season_dir, "transactions.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRANSACTION_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(all_rows)} transactions saved to {out_path}")


if __name__ == "__main__":
    main()
