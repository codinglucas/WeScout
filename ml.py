from sofascore import execute, fetch_json
from selenium import webdriver

players = execute()

def get_league_avg(nav):
    limit = 10
    offset = 0
    goal_sum = 0
    attribute = "goals"

    for player in players:
        for season in player.seasons:
            url = f"https://www.sofascore.com/api/v1/unique-tournament/{season["tournament_id"]}/season/{season["season_id"]}/statistics?limit={limit}&offset={offset}&order=-{attribute}&accumulation=total&fields=goals,successfulDribbles,tackles,assists,accuratePassesPercentage,rating&filters=position.in.D~M~F"

            data = fetch_json(nav, url)

            if data == None:
                print("No data was found")
                return []

            for result in data["results"]:
                goals = result["goals"]
                player_name = result["player"]["name"]

                goal_sum += goals

                print(f"Added {goals} to goal sum (current total: {goal_sum}). Player: {player_name} \n")
            break
        break

nav = webdriver.Firefox()
nav.get("https://www.sofascore.com")
get_league_avg(nav)

            