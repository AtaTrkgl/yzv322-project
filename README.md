# YZV 322E Final Project: Financial Market Analytics Pipeline

## Project Summary

This project is an end-to-end, fully containerized data engineering pipeline designed to ingest and analyze real-time and historical stock market data. Utilizing the yfinance Python library, the system extracts OHLCV (open, high, low, close, volume) time-series data for a configurable set of stock tickers. The pipeline transforms this raw data into actionable financial indicators, including 7-day and 30-day Simple Moving Averages (SMA), intraday volatility spread, and rule-based Bullish/Bearish signal generation.

The processed data is persisted in a relational PostgreSQL database and simultaneously indexed in Elasticsearch. Kibana is used to surface these metrics through interactive dashboards featuring candlestick views, moving average overlays, and volume bar charts. The entire architecture is packaged as a single portable artifact requiring no host-machine installation.

## Team Members
[Ata Türkoğlu](https://www.github.com/AtaTrkgl) (150210337) - Data ingestion, orchestration (Apache Airflow), and ETL processing.  

Venera Vangjeli (150240933) - Relational storage (PostgreSQL/pgAdmin), search indexing (Elasticsearch), and visual analytics (Kibana).

## Architecture

The architecture is divided into two cohesive subsystems:

- **Ingestion & ETL:** A Dockerized Python service queries the yfinance API, orchestrated by Apache Airflow DAGs that manage scheduling, retries, and pipeline idempotency.
- **Storage & Analytics:** Enriched records are loaded into PostgreSQL using a normalized schema managed by SQL migrations, while processed documents are pushed to Elasticsearch for interactive querying via Kibana. All inter-service communication utilizes an internal Docker Compose network.

## Setup Instructions

1. Clone this repository to your local machine.
2. Create a `.env` file in the root directory to manage secrets and credentials securely. You can use the following template:

   ```env
   POSTGRES_USER=airflow
   POSTGRES_PASSWORD=airflow
   POSTGRES_DB=airflow
   PGADMIN_EMAIL=admin@admin.com
   PGADMIN_PASSWORD=admin
   ```

3. Ensure Docker and Docker Compose are installed on your system.
4. Launch the entire pipeline using the following command:

   ```bash
   docker compose up -d
   ```

5. The system will download the required images, build the custom Python containers, and initialize the networks and named volumes automatically.

## Example Commands & Access Points

- **Start System:** `docker compose up -d`.  
- **Airflow UI:** Access at http://localhost:8080 to trigger or monitor the ingestion DAGs.  
- **pgAdmin:** Access at http://localhost:5050 to view the PostgreSQL schema and derived indicator tables.  
- **Kibana Dashboards:** Access at http://localhost:5601 to view the visual analytics and market regime heatmaps.

## How to Run

Once the Docker containers are up and running (`docker compose up -d`), you can interact with the various components of the pipeline.

### 1. Accessing Apache Airflow UI

1.  Open your web browser and navigate to [http://localhost:8080](http://localhost:8080).
2.  Log in with the following credentials:
    -   **Username:** `admin`
    -   **Password:** `admin`
3.  Once logged in, you should see the `yfinance_ingestion_dag`. You can manually trigger it by toggling the DAG to "On" and then clicking the "Play" button, or wait for its scheduled run.

### 2. Accessing pgAdmin and Viewing Data

1.  Open your web browser and navigate to [http://localhost:5050](http://localhost:5050).
2.  Log in with the following credentials:
    -   **Email:** `admin@admin.com`
    -   **Password:** `admin`
3.  **Add a New Server:**
    -   In the left-hand panel, right-click on "Servers" and select "Register" -> "Server...".
    -   In the "General" tab, enter a name for your server, e.g., "Financial Market DB".
    -   Go to the "Connection" tab and enter the following details:
        -   **Host name/address:** `postgres` (This is the service name within the Docker network)
        -   **Port:** `5432`
        -   **Maintenance database:** `finance`
        -   **Username:** `airflow`
        -   **Password:** `airflow`
    -   Click "Save".
4.  **Explore the Database:**
    -   Once connected, expand "Servers" -> "Financial Market DB" -> "Databases" -> "finance" -> "Schemas" -> "public" -> "Tables".
    -   You should see the `stock_data` table. Right-click on `stock_data` and select "View/Edit Data" -> "All Rows" to see the ingested financial data.
