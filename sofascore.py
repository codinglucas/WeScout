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
def get_match(nav, player):
    id_url = f"https://www.sofascore.com/api/v1/search/all?q={player.name} {player.club.split()[0]}"
    nav.get(id_url)


    text = nav.find_element("tag name", "body").text

    match = re.search(
        r'entity\s+id\s+(\d+)',
        text
    )


    if match == None:
        id_url = f"https://www.sofascore.com/api/v1/search/all?q={player.name.split()[-1]} {player.club.split()[0]}"
        nav.get(id_url)

        text = nav.find_element("tag name", "body").text

        match = re.search(
                r'entity\s+id\s+(\d+)',
                text
            )

    print(player.name, "url: ", id_url)
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
    print(f"fetch to the following url {url}")
    script = """
    const url = arguments[0];
    const callback = arguments[arguments.length - 1];
    fetch(url, { headers: { "Accept": "application/json" } })
        .then(r => r.text())
        .then(text => callback({status: "ok", body: text}))
        .catch(err => callback({status: "error", body: String(err)}));
    """
    result = nav.execute_async_script(script, url)
    print("Raw result")
    print(result)
    if result["status"] != "ok":
        return None
    try:
        return json.loads(result["body"])
    except json.JSONDecodeError:
        return None

    
def get_recent_seasons_ids(nav, player_id, limit=3):
    print("Running get_recent_seasons")
    url = f"https://api.sofascore.com/api/v1/player/{player_id}/statistics/seasons"

    data = fetch_json(nav, url) #data = dict of API

    if not data:
        print("no data in get_recent_seasons fetch")
        return[]

    entries = []
    for entry in data.get("uniqueTournamentSeasons", []):
        tournament_id = entry["uniqueTournament"]["id"]
        #print("tournament id ", tournament_id)
        for season in entry["seasons"]:
            entries.append((tournament_id, season["id"]))
            #print("season id ", season["id"])
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

        match = get_match(nav, player)

        if match:
            player.sofascore_id = match.group(1)
            print(player.name, "->", player.sofascore_id)

        else:
            print(player.name, "-> ID not found")



def get_players_stats(nav, players):

    print("get_players_stats being called")

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

        nav.get(f"https://www.sofascore.com/player/x/{player.sofascore_id}")

        #print("Player name ", player.name, "player id", player.sofascore_id)
        seasons = get_recent_seasons_ids(nav, player.sofascore_id, limit=3)
        print("\n\n\nseasons", seasons)


        count = 0


        for tournament_id, season_id in seasons:
            print("Tournament_Id", tournament_id)
            print("Season_id", season_id)
            print(f"Season {count}")
            count += 1
            player_season_stats = get_season_stats(nav, player.sofascore_id, tournament_id, season_id)

            print(player.name, "stats: ", player_season_stats)
            

            for sofascore_key, player_attribute in STAT_TO_ATTR.items():
                if sofascore_key in player_season_stats.keys(): #checar se o player tiver esse stats
                    value = getattr(player, player_attribute) + player_season_stats.get(sofascore_key)
                    setattr(player, player_attribute, value)
                else:
                    print(player.name, sofascore_key, ": ", "Not found")





    
if __name__ == "__main__":
    nav = webdriver.Firefox()

    get_player_id(nav, players)
    """get_players_stats(nav, players)

    for player in players:
        print("Initialization completed. now showing vars(player)")
        for var in vars(player):
            print(f"{player.name}, {var}: ", getattr(player, var))"""