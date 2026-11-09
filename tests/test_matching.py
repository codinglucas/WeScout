from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

import pytest

from wescout.db import repository as repo
from wescout.matching import (
    AUTO,
    MatchSubject,
    dob_score,
    match_subject,
    name_score,
    normalize_name,
    score_pair,
)
from wescout.models import ClubRef, CompetitionRef, PlayerRecord, SeasonStatsRecord
from wescout.resolve import resolve_players

T0 = datetime(2026, 11, 9)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Benjamin Šeško", "benjamin sesko"),
        ("Martin Ødegaard", "martin odegaard"),
        ("İlkay Gündoğan", "ilkay gundogan"),
        ("Heung-Min Son", "heung min son"),
        ("N'Golo Kanté", "ngolo kante"),
        ("Александр Головин", "aleksandr golovin"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_initials_match_full_name() -> None:
    a = MatchSubject.build("a", "M. Akanji", "Manuel Obafemi", "Akanji")
    assert name_score(a.names, ("Manuel Akanji",)) >= 0.95


def test_shared_first_name_is_not_a_name_match() -> None:
    assert name_score(("Gabriel Jesus",), ("Gabriel Martinelli",)) <= 0.75


def test_dob_scores() -> None:
    d = date(2003, 5, 3)
    assert dob_score(d, d) == 1.0
    assert dob_score(d, date(2003, 3, 5)) == 0.9
    assert dob_score(d, date(2003, 5, 4)) == 0.0
    assert dob_score(d, None) is None


def test_same_name_different_dob_is_rejected() -> None:
    a = MatchSubject.build("a", "Danilo", date_of_birth=date(1991, 7, 15))
    b = MatchSubject.build("b", "Danilo", date_of_birth=date(2001, 4, 29))
    assert score_pair(a, b)[0] == 0.0


def test_missing_dob_never_auto_matches() -> None:
    a = MatchSubject.build("a", "Alexander Isak", date_of_birth=date(1999, 9, 21), clubs=["X"])
    b = MatchSubject.build("b", "Alexander Isak", clubs=["X"])
    assert score_pair(a, b)[0] < AUTO


def test_ambiguous_candidates_go_to_review() -> None:
    subject = MatchSubject.build("s", "Danilo", date_of_birth=date(1991, 7, 15))
    twins = [
        MatchSubject.build("1", "Danilo", date_of_birth=date(1991, 7, 15)),
        MatchSubject.build("2", "Danilo", date_of_birth=date(1991, 7, 15)),
    ]
    result = match_subject(subject, twins)
    assert result.decision == "review"
    assert "ambiguous" in result.reason


def test_eval_script_on_starter_labels() -> None:
    import importlib.util

    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location("ev", root / "scripts" / "eval_matching.py")
    assert spec and spec.loader
    ev = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ev)
    result = ev.evaluate(ev.load(root / "eval" / "match_labels.csv"))
    assert result["fp"] == 0  # a wrong automatic link is the expensive error


# ---------------------------------------------------------------- resolver against the DB


def _add(db: Any, source: str, spid: str, name: str, dob: date | None, club: str) -> None:
    repo.register_source(
        db, source, "local_scrape", None, None
    ) if source != "api_football" else None
    repo.upsert_source_players(db, [PlayerRecord(source, spid, name, date_of_birth=dob)], T0)
    repo.upsert_season_stats(
        db,
        [SeasonStatsRecord(source, spid, CompetitionRef("39", "PL"), ClubRef(club, club), 2023)],
        T0,
    )


def _player_of(db: Any, source: str, spid: str) -> Any:
    return db.execute(
        "SELECT player_id, matched_by FROM source_players WHERE source=? AND source_player_id=?",
        [source, spid],
    ).fetchone()


def test_resolver_auto_review_new_and_manual(db: Any, tmp_path: Path) -> None:
    _add(db, "api_football", "1", "Danilo", date(1991, 7, 15), "Juventus")
    _add(db, "api_football", "2", "Danilo", date(2001, 4, 29), "Nottingham Forest")
    _add(db, "api_football", "3", "A. Isak", date(1999, 9, 21), "Newcastle")
    _add(db, "sofascore", "s1", "Danilo", date(1991, 7, 15), "Juventus")  # auto -> 1
    _add(db, "sofascore", "s2", "Alexander Isak", None, "Newcastle")  # no DOB -> review
    _add(db, "sofascore", "s3", "Unknown Youngster", date(2007, 1, 1), "Juventus")  # new

    stats = resolve_players(db)
    assert (stats.anchored, stats.auto, stats.review, stats.new) == (3, 1, 1, 1)
    assert _player_of(db, "sofascore", "s1") == (_player_of(db, "api_football", "1")[0], "auto")
    assert _player_of(db, "sofascore", "s2")[0] is None
    assert db.execute("SELECT count(*) FROM match_reviews").fetchone()[0] == 1

    manual = tmp_path / "manual_matches.csv"
    manual.write_text(
        "source,source_player_id,match_source,match_source_player_id,note\n"
        "sofascore,s2,api_football,3,checked by hand\n",
        encoding="utf-8",
    )
    stats = resolve_players(db, manual)
    assert stats.manual == 1
    assert _player_of(db, "sofascore", "s2") == (_player_of(db, "api_football", "3")[0], "manual")
    assert db.execute("SELECT count(*) FROM match_reviews").fetchone()[0] == 0

    # Idempotent: nothing left to do on a second run.
    again = resolve_players(db)
    assert (again.anchored, again.auto, again.review, again.new) == (0, 0, 0, 0)
