import re
from dataclasses import dataclass, asdict
from typing import List, Optional
from dataclass import Player
import requests
from bs4 import BeautifulSoup

#Initial values
MAX_AGE = 20
MIN_AGE = 0
MAX_PRICE = 5_000_000
POSITION_ID = 6


def parse_price(raw: str) -> int:
    raw = raw.strip()
    if not raw or raw == "-":
        return 0

    match = re.search(r"([\d.,]+)\s*([mk]?)", raw)
    if not match:
        return 0

    number_str, suffix = match.groups()
    number_str = number_str.replace(",", ".")
    try:
        number = float(number_str)
    except ValueError:
        return 0

    multiplier = {"m": 1_000_000, "k": 1_000}.get(suffix, 1)
    return int(number * multiplier)


def get_transfermarkt_player_list(
    min_age: int = MIN_AGE,
    max_age: int = MAX_AGE,
    max_price: int = MAX_PRICE,
    position_id: int = POSITION_ID,
) -> List[Player]:
    url = "https://www.transfermarkt.com/detailsuche/spielerdetail/suche/64678593"

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
        "DetailsucheSaved[kontinent_id]": "4",
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
        "DetailsucheSaved[hauptposition_id]": f"{position_id}",
        "DetailsucheSaved[nebenposition_id_1]": "",
        "DetailsucheSaved[nebenposition_id_2]": "",
        "DetailsucheSaved[minMarktwert]": "0",
        "DetailsucheSaved[maxMarktwert]": f"{max_price}",
        "DetailsucheSaved[marktwert]": f"0;{max_price}",
        "DetailsucheSaved[fuss_id]": ["", ""],
        "DetailsucheSaved[captain]": ["", ""],
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
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:141.0) "
            "Gecko/20100101 Firefox/141.0"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    with requests.Session() as session:
        session.headers.update(headers)
        resp = session.post(url, data=form_data)
        print(resp.status_code)


    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", class_="items")

    if not table or not table.tbody:
        print("No table found. Ending method")
        return []

    players: List[Player] = []

    # Single pass over each row: pull name, club and value together so they
    # can never fall out of alignment (previous version relied on 3 separate
    # selects staying in the same order).
    for tr in table.tbody.find_all("tr", recursive=False):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 8:
            continue  # skip header/spacer rows

        name_tag = tr.select_one("td.hauptlink a")
        name = name_tag.get_text(strip=True) if name_tag else "N/A"

        club = tr.select_one('td.zentriert a[href*="/verein/"] img')
        club = club["alt"] if club else "N/A"

        price_tag = tr.select_one("td.rechts.hauptlink")
        value = parse_price(price_tag.get_text(strip=True) if price_tag else "")

        players.append(Player(name=name, club=club, value=value))

    return players


if __name__ == "__main__":
    result = get_transfermarkt_player_list(MIN_AGE, MAX_AGE, MAX_PRICE, POSITION_ID)
    for p in result:
        print(p.name)
        print(p.club)
        print(p.value)