-- 001_init: core schema for Phase 1.
--
-- Design rules (see docs/decisions.md, ADR-003/004):
--   * Every fact row is keyed by (source, source_player_id, ...) - the provider's own IDs.
--     Canonical identity lives in source_players.player_id, so re-matching a player only
--     updates one column; no fact rows have to be re-keyed.
--   * Every fact row carries `source` and `fetched_at`. Licensing is looked up in `sources`,
--     so PUBLIC_MODE is a single join (license <> 'local_scrape').
--   * No FOREIGN KEY constraints: DuckDB cannot upsert a row that an FK references.
--     Referential integrity is checked by wescout.db.integrity after each ETL load.
--   * Dates that matter for point-in-time features (valued_at, transfer_date, observed_at,
--     season start/end) are stored separately from fetched_at.

CREATE TABLE sources (
    source       VARCHAR PRIMARY KEY,
    license      VARCHAR NOT NULL CHECK (license IN ('licensed', 'local_scrape')),
    attribution  VARCHAR,
    url          VARCHAR
);

-- Local-only providers (git-ignored local_providers/) register their own rows at load time.
INSERT INTO sources VALUES
    ('api_football', 'licensed', 'Data provided by API-Football (api-sports.io)', 'https://www.api-football.com'),
    ('statsbomb',    'licensed', 'Data provided by StatsBomb open data',          'https://github.com/statsbomb/open-data'),
    ('manual',       'licensed', NULL,                                            NULL);

-- Canonical identity. Attributes live on source_players and are resolved per query,
-- so a public response can never pick up a field that only a scraper provided.
CREATE SEQUENCE player_id_seq START 1;
CREATE TABLE players (
    player_id   BIGINT PRIMARY KEY DEFAULT nextval('player_id_seq'),
    created_at  TIMESTAMP NOT NULL DEFAULT current_timestamp
);

CREATE SEQUENCE competition_id_seq START 1;
CREATE TABLE competitions (
    competition_id  BIGINT PRIMARY KEY DEFAULT nextval('competition_id_seq'),
    name            VARCHAR NOT NULL,
    country         VARCHAR,
    kind            VARCHAR,            -- 'league' | 'cup'
    source          VARCHAR NOT NULL,  -- source that created the row
    fetched_at      TIMESTAMP NOT NULL
);

CREATE SEQUENCE club_id_seq START 1;
CREATE TABLE clubs (
    club_id     BIGINT PRIMARY KEY DEFAULT nextval('club_id_seq'),
    name        VARCHAR NOT NULL,
    country     VARCHAR,
    source      VARCHAR NOT NULL,
    fetched_at  TIMESTAMP NOT NULL
);

-- Provider IDs for clubs and competitions.
CREATE TABLE external_ids (
    entity_type  VARCHAR NOT NULL CHECK (entity_type IN ('club', 'competition')),
    source       VARCHAR NOT NULL,
    source_id    VARCHAR NOT NULL,
    entity_id    BIGINT  NOT NULL,
    fetched_at   TIMESTAMP NOT NULL,
    PRIMARY KEY (entity_type, source, source_id)
);

CREATE SEQUENCE season_id_seq START 1;
CREATE TABLE seasons (
    season_id       BIGINT PRIMARY KEY DEFAULT nextval('season_id_seq'),
    competition_id  BIGINT  NOT NULL,
    start_year      INTEGER NOT NULL,   -- 2023 = 2023/24 (or calendar 2023)
    label           VARCHAR NOT NULL,
    start_date      DATE,
    end_date        DATE,
    is_complete     BOOLEAN NOT NULL DEFAULT false,
    UNIQUE (competition_id, start_year)
);

-- One row per player per source. player_id is NULL until matched.
CREATE TABLE source_players (
    source             VARCHAR NOT NULL,
    source_player_id   VARCHAR NOT NULL,
    player_id          BIGINT,
    name               VARCHAR NOT NULL,
    first_name         VARCHAR,
    last_name          VARCHAR,
    date_of_birth      DATE,
    nationality        VARCHAR,
    height_cm          SMALLINT,
    weight_kg          SMALLINT,
    foot               VARCHAR,
    position           VARCHAR,   -- coarse: GK | DF | MF | FW
    detailed_position  VARCHAR,   -- frontend codes: gk, cb, lb, ... (nullable)
    photo_url          VARCHAR,
    match_confidence   DOUBLE,
    matched_by         VARCHAR,   -- 'anchor' | 'auto' | 'manual'
    fetched_at         TIMESTAMP NOT NULL,
    PRIMARY KEY (source, source_player_id)
);

-- Raw counts only; per-90 and percentiles are Phase 2 (computed, not stored).
CREATE TABLE player_season_stats (
    source               VARCHAR NOT NULL,
    source_player_id     VARCHAR NOT NULL,
    season_id            BIGINT  NOT NULL,
    club_id              BIGINT  NOT NULL,
    position             VARCHAR,
    appearances          INTEGER,
    starts               INTEGER,
    minutes              INTEGER,
    rating               DOUBLE,
    goals                INTEGER,
    assists              INTEGER,
    key_passes           INTEGER,
    tackles              INTEGER,
    interceptions        INTEGER,
    dribbled_past        INTEGER,
    big_chances_created  INTEGER,
    accurate_passes      INTEGER,
    total_passes         INTEGER,
    extra                JSON,      -- provider-specific stats kept verbatim
    fetched_at           TIMESTAMP NOT NULL,
    PRIMARY KEY (source, source_player_id, season_id, club_id)
);

CREATE TABLE market_values (
    source            VARCHAR NOT NULL,
    source_player_id  VARCHAR NOT NULL,
    valued_at         DATE    NOT NULL,   -- valuation date (use this for features)
    value_eur         BIGINT  NOT NULL,
    club_id           BIGINT,
    fetched_at        TIMESTAMP NOT NULL, -- when we collected it
    PRIMARY KEY (source, source_player_id, valued_at)
);

CREATE TABLE transfers (
    source            VARCHAR NOT NULL,
    source_player_id  VARCHAR NOT NULL,
    transfer_key      VARCHAR NOT NULL,   -- deterministic: date|from|to, provider IDs
    transfer_date     DATE,
    from_club_id      BIGINT,
    to_club_id        BIGINT,
    fee_eur           BIGINT,
    fee_type          VARCHAR CHECK (fee_type IN ('fee', 'loan', 'loan_end', 'free', 'unknown')),
    fee_raw           VARCHAR,
    fetched_at        TIMESTAMP NOT NULL,
    PRIMARY KEY (source, source_player_id, transfer_key)
);

CREATE TABLE contracts (
    source            VARCHAR NOT NULL,
    source_player_id  VARCHAR NOT NULL,
    club_id           BIGINT  NOT NULL,
    expires           DATE,
    observed_at       DATE    NOT NULL,   -- contract info as known on this date
    fetched_at        TIMESTAMP NOT NULL,
    PRIMARY KEY (source, source_player_id, club_id, observed_at)
);

-- Low-confidence matches waiting for a human decision.
CREATE TABLE match_reviews (
    source               VARCHAR NOT NULL,
    source_player_id     VARCHAR NOT NULL,
    candidate_player_id  BIGINT,
    score                DOUBLE,
    reason               VARCHAR,
    created_at           TIMESTAMP NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (source, source_player_id)
);

-- ETL bookkeeping.
CREATE SEQUENCE etl_run_id_seq START 1;
CREATE TABLE etl_runs (
    run_id         BIGINT PRIMARY KEY DEFAULT nextval('etl_run_id_seq'),
    provider       VARCHAR NOT NULL,
    args           JSON,
    started_at     TIMESTAMP NOT NULL,
    finished_at    TIMESTAMP,
    status         VARCHAR NOT NULL,   -- running | ok | partial | failed
    records        INTEGER DEFAULT 0,
    requests_used  INTEGER DEFAULT 0,
    message        VARCHAR
);

-- One row per unit of work (e.g. one page of /players). Makes runs resumable.
CREATE TABLE etl_checkpoints (
    provider    VARCHAR NOT NULL,
    task_key    VARCHAR NOT NULL,
    status      VARCHAR NOT NULL,   -- done | failed
    records     INTEGER,
    updated_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (provider, task_key)
);

CREATE TABLE api_usage (
    provider       VARCHAR NOT NULL,
    usage_date     DATE    NOT NULL,   -- provider's day (UTC)
    requests_used  INTEGER NOT NULL,
    PRIMARY KEY (provider, usage_date)
);

-- Index of raw responses stored on disk under data/raw/ (re-parse without re-fetching).
CREATE TABLE raw_responses (
    request_key  VARCHAR PRIMARY KEY,  -- sha256 of source + endpoint + sorted params
    source       VARCHAR NOT NULL,
    endpoint     VARCHAR NOT NULL,
    params       JSON,
    path         VARCHAR NOT NULL,
    status_code  INTEGER NOT NULL,
    fetched_at   TIMESTAMP NOT NULL
);
