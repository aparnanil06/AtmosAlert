# ingest/airnow.py
import os
import requests
from datetime import datetime
from zoneinfo import ZoneInfo  # Py3.9+
from dotenv import load_dotenv
from elasticsearch import Elasticsearch, helpers

# ---------------- Env & ES ----------------
load_dotenv()
ELASTIC_URL = os.getenv("ELASTIC_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")
AIRNOW_API_KEY = os.getenv("AIRNOW_API_KEY")  # get one free at https://docs.airnowapi.org/

assert ELASTIC_URL and ELASTIC_API_KEY, "Set ELASTIC_URL and ELASTIC_API_KEY in .env"
assert AIRNOW_API_KEY, "Set AIRNOW_API_KEY in .env"

es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY)

# ---------------- Helpers ----------------
PARAM_MAP = {"PM2.5": "pm25", "PM10": "pm10", "O3": "o3", "NO2": "no2", "CO": "co", "SO2": "so2"}

TZ_MAP = {
    "CST": "America/Chicago", "CDT": "America/Chicago",
    "EST": "America/New_York", "EDT": "America/New_York",
    "MST": "America/Denver",  "MDT": "America/Denver",
    "PST": "America/Los_Angeles","PDT": "America/Los_Angeles"
}

def to_utc_iso(date_observed: str, hour_observed, local_tz: str | None) -> str:
    hour = int(hour_observed)
    # resolve tz
    tz_key = (local_tz or "").strip()
    iana = TZ_MAP.get(tz_key, tz_key) or "America/Chicago"
    try:
        tzinfo = ZoneInfo(iana)
    except Exception:
        # final fallback
        tzinfo = ZoneInfo("America/Chicago")
    # build local dt → UTC
    dt_local = datetime.strptime(date_observed, "%Y-%m-%d").replace(
        hour=hour, minute=0, second=0, microsecond=0, tzinfo=tzinfo
    )
    return dt_local.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z")

PARAM_MAP = {"PM2.5": "pm25", "PM10": "pm10", "O3": "o3", "NO2": "no2", "CO": "co", "SO2": "so2"}

def normalize_obs(obs: dict) -> dict | None:
    try:
        param = PARAM_MAP.get(obs.get("ParameterName"), obs.get("ParameterName"))
        unit = (obs.get("Unit") or "AQI").strip() if isinstance(obs.get("Unit"), str) else "AQI"

        ts = to_utc_iso(
            obs.get("DateObserved"), 
            obs.get("HourObserved"), 
            obs.get("LocalTimeZone")
        )

        lat = obs.get("Latitude")
        lon = obs.get("Longitude")
        val_aqi = obs.get("AQI")
        val_raw = obs.get("Value")

        # require timestamp and coordinates; accept AQI or raw concentration
        if not ts or lat is None or lon is None or (val_aqi is None and val_raw is None):
            return None

        return {
            "date": {"utc": ts},
            "parameter": param,
            "value": val_aqi,              # AQI
            "raw_value": val_raw,          # concentration
            "unit": unit,
            "coordinates": {"latitude": lat, "longitude": lon},
            "location_name": obs.get("ReportingArea"),
            "aqi_category": (obs.get("Category") or {}).get("Name"),
        }
    except Exception as e:
        # print one sample to help debug if needed
        print("normalize_obs error:", e, "obs:", {k: obs.get(k) for k in ("ParameterName","DateObserved","HourObserved","LocalTimeZone","Latitude","Longitude","AQI","Value")})
        return None


# ---------------- AirNow fetchers ----------------
def fetch_airnow_by_zipcode(zipcode="47711", distance_miles=50):
    """Current observations by ZIP (Evansville default)."""
    url = "https://www.airnowapi.org/aq/observation/zipCode/current/"
    params = {
        "format": "application/json",
        "zipCode": zipcode,
        "distance": distance_miles,  # miles
        "API_KEY": AIRNOW_API_KEY,
    }
    r = requests.get(url, params=params, timeout=30)
    safe_url = r.url.replace(AIRNOW_API_KEY, "***")
    print(f"GET ZIP: {safe_url} | status: {r.status_code}")
    if r.status_code != 200:
        print("Error:", r.text)
        return []
    raw = r.json()
    results = [doc for obs in raw if (doc := normalize_obs(obs)) is not None]
    print(f"ZIP results: {len(results)} of {len(raw)}")
    return results

def fetch_airnow_by_coords(lat, lon, distance_miles=50):
    """Current observations by lat/long center + distance (miles)."""
    url = "https://www.airnowapi.org/aq/observation/latLong/current/"
    params = {
        "format": "application/json",
        "latitude": lat,
        "longitude": lon,
        "distance": distance_miles,  # miles
        "API_KEY": AIRNOW_API_KEY,
    }
    r = requests.get(url, params=params, timeout=30)
    safe_url = r.url.replace(AIRNOW_API_KEY, "***")
    print(f"GET COORDS: {safe_url} | status: {r.status_code}")
    if r.status_code != 200:
        print("Error:", r.text)
        return []
    raw = r.json()
    results = [doc for obs in raw if (doc := normalize_obs(obs)) is not None]
    print(f"COORD results: {len(results)} of {len(raw)}")
    return results

# ---------------- ES bulk load ----------------
def load_to_elastic(results: list[dict]):
    if not results:
        print("No valid documents to insert")
        return
    actions = []
    for r in results:
        actions.append({
            "_index": "tempo-exposure",
            "_source": {
                "@timestamp": r["date"]["utc"],
                "pollutant": r["parameter"],
                "value": r["raw_value"],  # store concentration for analytics
                "aqi": r["value"],        # store AQI separately for alerts
                "unit": r["unit"],
                "location": {"lat": r["coordinates"]["latitude"], "lon": r["coordinates"]["longitude"]},
                "location_name": r.get("location_name"),
                "aqi_category": r.get("aqi_category"),
                "source": "EPA AirNow",
            }
        })
    helpers.bulk(es, actions)
    print(f"Inserted {len(actions)} docs into tempo-exposure")

# ---------------- Main ----------------
if __name__ == "__main__":
    print("Fetching AirNow data for Evansville, IN (ZIP 47711)…")
    data = fetch_airnow_by_zipcode("47711", distance_miles=50)

    if not data:
        print("ZIP returned nothing; trying coordinates near Evansville…")
        # Downtown Evansville approx
        data = fetch_airnow_by_coords(37.9716, -87.5711, distance_miles=50)

    if data:
        print("Stations:", sorted({d.get("location_name") for d in data if d.get("location_name")}))
        load_to_elastic(data)
    else:
        print("No data available from AirNow. Check your API key or widen distance.")
