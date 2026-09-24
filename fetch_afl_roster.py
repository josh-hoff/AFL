import argparse
import csv
import time
from datetime import datetime

ROSTER_URL = "https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
PERSON_URL = "https://statsapi.mlb.com/api/v1/people/{person_id}"
TEAM_URL = "https://statsapi.mlb.com/api/v1/teams/{team_id}"

AFL_TEAMS = {
    490: "Peoria Javelinas",
    454: "Glendale Desert Dogs",
    542: "Surprise Saguaros",
    544: "Scottsdale Scorpions",
    555: "Mesa Solar Sox",
    527: "Salt River Rafters",
}

ROSTER_FIELDS = [
    "season", "team", "player_id", "full_name", "jersey_number",
    "position_code", "position_name", "position_abbreviation",
    "org_id", "org_name", "birth_date", "age", "birth_city", "birth_state",
    "birth_country", "height", "weight", "bats", "throws",
    "draft_year", "mlb_debut_date",
]

_org_name_cache = {}


def fetch_roster(team_id, season):
    import requests

    resp = requests.get(ROSTER_URL.format(team_id=team_id), params={"season": season}, timeout=30)
    resp.raise_for_status()
    return resp.json().get("roster", [])


def fetch_person(person_id, hydrate_current_team=False):
    import requests

    params = {}
    if hydrate_current_team:
        params["hydrate"] = "currentTeam"
    resp = requests.get(PERSON_URL.format(person_id=person_id), params=params, timeout=30)
    resp.raise_for_status()
    people = resp.json().get("people", [])
    return people[0] if people else {}


def fetch_team_name(team_id):
    import requests

    if team_id in _org_name_cache:
        return _org_name_cache[team_id]

    resp = requests.get(TEAM_URL.format(team_id=team_id), timeout=30)
    resp.raise_for_status()
    teams = resp.json().get("teams", [])
    name = teams[0].get("name", "") if teams else ""
    _org_name_cache[team_id] = name
    return name


def resolve_org(roster_entry, person_bio):
    parent_team_id = roster_entry.get("parentTeamId")
    if parent_team_id:
        return parent_team_id, fetch_team_name(parent_team_id)

    person_with_team = fetch_person(person_bio["id"], hydrate_current_team=True)
    current_team = person_with_team.get("currentTeam", {})
    if not current_team:
        return "", ""

    parent_org_id = current_team.get("parentOrgId")
    if parent_org_id:
        return parent_org_id, fetch_team_name(parent_org_id)

    return current_team.get("id", ""), current_team.get("name", "")


def build_roster_row(season, team_name, roster_entry):
    person_id = roster_entry.get("person", {}).get("id")
    person_bio = fetch_person(person_id)
    time.sleep(0.2)

    org_id, org_name = resolve_org(roster_entry, {"id": person_id})
    time.sleep(0.2)

    position = roster_entry.get("position", {})

    return {
        "season": season,
        "team": team_name,
        "player_id": person_id,
        "full_name": roster_entry.get("person", {}).get("fullName", ""),
        "jersey_number": roster_entry.get("jerseyNumber", ""),
        "position_code": position.get("code", ""),
        "position_name": position.get("name", ""),
        "position_abbreviation": position.get("abbreviation", ""),
        "org_id": org_id,
        "org_name": org_name,
        "birth_date": person_bio.get("birthDate", ""),
        "age": person_bio.get("currentAge", ""),
        "birth_city": person_bio.get("birthCity", ""),
        "birth_state": person_bio.get("birthStateProvince", ""),
        "birth_country": person_bio.get("birthCountry", ""),
        "height": person_bio.get("height", ""),
        "weight": person_bio.get("weight", ""),
        "bats": person_bio.get("batSide", {}).get("description", ""),
        "throws": person_bio.get("pitchHand", {}).get("description", ""),
        "draft_year": person_bio.get("draftYear", ""),
        "mlb_debut_date": person_bio.get("mlbDebutDate", ""),
    }


def main():
    parser = argparse.ArgumentParser(description="Fetch AFL team rosters with bio info and MLB organization.")
    parser.add_argument(
        "season", type=int, nargs="?", default=datetime.now().year,
        help="Season year (defaults to the current year if omitted)",
    )
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()

    all_rows = []

    for team_id, team_name in AFL_TEAMS.items():
        print(f"Fetching {team_name} roster...")
        try:
            roster = fetch_roster(team_id, args.season)
        except Exception as e:
            print(f"  failed to fetch roster ({e}), skipping team.")
            continue

        for i, entry in enumerate(roster, 1):
            player_name = entry.get("person", {}).get("fullName", "unknown")
            print(f"  [{i}/{len(roster)}] {player_name} ...", end=" ")
            try:
                row = build_roster_row(args.season, team_name, entry)
                all_rows.append(row)
                print(f"{row['org_name'] or 'org unresolved'}")
            except Exception as e:
                print(f"failed ({e}), skipping player.")

    import os
    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)
    out_path = os.path.join(season_dir, "roster.csv")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ROSTER_FIELDS)
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print()
    print(f"Done. {len(all_rows)} players saved to {out_path}")


if __name__ == "__main__":
    main()
