import os, requests
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv

load_dotenv()
ES_URL = os.getenv("ELASTIC_URL")
ES_KEY = os.getenv("ELASTIC_API_KEY")
AIRNOW_KEY = os.getenv("AIRNOW_API_KEY")
INDEX = "tempo-exposure"

if not ES_URL or not ES_KEY:
    raise RuntimeError("Set ELASTIC_URL and ELASTIC_API_KEY in .env")

es = Elasticsearch(ES_URL, api_key=ES_KEY)

app = FastAPI(title="AirTime Capsule API", version="0.1.0")

# CORS so your web frontend can call this
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----- Helpers -----
AQI_BANDS = [
    (0, 50, "Good", "Air quality is good. Enjoy outdoor activities."),
    (51, 100, "Moderate", "Unusually sensitive people should reduce prolonged or heavy exertion outdoors."),
    (101, 150, "Unhealthy for Sensitive Groups",
     "People with asthma, children, older adults: reduce strenuous outdoor activity; consider masks if smoky."),
    (151, 200, "Unhealthy",
     "Everyone reduce prolonged outdoor exertion; sensitive groups stay indoors with clean air."),
    (201, 300, "Very Unhealthy",
     "Avoid outdoor activity; use clean air rooms/filters; follow local advisories."),
    (301, 500, "Hazardous",
     "Stay indoors with HEPA filtration; avoid exertion; follow emergency guidance.")
]
def aqi_category(aqi: Optional[int]):
    if aqi is None: return {"label":"Unknown","message":"No guidance available.","band":[None,None]}
    for lo, hi, label, msg in AQI_BANDS:
        if lo <= aqi <= hi: return {"label":label,"message":msg,"band":[lo,hi]}
    return {"label":"Unknown","message":"No guidance available.","band":[None,None]}

def exposure_score(pm25_24h: Optional[float], years: float=10.0):
    # Heuristic vs WHO PM2.5 daily guideline (15 µg/m³). You can switch to EPA (35) if desired.
    if pm25_24h is None: return {"score":0,"stress_pct":0}
    REF = 15.0
    ratio = max(pm25_24h/REF, 0.0)
    score = min(ratio * years * 10, 100)
    return {"score":score, "stress_pct":round(score)}

def geocode(address: str):
    # Simple geocoder via Nominatim (no key). Replace with Mapbox/Google later if needed.
    r = requests.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": address, "format": "json", "limit": 1},
        headers={"User-Agent": "AirTimeCapsule/1.0"}
    )
    r.raise_for_status()
    data = r.json()
    if not data:
        raise HTTPException(404, "Address not found")
    return float(data[0]["lat"]), float(data[0]["lon"])

def airnow_latest(lat: float, lon: float, distance_miles: int = 50) -> List[Dict[str, Any]]:
    """On-demand fetch from AirNow for any location; normalized to our index schema."""
    if not AIRNOW_KEY:
        return []
    url = "https://www.airnowapi.org/aq/observation/latLong/current/"
    params = {
        "format": "application/json",
        "latitude": lat,
        "longitude": lon,
        "distance": distance_miles,  # miles
        "API_KEY": AIRNOW_KEY
    }
    r = requests.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return []
    rows = []
    pmap = {"PM2.5":"pm25","PM10":"pm10","O3":"o3","NO2":"no2","CO":"co","SO2":"so2"}
    for obs in r.json():
        pollutant = pmap.get(obs.get("ParameterName"), obs.get("ParameterName"))
        hour = str(obs.get("HourObserved")).zfill(2)
        # AirNow’s DateObserved/HourObserved are local; for simplicity we tag as Z (ok for demo freshness).
        ts = f"{obs.get('DateObserved')}T{hour}:00:00Z"
        row = {
            "@timestamp": ts,
            "pollutant": pollutant,
            "value": obs.get("Value"),     # concentration
            "aqi": obs.get("AQI"),         # AQI number
            "unit": obs.get("Unit") or "AQI",
            "location": {"lat": obs.get("Latitude"), "lon": obs.get("Longitude")},
            "location_name": obs.get("ReportingArea"),
            "aqi_category": (obs.get("Category") or {}).get("Name"),
            "source": "EPA AirNow"
        }
        rows.append(row)
    return rows

def index_docs_idempotent(rows: List[Dict[str, Any]]) -> int:
    if not rows: return 0
    actions = []
    for r in rows:
        doc_id = f"{r.get('location_name')}|{r.get('pollutant')}|{r.get('@timestamp')}"
        actions.append({"_index": INDEX, "_id": doc_id, "_op_type": "index", "_source": r})
    helpers.bulk(es, actions)
    return len(actions)

# ----- Schemas -----
class PollutantRow(BaseModel):
    pollutant: str
    latest_aqi: int | None
    latest_value: float | None
    unit: str | None
    avg24_value: float | None

class AQResponse(BaseModel):
    area_name: str | None
    overall_aqi: int | None
    overall_category: Dict[str, Any]
    rows: List[PollutantRow]
    exposure: Dict[str, Any]

# ----- API -----
@app.get("/api/aqi", response_model=AQResponse)
def get_aqi(
    lat: float | None = Query(default=None),
    lon: float | None = Query(default=None),
    address: str | None = Query(default=None),
    zip: str | None = Query(default=None),
    radius_km: float = Query(25.0, ge=1.0, le=200.0)
):
    # 1) Resolve coordinates
    if address:
        lat, lon = geocode(address)
    elif zip:
        lat, lon = geocode(zip)
    if lat is None or lon is None:
        raise HTTPException(400, "Provide lat/lon or address/zip")

    # 2) Latest per pollutant from ES (last 3h)
    latest_q = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"range": {"@timestamp": {"gte": "now-3h"}}},
            {"geo_distance": {"distance": f"{radius_km}km", "location": {"lat": lat, "lon": lon}}}
        ]}},
        "aggs": {"by_pollutant": {"terms": {"field": "pollutant.keyword", "size": 10},
                 "aggs": {"latest": {"top_hits": {"size": 1, "sort": [{"@timestamp": "desc"}],
                           "_source": {"includes": ["aqi","value","unit","location_name"]}}}}}}
    }
    latest_res = es.search(index=INDEX, body=latest_q)
    buckets = latest_res["aggregations"]["by_pollutant"]["buckets"]

    # 3) If sparse, live-fetch from AirNow and index, then rerun
    if len(buckets) < 2:
        fetched = airnow_latest(lat, lon, distance_miles=int(radius_km * 0.621))
        if fetched:
            index_docs_idempotent(fetched)
            latest_res = es.search(index=INDEX, body=latest_q)
            buckets = latest_res["aggregations"]["by_pollutant"]["buckets"]

    rows: List[PollutantRow] = []
    area_name = None
    for b in buckets:
        src = b["latest"]["hits"]["hits"][0]["_source"]
        rows.append(PollutantRow(
            pollutant=b["key"],
            latest_aqi=src.get("aqi"),
            latest_value=src.get("value"),
            unit=src.get("unit"),
            avg24_value=None
        ))
        area_name = area_name or src.get("location_name")

    # 4) 24h averages (for exposure & table)
    avg_q = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"range": {"@timestamp": {"gte": "now-24h"}}},
            {"geo_distance": {"distance": f"{radius_km}km", "location": {"lat": lat, "lon": lon}}}
        ]}},
        "aggs": {"by_pollutant": {"terms": {"field": "pollutant.keyword", "size": 10},
                 "aggs": {"avg_value": {"avg": {"field": "value"}}}}}
    }
    avg_res = es.search(index=INDEX, body=avg_q)
    avg_map = {b["key"]: b["avg_value"]["value"] for b in avg_res["aggregations"]["by_pollutant"]["buckets"]}

    # 5) Overall category & exposure
    overall_aqi_vals = [r.latest_aqi for r in rows if r.latest_aqi is not None]
    overall_aqi = max(overall_aqi_vals) if overall_aqi_vals else None
    overall = aqi_category(overall_aqi)
    pm25_avg = avg_map.get("pm25")
    exposure = exposure_score(pm25_avg, years=10.0)

    return {
        "area_name": area_name,
        "overall_aqi": overall_aqi,
        "overall_category": overall,
        "rows": [r.dict() for r in rows],
        "exposure": exposure
    }

@app.get("/health")
def health():
    ok = es.ping()
    return {"ok": ok}
