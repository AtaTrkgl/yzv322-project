import pandas as pd
import argparse
import os
import logging
import json
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import pandas as pd
import argparse
import os
import logging
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def transform_data(data_dir, target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    logging.info(f"Starting transformation for date: {target_date_str}")

    # 1. Gather files needed for SMA-30 (last 45 days to cover weekends/holidays)
    lookback_days = 45
    start_lookback = target_date - timedelta(days=lookback_days)
    
    all_records = []
    
    # We look for all files in the directory and filter by date range
    for filename in os.listdir(data_dir):
        if not filename.endswith(".json"):
            continue
        
        # filename: AAPL_2026-02-05_2026-02-06.json
        # Split off the ticker prefix first, then extract dates
        name = filename.replace(".json", "")
        # Find the two dates by regex instead of naive split
        import re
        date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', name)
        if len(date_matches) < 1:
            continue
        
        try:
            file_date = datetime.strptime(date_matches[0], "%Y-%m-%d")
        except ValueError:
            continue

        if start_lookback <= file_date <= target_date:
            filepath = os.path.join(data_dir, filename)
            if os.path.getsize(filepath) == 0: continue
            
            try:
                with open(filepath, 'r') as f:
                    records = json.load(f)
                    if records:
                        all_records.extend(records)
            except json.JSONDecodeError:
                logging.error(f"Failed to decode {filename}")

    if not all_records:
        logging.warning(f"No records found for {target_date_str} or lookback period.")
        return

    # 2. Process data
    df = pd.DataFrame(all_records)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by=['ticker', 'timestamp']).drop_duplicates(subset=['ticker', 'timestamp'])
    
    # Group by ticker
    grouped = df.groupby('ticker')
    
    df['sma_7'] = grouped['close'].transform(lambda x: x.rolling(window=7, min_periods=1).mean())
    df['sma_10'] = grouped['close'].transform(lambda x: x.rolling(window=10, min_periods=1).mean())
    df['sma_30'] = grouped['close'].transform(lambda x: x.rolling(window=30, min_periods=1).mean())
    
    df['daily_spread'] = df['high'] - df['low']
    df['percentage_change'] = grouped['close'].transform(lambda x: x.pct_change() * 100)
    
    df['signal'] = 'NEUTRAL'
    df.loc[(df['close'] > df['open']) & (df['close'] > df['sma_7']), 'signal'] = 'BULLISH'
    df.loc[(df['close'] < df['open']) & (df['close'] < df['sma_7']), 'signal'] = 'BEARISH'
    
    for col in ['sma_7', 'sma_10', 'sma_30', 'daily_spread', 'percentage_change']:
        df[col] = df[col].round(4)

    # df = df.replace({pd.NA: None, float('nan'): None})
    df = df.where(df.notna(), other=None)

    # 3. Save ONLY the target date's data back to its specific files
    # Filter for the target date matching the YYYY-MM-DD string to avoid timezone naive/aware comparison issues
    target_df = df[df['timestamp'].dt.strftime('%Y-%m-%d') == target_date_str].copy()
    
    if target_df.empty:
        logging.warning(f"No data points found exactly on {target_date_str} after calculations.")
        return

    # Identify the files that should contain this target date data
    for ticker in target_df['ticker'].unique():
        ticker_df = target_df[target_df['ticker'] == ticker].copy()
        
        # Format timestamp for JSON
        ticker_df['timestamp'] = ticker_df['timestamp'].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        updated_records = ticker_df.to_dict('records')
        
        # The filename expected by fetcher: {ticker}_{start}_{end}.json
        # In Airflow, ds is 'start' and next_ds is 'end'
        # We need to find the specific file for this ticker and date
        for filename in os.listdir(data_dir):
            date_matches = re.findall(r'\d{4}-\d{2}-\d{2}', filename)
            if date_matches and date_matches[0] == target_date_str and filename.startswith(f"{ticker}_"):
                filepath = os.path.join(data_dir, filename)
                with open(filepath, 'w') as f:
                    json.dump(updated_records, f, indent=2)
                
                # Log the calculated stats to verify
                sample = updated_records[0] if updated_records else {}
                logging.info(f"Updated {filename} with stats -> SMA-7: {sample.get('sma_7')}, SMA-30: {sample.get('sma_30')}, Signal: {sample.get('signal')}")
                logging.info(f"Files in {data_dir}: {os.listdir(data_dir)}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--date", required=False, help="Target date (YYYY-MM-DD) to process")
    args = parser.parse_args()
    
    transform_data(args.data_dir, args.date)