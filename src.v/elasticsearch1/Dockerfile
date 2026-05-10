FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY elasticsearch_indexer.py .
COPY kibana_setup.py .

CMD ["python", "elasticsearch_indexer.py"]
