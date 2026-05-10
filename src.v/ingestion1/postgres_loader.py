"""
postgres_loader.py
Owner: Venera Vangjeli (150240933)

Loads transformed JSON records into the normalized PostgreSQL schema:
  tickers  ->  daily_ohlcv  ->  derived_indicators
"""

import os
import json
import psycopg2
import logging
import argparse
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_connection(host, port, user, password, db_name):
    return psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=db_name
    )


def upsert_ticker(cur, symbol: str) -> int:
    """Insert ticker if not exists and return its id."""
    cur.execute(
        """
        INSERT INTO tickers (symbol)
        VALUES (%s)
        ON CONFLICT (symbol) DO UPDATE SET symbol = EXCLUDED.symbol
        RETURNING id
        """,
        (symbol,),
    )
    return cur.fetchone()[0]


def upsert_ohlcv(cur, ticker_id: int, record: dict) -> int:
    """Insert OHLCV row if not exists and return its id."""
    # Timestamp may be ISO string like "2024-01-02T00:00:00Z" or just a date
    raw_ts = record.get("timestamp", "")
    try:
        trade_date = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).date()
    except Exception:
        trade_date = raw_ts[:10]  # fall back to first 10 chars (YYYY-MM-DD)

    cur.execute(
        """
        INSERT INTO daily_ohlcv (ticker_id, trade_date, open, high, low, close, volume)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ticker_id, trade_date) DO UPDATE
            SET open   = EXCLUDED.open,
                high   = EXCLUDED.high,
                low    = EXCLUDED.low,
                close  = EXCLUDED.close,
                volume = EXCLUDED.volume
        RETURNING id
        """,
        (
            ticker_id,
            trade_date,
            record.get("open"),
            record.get("high"),
            record.get("low"),
            record.get("close"),
            record.get("volume", 0),
        ),
    )
    return cur.fetchone()[0]


def upsert_indicators(cur, ohlcv_id: int, record: dict) -> None:
    """Insert or update derived indicators for a given OHLCV row."""
    cur.execute(
        """
        INSERT INTO derived_indicators
            (ohlcv_id, sma_7, sma_10, sma_30, daily_spread, percentage_change, signal)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (ohlcv_id) DO UPDATE
            SET sma_7             = EXCLUDED.sma_7,
                sma_10            = EXCLUDED.sma_10,
                sma_30            = EXCLUDED.sma_30,
                daily_spread      = EXCLUDED.daily_spread,
                percentage_change = EXCLUDED.percentage_change,
                signal            = EXCLUDED.signal
        """,
        (
            ohlcv_id,
            record.get("sma_7"),
            record.get("sma_10"),
            record.get("sma_30"),
            record.get("daily_spread"),
            record.get("percentage_change"),
            record.get("signal"),
        ),
    )


def load_data(data_dir: str, host: str, port: str, user: str, password: str, db_name: str, target_date: str = None):
    conn = get_connection(host, port, user, password, db_name)
    cur = conn.cursor()

    loaded = 0
    for filename in sorted(os.listdir(data_dir)):
        if not filename.endswith(".json"):
            continue

        # Optionally filter to only today's files (Airflow idempotency)
        if target_date:
            import re
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", filename)
            if not dates or dates[0] != target_date:
                logging.info(f"Skipping {filename} (not target date {target_date})")
                continue

        filepath = os.path.join(data_dir, filename)
        if os.path.getsize(filepath) == 0:
            continue

        logging.info(f"Loading {filepath}")
        with open(filepath, "r") as f:
            try:
                records = json.load(f)
            except json.JSONDecodeError:
                logging.error(f"Failed to decode {filepath}")
                continue

        for record in records:
            symbol = record.get("ticker", "").upper()
            if not symbol:
                continue
            ticker_id = upsert_ticker(cur, symbol)
            ohlcv_id = upsert_ohlcv(cur, ticker_id, record)
            upsert_indicators(cur, ohlcv_id, record)
            loaded += 1

        conn.commit()
        logging.info(f"Committed {filename}")

    cur.close()
    conn.close()
    logging.info(f"Done — {loaded} records loaded into normalized schema.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load transformed OHLCV JSON into PostgreSQL normalized schema.")
    parser.add_argument("--data-dir", required=True, help="Directory with transformed JSON files")
    parser.add_argument("--date", required=False, help="Filter to specific YYYY-MM-DD date (optional)")
    args = parser.parse_args()

    load_data(
        data_dir=args.data_dir,
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=os.environ.get("POSTGRES_PORT", "5432"),
        user=os.environ.get("POSTGRES_USER", "airflow"),
        password=os.environ.get("POSTGRES_PASSWORD", "airflow"),
        db_name=os.environ.get("POSTGRES_DB", "finance"),
        target_date=args.date,
    )
