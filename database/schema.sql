-- Reference DDL, kept in sync with database/models.py by hand.
-- This is documentation, not the source of truth: SQLAlchemy's
-- Base.metadata.create_all() (see database/init_db.py) is what actually
-- creates the tables, from the same portable types used here so this
-- runs unchanged on SQLite or PostgreSQL.

CREATE TABLE users (
    id              INTEGER PRIMARY KEY,
    username        VARCHAR(64) UNIQUE NOT NULL,
    password_hash   VARCHAR(256) NOT NULL,
    full_name       VARCHAR(128) NOT NULL,
    email           VARCHAR(128),
    role            VARCHAR(16) NOT NULL,     -- admin | operator | citizen
    created_at      TIMESTAMP NOT NULL
);

CREATE TABLE waste_categories (
    id              INTEGER PRIMARY KEY,
    key             VARCHAR(32) UNIQUE NOT NULL,   -- plastic, paper, cardboard, glass, metal, organic, other
    label           VARCHAR(64) NOT NULL,
    bin_stream      VARCHAR(128) NOT NULL,
    bin_color       VARCHAR(32) NOT NULL,
    recyclable      BOOLEAN NOT NULL,
    description     VARCHAR(256)
);

CREATE TABLE locations (
    id              INTEGER PRIMARY KEY,
    name            VARCHAR(128) NOT NULL,
    address         VARCHAR(256),
    latitude        FLOAT NOT NULL,
    longitude       FLOAT NOT NULL,
    location_type   VARCHAR(32) NOT NULL,      -- hospital | market | school | residential | commercial | park
    zone            VARCHAR(64)
);

CREATE TABLE bins (
    id                      INTEGER PRIMARY KEY,
    bin_code                VARCHAR(32) UNIQUE NOT NULL,
    location_id             INTEGER NOT NULL REFERENCES locations(id),
    waste_category_id       INTEGER NOT NULL REFERENCES waste_categories(id),
    capacity_liters         FLOAT NOT NULL DEFAULT 240.0,
    current_fill_level      FLOAT NOT NULL DEFAULT 0.0,   -- 0-100
    status                  VARCHAR(16) NOT NULL DEFAULT 'normal',
    installed_at            TIMESTAMP NOT NULL,
    last_collection_time    TIMESTAMP
);

CREATE TABLE bin_sensor_readings (
    id              INTEGER PRIMARY KEY,
    bin_id          INTEGER NOT NULL REFERENCES bins(id),
    timestamp       TIMESTAMP NOT NULL,
    fill_level      FLOAT NOT NULL,             -- 0-100
    is_simulated    BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE waste_detections (
    id                              INTEGER PRIMARY KEY,
    user_id                         INTEGER REFERENCES users(id),
    waste_category_id               INTEGER REFERENCES waste_categories(id),
    detected_at                     TIMESTAMP NOT NULL,
    image_path                      VARCHAR(512),
    confidence                      FLOAT NOT NULL,
    bbox_x FLOAT, bbox_y FLOAT, bbox_w FLOAT, bbox_h FLOAT,   -- normalized 0-1
    raw_label                       VARCHAR(64),
    manual_verification_required    BOOLEAN NOT NULL DEFAULT FALSE,
    source                          VARCHAR(16) NOT NULL DEFAULT 'upload'
);

CREATE TABLE routes (
    id                          INTEGER PRIMARY KEY,
    vehicle_label               VARCHAR(32) NOT NULL,
    planned_date                TIMESTAMP NOT NULL,
    bin_sequence                JSON NOT NULL,   -- ordered list of bin ids
    total_distance_km           FLOAT NOT NULL,
    total_duration_minutes      FLOAT NOT NULL,
    is_optimized                BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE collection_records (
    id                          INTEGER PRIMARY KEY,
    bin_id                      INTEGER NOT NULL REFERENCES bins(id),
    route_id                    INTEGER REFERENCES routes(id),
    operator_id                 INTEGER REFERENCES users(id),
    scheduled_time               TIMESTAMP,
    collected_time               TIMESTAMP,
    status                       VARCHAR(16) NOT NULL DEFAULT 'scheduled',  -- scheduled|completed|missed
    fill_level_at_collection      FLOAT
);

CREATE TABLE prediction_results (
    id                          INTEGER PRIMARY KEY,
    bin_id                      INTEGER NOT NULL REFERENCES bins(id),
    predicted_at                TIMESTAMP NOT NULL,
    predicted_fill_level_24h    FLOAT NOT NULL,
    predicted_hours_to_full     FLOAT,
    overflow_probability        FLOAT NOT NULL,   -- 0-1
    collection_required         BOOLEAN NOT NULL,
    priority_score               FLOAT NOT NULL,   -- 0-100
    priority_band                VARCHAR(16) NOT NULL,  -- low|medium|high|critical
    model_version                 VARCHAR(32) NOT NULL
);
