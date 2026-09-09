from dataclasses import dataclass

@dataclass
class Player:
    name: str
    club: str
    value: int = 0

    sofascore_id: str | None = None

    matches: float | None = None
    rating: float | None = None
    goals: float | None = None
    assists: float | None = None
    key_passes: float | None = None
    minutes_played: float | None = None
    tackles: float | None = None
    interceptions: float | None = None
    dribbled_past: float | None = None
    big_chances_created: float | None = None
    accurate_passes: float | None = None
    total_passes: float | None = None