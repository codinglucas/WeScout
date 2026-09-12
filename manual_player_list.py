from dataclass import Player
from typing import List, Optional

players: List[Player] = []



def create_manual_list():
    big_list = [
        ["Alexander Isak", "Liverpool"],
        ["Florian Wirtz", "Liverpool"],
        ["Benjamin Šeško", "Manchester United"],
        ["Nick Woltemade", "Newcastle"],
        ["Victor Osimhen", "Galatasaray"]
    ]

    for name, club in big_list:
        players.append(Player(name=name, club=club))

    return players