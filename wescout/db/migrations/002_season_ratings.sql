-- 002_season_ratings: one rating per player-season from rating-only sources
-- (e.g. a hand-filled CSV). Kept apart from player_season_stats on purpose:
-- these rows cover all competitions, so mixing them into league stats would
-- double count minutes and break the search's per-league numbers.

CREATE TABLE player_season_ratings (
    source             VARCHAR NOT NULL,
    source_player_id   VARCHAR NOT NULL,
    season_start_year  INTEGER NOT NULL,   -- 2023 = 2023/24
    club_name          VARCHAR NOT NULL DEFAULT '',
    rating             DOUBLE  NOT NULL,
    minutes            INTEGER,
    scope              VARCHAR NOT NULL DEFAULT 'all_competitions',
    fetched_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (source, source_player_id, season_start_year, club_name)
);
