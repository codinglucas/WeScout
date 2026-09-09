from transfermarkt_scrapper import get_transfermarkt_player_list
from selenium import webdriver
import re
import json

#MAX_AGE = input("Max_age: ")
#MIN_AGE = input("Min_age: ")
#MAX_PRICE = input("Max_price: ")
#POSITION_ID = input("Position_id: ")

players = get_transfermarkt_player_list()

# helper methods
def get_match(nav, player_name):
    id_url = f"https://www.sofascore.com/api/v1/search/all?q={player_name}"
    nav.get(id_url)

    text = nav.find_element("tag name", "body").text

    match = re.search(
        r'entity\s+id\s+(\d+)',
        text
    )

    return match




def calculate_p90_pmatches(decision, player):
    #matches = player.matches

    for key, value in list(player.__dict__.items()):
        if key in ['name', 'club', 'minutes_played', 'value', 'sofascore_id', 'matches']:
            continue
        if decision == 1:
            player.__dict__[key] = (90 * value) / player.minutes_played
        else: 
            player.__dict__[key] = value / player.matches



def fetch_json(nav, url):
    script = """
    const url = arguments[0];
    const callback = arguments[arguments.length - 1];
    fetch(url, { headers: { "Accept": "application/json" } })
        .then(r => r.text())
        .then(text => callback({status: "ok", body: text}))
        .catch(err => callback({status: "error", body: String(err)}));
    """
    result = nav.execute_async_script(script, url)
    if result["status"] != "ok":
        return None
    try:
        return json.loads(result["body"])
    except json.JSONDecodeError:
        return None

    
def get_recent_seasons(nav, player_id, limit=3):
    url = f"https://api.sofascore.com/api/v1/player/{player_id}/statistics/seasons"

    data = fetch_json(nav, url)

    if not data:
        return[]

    entries = []
    for entry in data.get("uniqueTournamentSeasons", []):
        tournament_id = entry["uniqueTournament"]["id"]
        for season in entry["seasons"]:
            entries.append((tournament_id, season["id"]))
    return entries[:limit]


def get_season_stats(nav, player_id, tournament_id, season_id):
    url = (
        f"https://api.sofascore.com/api/v1/player/{player_id}"
        f"/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    )
    data = fetch_json(nav, url)
    if not data:
        print("Not data")
        return None
    return data.get("statistics")



    #Main methods



def get_player_id(nav, players):

    for player in players:

        match = get_match(nav, player.name)

        if match:
            player.sofascore_id = match.group(1)
            print(player.name, "->", player.sofascore_id)

        else:
            print(player.name, "-> ID not found")
        break



def get_players_stats(nav, players):

    STAT_TO_ATTR = {
        "rating": "rating",
        "appearances": "matches",
        "goals": "goals",
        "assists": "assists",
        "keyPasses": "key_passes",
        "minutesPlayed": "minutes_played",
        "tackles": "tackles",
        "interceptions": "interceptions",
        "dribbledPast": "dribbled_past",
        "bigChancesCreated": "big_chances_created",
        "accuratePasses": "accurate_passes",
        "totalPasses": "total_passes",
    }

    for player in players:

        seasons = get_recent_seasons(nav, player.sofascore_id, limit=3)
        count = 0
        for tournament_id, season_id in seasons:
            print("Tournament_Id", tournament_id)
            print("Season_id", season_id)
            print(f"Season {count}")
            count += 1
            season_stats = get_season_stats(nav, player.sofascore_id, tournament_id, season_id)

            for x in STAT_TO_ATTR.keys():
                if x in season_stats.keys():
                    print(season_stats[x])
                else:
                    print(x, "Not found")
        break





    
if __name__ == "__main__":
    nav = webdriver.Firefox()

    get_player_id(nav, players)

    nav.get(f"https://www.sofascore.com/player/x/{players[0].sofascore_id}")

    get_players_stats(nav, players)

   