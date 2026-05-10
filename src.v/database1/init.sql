-- ============================================================
-- YZV322E Final Project — PostgreSQL Normalized Schema
-- Owner: Venera Vangjeli (150240933)
-- ============================================================

-- 1. Ticker metadata table
CREATE TABLE IF NOT EXISTS tickers (
    id        SERIAL PRIMARY KEY,
    symbol    VARCHAR(10)  UNIQUE NOT NULL,
    name      VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. Daily OHLCV observations
CREATE TABLE IF NOT EXISTS daily_ohlcv (
    id          SERIAL PRIMARY KEY,
    ticker_id   INTEGER NOT NULL REFERENCES tickers(id) ON DELETE CASCADE,
    trade_date  DATE    NOT NULL,
    open        NUMERIC(14, 4),
    high        NUMERIC(14, 4),
    low         NUMERIC(14, 4),
    close       NUMERIC(14, 4),
    volume      BIGINT,
    UNIQUE (ticker_id, trade_date)
);

-- 3. Derived indicators (one row per OHLCV row)
CREATE TABLE IF NOT EXISTS derived_indicators (
    id                SERIAL PRIMARY KEY,
    ohlcv_id          INTEGER NOT NULL REFERENCES daily_ohlcv(id) ON DELETE CASCADE,
    sma_7             NUMERIC(14, 4),
    sma_10            NUMERIC(14, 4),
    sma_30            NUMERIC(14, 4),
    daily_spread      NUMERIC(14, 4),
    percentage_change NUMERIC(10, 4),
    signal            VARCHAR(10),
    UNIQUE (ohlcv_id)
);

-- ============================================================
-- Indexes for fast queries (time-range and ticker filtering)
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_ohlcv_ticker_date  ON daily_ohlcv (ticker_id, trade_date);
CREATE INDEX IF NOT EXISTS idx_ohlcv_trade_date   ON daily_ohlcv (trade_date);
CREATE INDEX IF NOT EXISTS idx_indicators_signal  ON derived_indicators (signal);

-- ============================================================
-- Convenience view used by Elasticsearch indexer & pgAdmin
-- ============================================================
CREATE OR REPLACE VIEW enriched_stock_data AS
SELECT
    t.symbol                        AS ticker,
    o.trade_date,
    o.open, o.high, o.low, o.close,
    o.volume,
    d.sma_7, d.sma_10, d.sma_30,
    d.daily_spread,
    d.percentage_change,
    d.signal
FROM tickers            t
JOIN daily_ohlcv        o ON o.ticker_id = t.id
LEFT JOIN derived_indicators d ON d.ohlcv_id  = o.id
ORDER BY t.symbol, o.trade_date;
