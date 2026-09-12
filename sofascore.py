from transfermarkt_scrapper import get_transfermarkt_player_list
from selenium import webdriver
import re
import json
from datetime import datetime


    # --------------------
    #   helper methods


def normalize_year(year):
    str(year)
    #print(data.items())
    if "/" in year:
        year = int(year.split("/")[1])
        year = 2000 + year


    return year


def match_id(nav, player): # match player for his ID
    first_club_word = player.club.split()[0] 
    last_name = player.name.split()[-1] 

    queries = [
        f"{player.name} {first_club_word}",
        f"{last_name} {first_club_word}",
        f"{last_name}"
    ]

    match = None

    for query in queries:
        if not query.strip(): 
            continue

        id_url = f"https://www.sofascore.com/api/v1/search/all?q={query}"
        
        nav.get(id_url)
        text = nav.find_element("tag name", "body").text
        
        match = re.search(r'entity\s+id\s+(\d+)', text)
        print(f"Match data type for {player.name}: {type(match)}")
        
        if match is not None:
            break  

    return match





def fetch_json(nav, url):
    print(f"\nFETCH to the following url {url}")

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
        return json.loads(result["body"]) #transforms result into Py dict
    except json.JSONDecodeError:
        return None


def retrieve_year_based_seasons(nav, player):
    print("Running retrieve_year_based_seasons()")
    nav.get(f"https://www.sofascore.com/player/x/{player.sofascore_id}")

    url = f"https://api.sofascore.com/api/v1/player/{player.sofascore_id}/statistics/seasons"
    
    data = fetch_json(nav, url) #data = JSON-based dict

    if data == None:
        print("No data found in RYBS")
    else:
        for x in data['uniqueTournamentSeasons']:
            year = x['seasons'][0]['year']

            #if (normalize_year(year) in desired_years):
        

    
    return

    
def get_recent_seasons_ids(nav, player_id, limit=3):
    print("\nRunning get_recent_seasons")
    print(f"Running seasons for {player_id}\n")


    url = f"https://api.sofascore.com/api/v1/player/{player_id}/statistics/seasons"

    data = fetch_json(nav, url) #data = JSON-based dict

    if data == None:
        print("No data found in get_recent_seasons fetch")
        return[]

    print("GET RECENT SEASONS ID type(data):", type(data))
    #year = retrieve_year(data)

    entries = []
    for entry in data.get("uniqueTournamentSeasons", []):
        tournament_id = entry["uniqueTournament"]["id"]
        print("tournament id ", tournament_id)

        for season in entry["seasons"]:
            entries.append((tournament_id, season["id"]))
            print("season id ", season["id"])

    print(f"\n{player_id} sucessfully found Tournament and Seasons IDs")
    print(f"Printing entries: {entries}")

    return entries[:limit]






def get_season_stats(nav, player_id, tournament_id, season_id):
    url = (
        f"https://api.sofascore.com/api/v1/player/{player_id}"
        f"/unique-tournament/{tournament_id}/season/{season_id}/statistics/overall"
    )

    data = fetch_json(nav, url)

    if data == None:
        print("No data available for get_season_stats")
        return None
    
    return data.get("statistics")












    # ----------------------------
    #        Main methods








def get_player_id(nav, players, break_1=True):

    for player in players:

        match = match_id(nav, player)

        if match:
            player.sofascore_id = match.group(1)
            print(player.name, "->", player.sofascore_id)

        else:
            print(player.name, "-> ID not found")

        if break_1:
            break



def get_players_stats(nav, players, break_1=False):


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
        print(f"\n\n\nPlayer {player.name} has {len(seasons)} seasons. Here are them: \n {seasons}")

        count = 0

        for tournament_id, season_id in seasons:
            print("Tournament_Id", tournament_id)
            print("Season_id", season_id)
            print(f"Season {count}")

            count += 1

            player_season_stats = get_season_stats(nav, player.sofascore_id, tournament_id, season_id)            

            for sofascore_key, player_attribute in STAT_TO_ATTR.items():
                if sofascore_key in player_season_stats.keys(): #checar se o player tiver esse stats
                    value = getattr(player, player_attribute) + player_season_stats.get(sofascore_key)
                    setattr(player, player_attribute, value)
                else:
                    print(player.name, sofascore_key, ": ", "Not found")

        if break_1:
            break

    return players



def execute():

    from manual_player_list import create_manual_list

    players = create_manual_list()
    nav = webdriver.Firefox()

    get_player_id(nav, players, break_1=False) #update player.sofascore_id

    for player in players:
        print(player.sofascore_id)

    for player in players:
        nav.get(f"https://www.sofascore.com/player/x/{player.sofascore_id}")
        players = get_players_stats(nav, players)

    return players






    # -----------------------------
    #   Execution


    
if __name__ == "__main__":
    from manual_player_list import create_manual_list

    players = create_manual_list()
    nav = webdriver.Firefox()

    get_player_id(nav, players, break_1=False)

    for player in players:

        retrieve_year_based_seasons(nav, player)

        break

    #execute()