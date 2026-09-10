from dataclasses import dataclass

@dataclass
class Player:
    name: str
    club: str
    value: int = 0

    sofascore_id: str | None = 0

    matches: float | None = 0
    rating: float | None = 0
    goals: float | None = 0
    assists: float | None = 0
    key_passes: float | None = 0
    minutes_played: float | None = 0
    tackles: float | None = 0
    interceptions: float | None = 0
    dribbled_past: float | None = 0
    big_chances_created: float | None = 0
    accurate_passes: float | None = 0
    total_passes: float | None = 0