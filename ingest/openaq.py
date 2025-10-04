import requests
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
import os

# ---- Load env vars ----
load_dotenv()
ELASTIC_URL = os.getenv("ELASTIC_URL")
API_KEY = os.getenv("ELASTIC_API_KEY")

es = Elasticsearch(ELASTIC_URL, api_key=API_KEY)


# ---- Fetch data from OpenAQ ----
def fetch_openaq(lat, lon, radius_km=500):
    url = "https://api.openaq.org/v3/measurements"
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": radius_km * 1000,  # in meters
        "parameter[]": ["pm25", "no2"],
        "limit": 50,
        "sort": "desc"
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    return r.json()["results"]

# ---- Load into Elasticsearch ----
def load_to_elastic(results):
    actions = []
    for r in results:
        actions.append({
            "_index": "tempo-exposure",
            "_source": {
                "@timestamp": r["date"]["utc"],
                "pollutant": r["parameter"],
                "value": r["value"],
                "unit": r["unit"],
                "location": {
                    "lat": r["coordinates"]["latitude"],
                    "lon": r["coordinates"]["longitude"]
                },
                "source": "OpenAQ"
            }
        })
    if actions:
        helpers.bulk(es, actions)
        print(f"Inserted {len(actions)} docs into tempo-exposure")

# ---- Run it ----
if __name__ == "__main__":
    data = fetch_openaq(40.1106, -88.2073)  # Example: Champaign, IL
    load_to_elastic(data)
