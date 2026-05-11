import urllib.request
import json
import time

max_retries = 5
for i in range(max_retries):
    try:
        req = urllib.request.Request('http://localhost:9200/stock_market/_count')
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode())
        if data['count'] > 0:
            print(f"Success! {data['count']} documents found in Elasticsearch.")
            exit(0)
        else:
            print(f"Attempt {i+1}: 0 documents found. Retrying in 2 seconds...")
            time.sleep(2)
    except Exception as e:
        print(f"Attempt {i+1}: Error: {e}. Retrying in 2 seconds...")
        time.sleep(2)
print("Failed to find documents in Elasticsearch.")
exit(1)