import csv, os
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv

load_dotenv()
ES_URL = os.getenv("ELASTIC_URL")
ES_KEY = os.getenv("ELASTIC_API_KEY")
CSV_PATH = os.getenv("TEMPO_CSV", "data/tempo_subset.csv")

es = Elasticsearch(ES_URL, api_key=ES_KEY)

def docs_from_csv(path):
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            # basic validation
            if not row.get("timestamp") or not row.get("lat") or not row.get("lon"):
                continue
            yield {
                "_index": "tempo-exposure",
                "_source": {
                    "@timestamp": row["timestamp"],
                    "pollutant": row["pollutant"].lower(),
                    "value": float(row["value"]),
                    "unit": row.get("unit") or "",
                    "location": {"lat": float(row["lat"]), "lon": float(row["lon"])},
                    "source": row.get("source", "TEMPO")
                }
            }

if __name__ == "__main__":
    batch = list(docs_from_csv(CSV_PATH))
    if not batch:
        print("No rows found; check CSV path/schema.")
    else:
        helpers.bulk(es, batch)
        print(f"Indexed {len(batch)} docs into tempo-exposure")
