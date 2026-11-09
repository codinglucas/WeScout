"""Cross-source player ID matching.

Strategy (docs/decisions.md, ADR-005):
  1. Normalise names: transliterate to ASCII (anyascii: Ø->O, ğ->g, Cyrillic...), lowercase,
     strip punctuation and suffixes.
  2. Date of birth is the strongest signal: a known DOB mismatch rejects the pair outright
     (that is what separates two different "Danilo"s). Day/month swaps score slightly lower.
  3. Fuzzy name score = best rapidfuzz token_set_ratio over name variants (display name,
     first+last, initial+last), so "M. Akanji" ~ "Manuel Akanji" and
     "Vinícius Júnior" ~ "Vinicius José Paixão de Oliveira Júnior".
  4. Same club in the same season adds a small bonus.
  5. Thresholds: >= AUTO -> matched automatically; >= REVIEW -> review list; else new player.
     Without a DOB on both sides a pair can never be auto-matched.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from anyascii import anyascii
from rapidfuzz import fuzz

AUTO = 0.90
REVIEW = 0.70
AMBIGUITY_MARGIN = 0.03

Decision = Literal["auto", "review", "new"]

_SUFFIXES = {"jr", "junior", "sr", "filho", "neto", "ii", "iii"}


def normalize_name(name: str) -> str:
    text = anyascii(name or "").lower()
    text = re.sub(r"[^a-z\s]", " ", text.replace("-", " ").replace("'", ""))
    return " ".join(text.split())


def core_tokens(name: str) -> list[str]:
    return [t for t in normalize_name(name).split() if t not in _SUFFIXES]


@dataclass(frozen=True)
class MatchSubject:
    """What the matcher knows about one player on one side."""

    key: str  # source:source_player_id, or the canonical player_id as text
    names: tuple[str, ...]
    date_of_birth: date | None = None
    clubs: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def build(
        cls,
        key: str,
        name: str,
        first_name: str | None = None,
        last_name: str | None = None,
        date_of_birth: date | None = None,
        clubs: Iterable[str] = (),
    ) -> MatchSubject:
        names = [name]
        if first_name and last_name:
            names.append(f"{first_name} {last_name}")
            names.append(f"{first_name.strip()[:1]}. {last_name}")
        return cls(
            key,
            tuple(dict.fromkeys(n for n in names if n)),
            date_of_birth,
            frozenset(normalize_name(c) for c in clubs if c),
        )


def name_score(a: Sequence[str], b: Sequence[str]) -> float:
    best = 0.0
    for x in a:
        tx = core_tokens(x)
        for y in b:
            ty = core_tokens(y)
            if not tx or not ty:
                continue
            sx, sy = " ".join(tx), " ".join(ty)
            score = fuzz.token_set_ratio(sx, sy) / 100
            # Initials: "m akanji" vs "manuel akanji" -> compare initial + last token.
            if len(tx[0]) == 1 or len(ty[0]) == 1:
                ix = f"{tx[0][0]} {tx[-1]}"
                iy = f"{ty[0][0]} {ty[-1]}"
                score = max(score, fuzz.ratio(ix, iy) / 100 * 0.97)
            # Guard: token_set_ratio gives 100 when one name is a subset ("Gabriel" in
            # "Gabriel Jesus"). Require the last tokens to agree for a full score.
            if len(tx) > 1 and len(ty) > 1 and fuzz.ratio(tx[-1], ty[-1]) < 80:
                score = min(score, 0.75)
            best = max(best, score)
    return best


def dob_score(a: date | None, b: date | None) -> float | None:
    """1.0 same day, 0.9 day/month swapped, 0.0 different, None if unknown."""
    if a is None or b is None:
        return None
    if a == b:
        return 1.0
    if a.year == b.year and a.month == b.day and a.day == b.month:
        return 0.9
    return 0.0


def club_score(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    return max(fuzz.token_set_ratio(x, y) / 100 for x in a for y in b)


def score_pair(a: MatchSubject, b: MatchSubject) -> tuple[float, str]:
    n = name_score(a.names, b.names)
    d = dob_score(a.date_of_birth, b.date_of_birth)
    c = club_score(a.clubs, b.clubs)
    club_bonus = 0.05 if c >= 0.85 else 0.0
    if d == 0.0:
        return 0.0, "dob mismatch"
    if d is None:
        # Without DOB we can't separate namesakes: cap below AUTO so a human decides.
        score = min(0.8 * n + club_bonus * 2, AUTO - 0.01)
        return round(score, 4), f"name={n:.2f} dob=? club={c:.2f}"
    score = min(1.0, 0.6 * n + 0.4 * d + club_bonus)
    return round(score, 4), f"name={n:.2f} dob={d:.1f} club={c:.2f}"


@dataclass(frozen=True)
class MatchResult:
    decision: Decision
    candidate: str | None
    score: float
    reason: str


def match_subject(subject: MatchSubject, candidates: Iterable[MatchSubject]) -> MatchResult:
    scored = sorted(
        ((score_pair(subject, c), c.key) for c in candidates), key=lambda t: t[0][0], reverse=True
    )
    if not scored or scored[0][0][0] < REVIEW:
        best = scored[0] if scored else ((0.0, "no candidates"), None)
        return MatchResult("new", best[1], best[0][0], best[0][1])
    (top_score, reason), top_key = scored[0]
    if len(scored) > 1 and top_score - scored[1][0][0] < AMBIGUITY_MARGIN:
        return MatchResult("review", top_key, top_score, f"ambiguous with {scored[1][1]}; {reason}")
    if top_score >= AUTO:
        return MatchResult("auto", top_key, top_score, reason)
    return MatchResult("review", top_key, top_score, reason)


# ---------------------------------------------------------------- manual overrides


@dataclass(frozen=True)
class ManualMatch:
    source: str
    source_player_id: str
    match_source: str | None  # None = force a new canonical player
    match_source_player_id: str | None


def load_manual_matches(path: Path) -> list[ManualMatch]:
    """CSV: source,source_player_id,match_source,match_source_player_id,note

    Overrides point at another source's ID (stable across DB rebuilds), never at an
    internal player_id. Leave match_* empty to force "this is a different player".
    """
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [
            ManualMatch(
                row["source"].strip(),
                row["source_player_id"].strip(),
                (row.get("match_source") or "").strip() or None,
                (row.get("match_source_player_id") or "").strip() or None,
            )
            for row in csv.DictReader(fh)
            if row.get("source") and not row["source"].startswith("#")
        ]
