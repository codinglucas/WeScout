from bs4 import BeautifulSoup
import requests

url = "https://www.transfermarkt.com/detailsuche/spielerdetail/suche/58179874"

max_age = 20
max_price = 5000000
position_id = 6
min_age = 0
'''max_age = input("Enter the maximum age (default is 20): ")
max_price = input("Enter the maximum price in milions (default is 5000000): ")
position_id = input("Enter the position ID: ")
'''
form_data = {
    "DetailsucheSaved[vorname]": "",
    "DetailsucheSaved[name]": "",
    "DetailsucheSaved[name_anzeige]": "",
    "DetailsucheSaved[passname]": "",
    "DetailsucheSaved[genaue_suche]": "0",
    "DetailsucheSaved[geb_ort]": "",
    "DetailsucheSaved[genaue_suche_geburtsort]": "0",
    "DetailsucheSaved[land_id]": "",
    "DetailsucheSaved[zweites_land_id]": "",
    "DetailsucheSaved[geb_land_id]": "",
    "DetailsucheSaved[kontinent_id]": "4", #confederation_id
    "DetailsucheSaved[geburtstag]": "doesn't+matter",
    "DetailsucheSaved[geburtsmonat]": "doesn't+matter",
    "DetailsucheSaved[geburtsjahr]": "",
    "DetailsucheSaved[minAlter]": f"{min_age}",
    "DetailsucheSaved[maxAlter]": f"{max_age}",
    "DetailsucheSaved[age]": f"0;{max_age}",
    "DetailsucheSaved[minJahrgang]": "1850",
    "DetailsucheSaved[maxJahrgang]": "2015",
    "DetailsucheSaved[jahrgang]": "1850;2015",
    "DetailsucheSaved[minGroesse]": "0",
    "DetailsucheSaved[maxGroesse]": "220",
    "DetailsucheSaved[groesse]": "0;220",
    "speichern": "Submit+search",
    "DetailsucheSaved[hauptposition_id]": f"{position_id}",        # ex: 6 = Atacante
    "DetailsucheSaved[nebenposition_id_1]": "",
    "DetailsucheSaved[nebenposition_id_2]": "",
    "DetailsucheSaved[minMarktwert]": "0",
    "DetailsucheSaved[maxMarktwert]": f"{max_price}",
    "DetailsucheSaved[marktwert]": f"0;{max_price}",
    "DetailsucheSaved[fuss_id]": ["",""],            # Array vira lista
    "DetailsucheSaved[captain]": ["",""],
    "DetailsucheSaved[rn]": "0",
    "DetailsucheSaved[wettbewerb_id]": "",
    "DetailsucheSaved[w_land_id]": "",
    "DetailsucheSaved[minNmSpiele]": "0",
    "DetailsucheSaved[maxNmSpiele]": "300",
    "DetailsucheSaved[nm_spiele]": "0;300",
    "DetailsucheSaved[trans_id]": "0",
    "DetailsucheSaved[aktiv]": "0",
    "DetailsucheSaved[vereinslos]": "0",
    "DetailsucheSaved[leihen]": "0",
}

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Content-Type": "application/x-www-form-urlencoded",
}

resp = requests.post(url, data=form_data, headers=headers)

soup = BeautifulSoup(resp.text, "html.parser")
table = soup.find("table", class_="items")

club_list = []

def get_int_price(price_list):
    actual_int_price = []
    for price in price_list:
        price = list(price)
        price.remove("€")

        if "m" in price:
            price.remove("m")
            price = "".join(price)
            price = float(price)
            price *= 1000000
        elif "k" in price:
            price.remove("k")
            price = "".join(price)
            price = float(price)
            price *= 1000

        actual_int_price.append(price)

    return actual_int_price

def extract_player_club(tr):
    tds = tr.find_all("td")

    current_club = tds[7]
    img = current_club.find("img", alt=True)

    return club_list.append(img["alt"])



    
 
def get_player_list(min_age, max_age, max_price, position_id):

    url = "https://www.transfermarkt.com/detailsuche/spielerdetail/suche/58282030" #random TF url to pass data into and get a new search

    form_data = {
    "DetailsucheSaved[vorname]": "",
    "DetailsucheSaved[name]": "",
    "DetailsucheSaved[name_anzeige]": "",
    "DetailsucheSaved[passname]": "",
    "DetailsucheSaved[genaue_suche]": "0",
    "DetailsucheSaved[geb_ort]": "",
    "DetailsucheSaved[genaue_suche_geburtsort]": "0",
    "DetailsucheSaved[land_id]": "",
    "DetailsucheSaved[zweites_land_id]": "",
    "DetailsucheSaved[geb_land_id]": "",
    "DetailsucheSaved[kontinent_id]": "4", #confederation_id
    "DetailsucheSaved[geburtstag]": "doesn't+matter",
    "DetailsucheSaved[geburtsmonat]": "doesn't+matter",
    "DetailsucheSaved[geburtsjahr]": "",
    "DetailsucheSaved[minAlter]": f"{min_age}",
    "DetailsucheSaved[maxAlter]": f"{max_age}",
    "DetailsucheSaved[age]": f"0;{max_age}",
    "DetailsucheSaved[minJahrgang]": "1850",
    "DetailsucheSaved[maxJahrgang]": "2015",
    "DetailsucheSaved[jahrgang]": "1850;2015",
    "DetailsucheSaved[minGroesse]": "0",
    "DetailsucheSaved[maxGroesse]": "220",
    "DetailsucheSaved[groesse]": "0;220",
    "speichern": "Submit+search",
    "DetailsucheSaved[hauptposition_id]": f"{position_id}",        # ex: 6 = Atacante
    "DetailsucheSaved[nebenposition_id_1]": "",
    "DetailsucheSaved[nebenposition_id_2]": "",
    "DetailsucheSaved[minMarktwert]": "0",
    "DetailsucheSaved[maxMarktwert]": f"{max_price}",
    "DetailsucheSaved[marktwert]": f"0;{max_price}",
    "DetailsucheSaved[fuss_id]": ["",""],            # Array vira lista
    "DetailsucheSaved[captain]": ["",""],
    "DetailsucheSaved[rn]": "0",
    "DetailsucheSaved[wettbewerb_id]": "",
    "DetailsucheSaved[w_land_id]": "",
    "DetailsucheSaved[minNmSpiele]": "0",
    "DetailsucheSaved[maxNmSpiele]": "300",
    "DetailsucheSaved[nm_spiele]": "0;300",
    "DetailsucheSaved[trans_id]": "0",
    "DetailsucheSaved[aktiv]": "0",
    "DetailsucheSaved[vereinslos]": "0",
    "DetailsucheSaved[leihen]": "0",
    }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) Gecko/20100101 Firefox/141.0"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    resp = requests.post(url, data=form_data, headers=headers)

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="items")

    if table:
        links = table.select('td.hauptlink a[href*="/profil/spieler/"]')
        print("ok")
    else:
        print('Could not find: \ntd.hauptlink a[href*="/profil/spieler/"]')
        


    players_list = []
    for a in links:
        players_list.append(a.get_text())



    club_list = []
    for tr in table.tbody.find_all("tr", recursive=False):
        name = tr.select_one("td.hauptlink a")
        name = name.text.strip() if name else "N/A"

        tds = tr.find_all("td")

        current_club = tds[7]
        img = current_club.find("img", alt=True)

        club_list.append(img["alt"])



    price = table.select("td.rechts.hauptlink")
    price_list = []
    for c in price:
        price_list.append(c.get_text(strip=True))

    int_price_list = get_int_price(price_list)




    return players_list, club_list, price_list, int_price_list


