import os
import json
import psycopg2
import logging
import argparse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_data(data_dir, db_host, db_port, db_user, db_password, db_name, target_date=None):
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        dbname=db_name
    )
    cur = conn.cursor()
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stock_data (
            id SERIAL PRIMARY KEY,
            ticker VARCHAR(10),
            timestamp TIMESTAMP,
            open FLOAT,
            high FLOAT,
            low FLOAT,
            close FLOAT,
            volume BIGINT,
            sma_7 FLOAT,
            sma_10 FLOAT,
            sma_30 FLOAT,
            daily_spread FLOAT,
            percentage_change FLOAT,
            signal VARCHAR(10),
            UNIQUE(ticker, timestamp)
        );
    """)
    conn.commit()

    for filename in os.listdir(data_dir):
        if not filename.endswith(".json"):
            continue
        
        # Only load files whose start date matches the target date
        if target_date:
            parts = filename.replace(".json", "").split("_")
            if len(parts) < 3 or parts[1] != target_date:
                logging.info(f"Skipping {filename} (not target date {target_date})")
                continue

        filepath = os.path.join(data_dir, filename)
        logging.info(f"Loading {filepath} into database")
        with open(filepath, 'r') as f:
            records = json.load(f)
            for r in records:
                cur.execute("""
                    INSERT INTO stock_data (ticker, timestamp, open, high, low, close, volume, sma_7, sma_10, sma_30, daily_spread, percentage_change, signal)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (ticker, timestamp) DO NOTHING;
                """, (
                    r['ticker'], r.get('timestamp'), r.get('open'), r.get('high'), r.get('low'), r.get('close'), r.get('volume', 0),
                    r.get('sma_7'), r.get('sma_10'), r.get('sma_30'), r.get('daily_spread'), r.get('percentage_change'), r.get('signal')
                ))
    conn.commit()
    cur.close()
    conn.close()
    logging.info("Successfully loaded data into PostgreSQL")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--date", required=False, help="Ignored, but required to absorb the Airflow DAG parameter")
    args = parser.parse_args()
    
    host = os.environ.get("POSTGRES_HOST", "postgres")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "airflow")
    password = os.environ.get("POSTGRES_PASSWORD", "airflow")
    db = os.environ.get("POSTGRES_DB", "finance")
    
    load_data(args.data_dir, host, port, user, password, db, target_date=args.date)
