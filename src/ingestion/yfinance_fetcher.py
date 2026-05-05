import yfinance as yf
import pandas as pd
import argparse
import os
import logging
import json

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Used if no tickers are provided via CLI
ticks = ["AAPL", "MSFT", "GOOGL"]

def fetch_data(tickers, start_date, end_date, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    for ticker in tickers:
        logging.info(f"Fetching data for {ticker} from {start_date} to {end_date}")
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if data.empty:
                logging.warning(f"No data found for {ticker} in the specified date range.")
                continue
                
            data = data.reset_index()
            # Flatten multi-index columns if they exist
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = [col[0] for col in data.columns]
                
            time_col = 'Date' if 'Date' in data.columns else 'Datetime'
            
            records = []
            for _, row in data.iterrows():
                record = {
                    "ticker": ticker,
                    "timestamp": row[time_col].strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "open": float(row.get("Open", 0)),
                    "high": float(row.get("High", 0)),
                    "low": float(row.get("Low", 0)),
                    "close": float(row.get("Close", 0)),
                    "volume": int(row.get("Volume", 0))
                }
                records.append(record)
                
            output_file = os.path.join(output_dir, f"{ticker}_{start_date}_{end_date}.json")
            with open(output_file, 'w') as f:
                json.dump(records, f, indent=2)
                
            logging.info(f"Successfully saved {ticker} data to {output_file}")
        except Exception as e:
            logging.error(f"Failed to fetch data for {ticker}: {e}")
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch OHLCV data from yfinance.")
    parser.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    parser.add_argument("--output", required=True, help="Output directory")
    
    args = parser.parse_args()
    fetch_data(ticks, args.start, args.end, args.output)
