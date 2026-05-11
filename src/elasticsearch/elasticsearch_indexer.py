"""
elasticsearch_indexer.py
Owner: Venera Vangjeli (150240933)

Reads enriched stock data from PostgreSQL and indexes it into
Elasticsearch with custom mappings optimised for:
  - time-range queries  (trade_date as a date field)
  - keyword queries     (ticker, signal as keyword fields)

Usage (standalone):
    python elasticsearch_indexer.py

Environment variables:
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
    ELASTICSEARCH_HOST  (default: http://elasticsearch:9200)
    ES_INDEX            (default: stock_market)
"""

import os
import time
import logging
import psycopg2
from elasticsearch import Elasticsearch, helpers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# ── configuration ──────────────────────────────────────────────────────────────
PG_HOST = os.environ.get("POSTGRES_HOST", "postgres")
PG_PORT = os.environ.get("POSTGRES_PORT", "5432")
PG_USER = os.environ.get("POSTGRES_USER", "airflow")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "airflow")
PG_DB   = os.environ.get("POSTGRES_DB", "airflow")

ES_HOST  = os.environ.get("ELASTICSEARCH_HOST", "http://elasticsearch:9200")
ES_INDEX = os.environ.get("ES_INDEX", "stock_market")

# ── Elasticsearch index mapping ─────────────────────────────────────────────
INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
    "mappings": {
        "properties": {
            "ticker":             {"type": "keyword"},
            "trade_date":         {"type": "date", "format": "yyyy-MM-dd"},
            "open":               {"type": "float"},
            "high":               {"type": "float"},
            "low":                {"type": "float"},
            "close":              {"type": "float"},
            "volume":             {"type": "long"},
            "sma_7":              {"type": "float"},
            "sma_10":             {"type": "float"},
            "sma_30":             {"type": "float"},
            "daily_spread":       {"type": "float"},
            "percentage_change":  {"type": "float"},
            "signal":             {"type": "keyword"},
        }
    },
}


def wait_for_elasticsearch(es: Elasticsearch, retries: int = 30, delay: int = 5) -> None:
    for attempt in range(1, retries + 1):
        try:
            if es.ping():
                logging.info("Elasticsearch is reachable.")
                return
        except Exception:
            pass
        logging.warning(f"Elasticsearch not ready — attempt {attempt}/{retries}. Retrying in {delay}s …")
        time.sleep(delay)
    raise RuntimeError("Elasticsearch did not become available in time.")


def create_index(es: Elasticsearch) -> None:
    if es.indices.exists(index=ES_INDEX):
        logging.info(f"Index '{ES_INDEX}' already exists — skipping creation.")
        return
    es.indices.create(index=ES_INDEX, body=INDEX_MAPPING)
    logging.info(f"Index '{ES_INDEX}' created with custom mappings.")


def fetch_enriched_records(pg_conn) -> list[dict]:
    """Query the stock_data from PostgreSQL."""
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                ticker,
                to_char(timestamp, 'YYYY-MM-DD') AS trade_date,
                open, high, low, close, volume,
                sma_7, sma_10, sma_30,
                daily_spread, percentage_change, signal
            FROM stock_data
            """
        )
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    records = []
    import math

    for row in rows:
        doc = dict(zip(columns, row))
        # Cast numerics so ES gets proper floats, not Decimal objects
        for field in ("open", "high", "low", "close", "sma_7", "sma_10", "sma_30",
                      "daily_spread", "percentage_change"):
            if doc[field] is not None:
                val = float(doc[field])
                if math.isnan(val):
                    doc[field] = None
                else:
                    doc[field] = val
        records.append(doc)

    logging.info(f"Fetched {len(records)} enriched records from PostgreSQL.")
    return records


def build_actions(records: list[dict]):
    for rec in records:
        doc_id = f"{rec['ticker']}_{rec['trade_date']}"
        yield {
            "_index": ES_INDEX,
            "_id":    doc_id,
            "_source": rec,
        }


def index_records(es: Elasticsearch, records: list[dict]) -> None:
    success, errors = helpers.bulk(es, build_actions(records), raise_on_error=False)
    logging.info(f"Indexed {success} documents successfully.")
    if errors:
        logging.warning(f"{len(errors)} documents had errors:")
        for err in errors[:5]:
            logging.warning(err)


def main() -> None:
    # Connect to Elasticsearch
    es = Elasticsearch(ES_HOST)
    wait_for_elasticsearch(es)
    create_index(es)

    while True:
        # Connect to PostgreSQL (with retry — postgres may still be initialising)
        pg_conn = None
        try:
            pg_conn = psycopg2.connect(
                host=PG_HOST, port=PG_PORT,
                user=PG_USER, password=PG_PASS,
                dbname=PG_DB,
            )
            logging.info("Connected to PostgreSQL for sync.")
            
            records = fetch_enriched_records(pg_conn)
            pg_conn.close()

            if records:
                index_records(es, records)
                logging.info(f"Successfully synced {len(records)} records to Elasticsearch.")
            else:
                logging.info("No new records found in PostgreSQL.")

        except Exception as exc:
            logging.error(f"Error during sync: {exc}")
            if pg_conn:
                pg_conn.close()
        
        logging.info("Sleeping for 60 seconds before next sync...")
        time.sleep(60)


if __name__ == "__main__":
    main()
