-- Schema for the Starling ops volume forecaster
-- SQLite-compatible DDL based on the processed data from data/processed/combined_demand_signals.csv
-- Nithin Arisetty, 2024

-- Drop and recreate so the notebook can re-run from scratch cleanly
DROP TABLE IF EXISTS complaints;
DROP TABLE IF EXISTS search_trends;
DROP TABLE IF EXISTS macro_indicators;
DROP TABLE IF EXISTS demand_signals;

CREATE TABLE complaints (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        DATE        NOT NULL,   -- first of month, half-year data distributed monthly
    firm_type   TEXT        NOT NULL,   -- 'neobank' | 'high_street'
    firm_name   TEXT,
    category    TEXT,                   -- 'Banking', 'Cards & payments', etc.
    complaints_received INTEGER NOT NULL,
    complaints_closed   INTEGER,
    pct_closed_3d       REAL,           -- % closed within 3 days
    pct_upheld          REAL
);

CREATE TABLE search_trends (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    date                DATE    NOT NULL,
    trends_starling     REAL,   -- Google Trends index 0-100 for "Starling Bank" (UK)
    trends_neobank_help REAL    -- Google Trends index 0-100 for "neobank help" (UK)
);

CREATE TABLE macro_indicators (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date                 DATE    NOT NULL,
    unemployment_rate    REAL,   -- ONS LF24, UK unemployment rate %
    consumer_confidence  REAL    -- GfK consumer confidence index (negative = pessimistic)
);

-- Denormalised combined table — this is what most queries will hit
-- Mirrors combined_demand_signals.csv exactly so SQL and notebook results are consistent
CREATE TABLE demand_signals (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    date                 DATE    NOT NULL,
    fca_complaints       REAL,
    trends_starling      REAL,
    trends_neobank_help  REAL,
    unemployment_rate    REAL,
    consumer_confidence  REAL,
    demand_index         REAL    -- weighted composite: 0.65 * complaints_norm + 0.35 * trends_norm
);

CREATE INDEX idx_demand_signals_date ON demand_signals (date);
CREATE INDEX idx_complaints_date     ON complaints (date);
