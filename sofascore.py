from selenium import webdriver
import re
from start import get_player_list
import pandas as pd

def create_benefit_cost_ratio_column(df, int_price_list):
    df["Actual Price"] = int_price_list 
    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")
    df["BCR"] = df["Rating"] / df["Actual Price"]
    return df

def calculate_per_90_stat(stat_value, minutes_played):
    """Calculate per 90 minutes stat"""
    try:
        if minutes_played == 0 or minutes_played == "N/A" or stat_value == "N/A":
            return 0
        return round((float(stat_value) * 90) / float(minutes_played), 2)
    except:
        return 0

def calculate_pass_completion(accurate_passes, total_passes):
    """Calculate pass completion percentage"""
    try:
        if total_passes == 0 or total_passes == "N/A" or accurate_passes == "N/A":
            return 0
        return round((float(accurate_passes) * 100) / float(total_passes), 2)
    except:
        return 0

def get_id(player_list):
    nav = webdriver.Firefox()
    id_list = []
    
    for player_name in player_list:
        url_research = f"https://www.sofascore.com/api/v1/search/all?q={player_name}"
        nav.get(url_research)
        html = nav.page_source

        match = re.search(r'<tr id="/results/0/entity/id".*?<span class="objectBox objectBox-number">(\d+)</span>', html)

        if match:
            entity_id = match.group(1)
            id_list.append(entity_id)
        else:
            print("ID não encontrado. Jogador: ", player_name)
            id_list.append("N/A")

    nav.close()
    return id_list

def get_player_data(player_list):
    """Fetch comprehensive player statistics"""
    id_list = get_id(player_list)
    nav = webdriver.Firefox()

    # Initialize all stat lists
    rating_list = []
    goal_list = []
    assists_list = []
    key_passes_list = []
    minutes_played_list = []
    tackles_list = []
    interceptions_list = []
    dribbled_past_list = []
    big_chances_created_list = []
    accurate_passes_list = []
    total_passes_list = []

    for id in id_list:
        if id == "N/A":
            # Append N/A for all stats if player ID not found
            rating_list.append("N/A")
            goal_list.append("N/A")
            assists_list.append("N/A")
            key_passes_list.append("N/A")
            minutes_played_list.append("N/A")
            tackles_list.append("N/A")
            interceptions_list.append("N/A")
            dribbled_past_list.append("N/A")
            big_chances_created_list.append("N/A")
            accurate_passes_list.append("N/A")
            total_passes_list.append("N/A")
            continue

        url_player_website = f"https://www.sofascore.com/api/v1/player/{id}/statistics"
        nav.get(url_player_website)
        html = nav.page_source

        # Rating
        match = re.search(r'id="/seasons/0/statistics/rating".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        rating_list.append(float(match.group(1)) if match else "N/A")

        # Goals
        goals = re.search(r'id="/seasons/0/statistics/goals".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        goal_list.append(goals.group(1) if goals else "N/A")

        # Assists
        assists = re.search(r'id="/seasons/0/statistics/assists".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        assists_list.append(assists.group(1) if assists else "N/A")

        # Key Passes
        key_passes = re.search(r'id="/seasons/0/statistics/keyPasses".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        key_passes_list.append(key_passes.group(1) if key_passes else "N/A")

        # Minutes Played
        minutes = re.search(r'id="/seasons/0/statistics/minutesPlayed".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        minutes_played_list.append(minutes.group(1) if minutes else "N/A")

        # Tackles
        tackles = re.search(r'id="/seasons/0/statistics/tackles".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        tackles_list.append(tackles.group(1) if tackles else "N/A")

        # Interceptions
        interceptions = re.search(r'id="/seasons/0/statistics/interceptions".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        interceptions_list.append(interceptions.group(1) if interceptions else "N/A")

        # Dribbled Past
        dribbled_past = re.search(r'id="/seasons/0/statistics/dribbledPast".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        dribbled_past_list.append(dribbled_past.group(1) if dribbled_past else "N/A")

        # Big Chances Created
        big_chances = re.search(r'id="/seasons/0/statistics/bigChancesCreated".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        big_chances_created_list.append(big_chances.group(1) if big_chances else "N/A")

        # Accurate Passes
        accurate = re.search(r'id="/seasons/0/statistics/accuratePasses".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        accurate_passes_list.append(accurate.group(1) if accurate else "N/A")

        # Total Passes
        total = re.search(r'id="/seasons/0/statistics/totalPasses".*?<span[^>]*?objectBox-number[^>]*?>([\d.]+)</span>', html)
        total_passes_list.append(total.group(1) if total else "N/A")

    nav.quit()

    return (id_list, rating_list, goal_list, assists_list, key_passes_list, 
            minutes_played_list, tackles_list, interceptions_list, dribbled_past_list,
            big_chances_created_list, accurate_passes_list, total_passes_list)

def dataframe_organizer(id_list, rating_list, price_list, goal_list, players_list, club_list, 
                       assists_list, key_passes_list, int_price_list, minutes_played_list,
                       tackles_list, interceptions_list, dribbled_past_list, 
                       big_chances_created_list, accurate_passes_list, total_passes_list):
    
    df = pd.DataFrame()

    df["Player"] = players_list
    df["Club"] = club_list
    df["Price"] = price_list
    df["Rating"] = rating_list
    df["Goals"] = goal_list
    df["Assists"] = assists_list
    df["Key Passes"] = key_passes_list
    df["ID"] = id_list
    df["Minutes Played"] = minutes_played_list
    df["Tackles"] = tackles_list
    df["Interceptions"] = interceptions_list
    df["Dribbled Past"] = dribbled_past_list
    df["Big Chances Created"] = big_chances_created_list
    df["Accurate Passes"] = accurate_passes_list
    df["Total Passes"] = total_passes_list

    # Calculate per 90 stats
    df["Tackles Per 90"] = df.apply(
        lambda row: calculate_per_90_stat(row["Tackles"], row["Minutes Played"]), axis=1
    )
    df["Interceptions Per 90"] = df.apply(
        lambda row: calculate_per_90_stat(row["Interceptions"], row["Minutes Played"]), axis=1
    )
    df["Dribbled Past Per 90"] = df.apply(
        lambda row: calculate_per_90_stat(row["Dribbled Past"], row["Minutes Played"]), axis=1
    )

    # Calculate pass completion percentage
    df["Pass Completion %"] = df.apply(
        lambda row: calculate_pass_completion(row["Accurate Passes"], row["Total Passes"]), axis=1
    )

    df = create_benefit_cost_ratio_column(df, int_price_list)

    return df

if __name__ == "__main__":
    min_age = 16
    max_age = 36
    max_price = 10000000
    position_id = 6

    player_list, club_list, price_list, int_price_list = get_player_list(min_age, max_age, max_price, position_id)

    (id_list, rating_list, goal_list, assists_list, key_passes_list, 
     minutes_played_list, tackles_list, interceptions_list, dribbled_past_list,
     big_chances_created_list, accurate_passes_list, total_passes_list) = get_player_data(player_list)

    df = dataframe_organizer(id_list, rating_list, price_list, goal_list, player_list, club_list, 
                            assists_list, key_passes_list, int_price_list, minutes_played_list,
                            tackles_list, interceptions_list, dribbled_past_list, 
                            big_chances_created_list, accurate_passes_list, total_passes_list)

    print(df[["Player", "Club", "Rating", "Goals", "Assists", "Key Passes", 
              "Tackles Per 90", "Interceptions Per 90", "Pass Completion %", "Price", "BCR"]])