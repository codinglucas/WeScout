from transfermarkt_scrapper import get_transfermarkt_player_list
from selenium import webdriver
import re
import json
from datetime import datetime


    # --------------------
    #   helper methods

CACHE_FILE = "player_cache.json"

def load_cache():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as file:
        json.dump(cache, file, indent=4, ensure_ascii=False)



def normalize_year(year):
    year = str(year)
    if "/" in year:
        year = int(year.split("/")[1])
        year = 2000 + year

    year = int(year)

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


def retrieve_year_based_seasons(nav, player): #update seasons attr of each player
    current_year = int(datetime.now().year)

    desired_years = []
    desired_years.extend([current_year, current_year-1, current_year-2])

    print(f"desired years {desired_years}")

    print("Running retrieve_year_based_seasons()")

    nav.get(f"https://www.sofascore.com/player/x/{player.sofascore_id}")
    url = f"https://api.sofascore.com/api/v1/player/{player.sofascore_id}/statistics/seasons"
    
    data = fetch_json(nav, url) #data = JSON-based dict

    if data == None:
        print("No data found in RYBS")

    else:
        for x in data['uniqueTournamentSeasons']:     
                for season in x["seasons"]:
                    year = normalize_year(season['year'])
                    if year in desired_years:
                        tournament_id = x["uniqueTournament"]["id"]
                        new_dict = {"tournament_id": tournament_id, "season_id": season["id"], "year": normalize_year(season['year']), "name": season["name"]}

                        player.seasons.append(new_dict)
                    else:
                        print(f"I disconsidered {season["name"]}. {year}")
                
        return 
        

    
def get_recent_seasons_ids(nav, player_id, limit=3, data=None):
    print("\nRunning get_recent_seasons")
    print(f"Running seasons for {player_id}\n")

    if data == None:

        url = f"https://api.sofascore.com/api/v1/player/{player_id}/statistics/seasons"

        data = fetch_json(nav, url) #data = JSON-based dict

        if data == None:
            print("No data found in get_recent_seasons fetch")
            return[]

    print("GET RECENT SEASONS ID type(data):", type(data))

    entries = []
    for entry in data.get("uniqueTournamentSeasons", []):
        tournament_id = entry["uniqueTournament"]["id"]
        print("tournament id ", tournament_id)

        for season in entry["seasons"]:
            entries.append((tournament_id, season["id"]))
            year = normalize_year(season['year'])
            print("season id ", season["id"])
            print("year", year)

    print(f"\n{player_id} sucessfully found Tournament and Seasons IDs")
    print(f"Printing entries: {entries}")

    return entries[:limit]


def normalize_rating(nav, player):
    player.rating = player.rating / player.matches


def get_season_stats(nav, player):

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


    for season in player.seasons:
        url = (
            f"https://api.sofascore.com/api/v1/player/{player.sofascore_id}"
            f"/unique-tournament/{season['tournament_id']}/season/{season['season_id']}/statistics/overall"
        )

        data = fetch_json(nav, url)['statistics']

        if data == None:
            print("No data available for get_season_stats")
            continue

        for sofascore_key, player_attribute in STAT_TO_ATTR.items():
            if sofascore_key in data.keys(): #checar se o player tiver esse stats

                if sofascore_key == "rating":
                    value = (data.get(sofascore_key) * data.get("appearances")) #sum current player atr value + one scrapped
                    value += getattr(player, player_attribute)
                    setattr(player, player_attribute, value)

                else:
                    value = getattr(player, player_attribute) + data.get(sofascore_key) #sum current player atr value + one scrapped
                    setattr(player, player_attribute, value)
            else:
                print(player.name, sofascore_key, ": ", "Not found")


        
    return

    # ----------------------------
    #        Main methods

def get_player_id(nav, players, break_1=True):

    player_cache_file = load_cache()

    for player in players:

        if player.name not in player_cache_file:
            match = match_id(nav, player)

            if match:
                player.sofascore_id = match.group(1)
                print(player.name, "->", player.sofascore_id)

                player_cache_file[player.name] = player.sofascore_id
                save_cache(player_cache_file)

            else:
                print(player.name, "-> ID not found")

        else:
            player.sofascore_id = player_cache_file[player.name]



def get_players_stats(nav, players, break_1=True):


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

        seasons = retrieve_year_based_seasons(nav, player)
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
        nav.get(f"https://www.sofascore.com/player/x/{player.sofascore_id}")
        retrieve_year_based_seasons(nav, player)
        #get_season_stats(nav, player)
        #normalize_rating(nav, player)

    return players






    # -----------------------------
    #   Execution
