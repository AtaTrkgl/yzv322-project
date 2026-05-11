from airflow import DAG
from airflow.providers.docker.operators.docker import DockerOperator
from datetime import datetime, timedelta
import os
from docker.types import Mount

default_args = {
    'owner': 'data_eng',
    'depends_on_past': True,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'yfinance_ingestion_dag',
    default_args=default_args,
    description='A simple DAG to ingest OHLCV data using yfinance',
    schedule_interval='@daily',
    start_date=datetime(2026, 1, 1),
    catchup=True,
    max_active_runs=1,
    tags=['ingestion', 'yfinance', 'docker'],
) as dag:
    
    run_ingestion = DockerOperator(
        task_id='fetch_yfinance_data',
        image='ingestion-service:latest',
        api_version='auto',
        auto_remove=True,
        # No --tickers argument supplied, meaning it will fallback to the ticks list in python
        command="python yfinance_fetcher.py --start {{ ds }} --end {{ data_interval_end | ds }} --output /data",
        docker_url='unix://var/run/docker.sock',
        network_mode='yzv322-project_pipeline-net',
        mount_tmp_dir=False,
        mounts=[
            Mount(source='ingestion_data', target='/data', type='volume')
        ]
    )

    transform_data = DockerOperator(
        task_id='transform_yfinance_data',
        image='ingestion-service:latest',
        api_version='auto',
        auto_remove=True,
        command="python transformer.py --data-dir /data --date {{ ds }}",
        docker_url='unix://var/run/docker.sock',
        network_mode='yzv322-project_pipeline-net',
        mount_tmp_dir=False,
        mounts=[
            Mount(source='ingestion_data', target='/data', type='volume')
        ]
    )

    load_to_postgres = DockerOperator(
        task_id='load_to_postgres',
        image='ingestion-service:latest',
        api_version='auto',
        auto_remove=True,
        command="python postgres_loader.py --data-dir /data --date {{ ds }}",
        docker_url='unix://var/run/docker.sock',
        network_mode='yzv322-project_pipeline-net',
        mount_tmp_dir=False,
        environment={
            'POSTGRES_HOST': 'postgres',
            'POSTGRES_PORT': '5432',
            'POSTGRES_USER': 'airflow',
            'POSTGRES_PASSWORD': 'airflow',
            'POSTGRES_DB': 'airflow'
        },
        mounts=[
            Mount(source='ingestion_data', target='/data', type='volume')
        ]
    )
    
    run_ingestion >> transform_data >> load_to_postgres
