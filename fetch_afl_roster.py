import argparse
import csv
import os
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


def _read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def keep_every_player_ever_seen(season, season_dir, all_rows):
    """A player must never disappear from the site once he has been on it.

    MLB's roster endpoint only lists who is on a club *right now*, so a player who is
    released, returned to his organization, or moved off the list vanishes from it. If
    roster.csv were simply overwritten, he (and every game log built from the roster)
    would vanish too. So the new roster is merged with the existing file:
      1. anyone already in roster.csv who is not on MLB's list today is kept as-is;
      2. anyone who appears in this season's lineups or pitching appearances but has
         never been on the roster file is added, so nobody who played is left out.
    Players still on MLB's list always use the fresh row (new team, jersey, age...)."""
    have = {str(r["player_id"]) for r in all_rows}

    kept = 0
    for old in _read_csv(os.path.join(season_dir, "roster.csv")):
        pid = str(old.get("player_id", ""))
        if pid and pid not in have:
            all_rows.append({k: old.get(k, "") for k in ROSTER_FIELDS})
            have.add(pid)
            kept += 1

    played = {}
    for row in _read_csv(os.path.join(season_dir, "batting_lineups.csv")):
        played.setdefault(str(row.get("player_id", "")), {
            "name": row.get("player_name", ""), "team": row.get("team_name", ""),
            "jersey": row.get("jersey_number", ""), "pos": (row.get("position_code", ""), row.get("position_name", ""), row.get("position_abbreviation", "")),
        })
    for row in _read_csv(os.path.join(season_dir, "pitcher_appearances.csv")):
        played.setdefault(str(row.get("pitcher_id", "")), {
            "name": row.get("pitcher_name", ""), "team": row.get("team_name", ""),
            "jersey": "", "pos": ("1", "Pitcher", "P"),
        })

    added = 0
    for pid, info in played.items():
        if not pid or pid in have:
            continue
        entry = {
            "person": {"id": int(pid) if pid.isdigit() else pid, "fullName": info["name"]},
            "jerseyNumber": info["jersey"],
            "position": {"code": info["pos"][0], "name": info["pos"][1], "abbreviation": info["pos"][2]},
        }
        try:
            row = build_roster_row(season, info["team"], entry)
        except Exception as e:
            print(f"  could not fetch bio for {info['name']} ({e}); saving basic row.")
            row = {k: "" for k in ROSTER_FIELDS}
            row.update({"season": season, "team": info["team"], "player_id": pid, "full_name": info["name"],
                        "jersey_number": info["jersey"], "position_code": info["pos"][0],
                        "position_name": info["pos"][1], "position_abbreviation": info["pos"][2]})
        all_rows.append(row)
        have.add(pid)
        added += 1

    if kept or added:
        print(f"Kept {kept} player(s) MLB no longer lists and added {added} who played but were never on the roster file.")
    return all_rows


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

    season_dir = os.path.join(args.output_dir, str(args.season))
    os.makedirs(season_dir, exist_ok=True)
    all_rows = keep_every_player_ever_seen(args.season, season_dir, all_rows)
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
