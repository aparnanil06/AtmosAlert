import os, requests
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from elasticsearch import Elasticsearch, helpers
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()
ES_URL = os.getenv("ELASTIC_URL")
ES_KEY = os.getenv("ELASTIC_API_KEY")
AIRNOW_KEY = os.getenv("AIRNOW_API_KEY")
INDEX = "tempo-exposure"

class AlertSubscription(BaseModel):
    email: str
    location: str
    threshold: int = 100


if not ES_URL or not ES_KEY:
    raise RuntimeError("Set ELASTIC_URL and ELASTIC_API_KEY in .env")

# FIXED: Use api_key parameter instead of headers
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
    if aqi is None: 
        return {"label":"Unknown","message":"No guidance available.","band":[None,None]}
    for lo, hi, label, msg in AQI_BANDS:
        if lo <= aqi <= hi: 
            return {"label":label,"message":msg,"band":[lo,hi]}
    return {"label":"Unknown","message":"No guidance available.","band":[None,None]}

def exposure_score(pm25_24h: Optional[float], years: float=10.0):
    if pm25_24h is None: 
        return {"score":0,"stress_pct":0}
    REF = 15.0
    ratio = max(pm25_24h/REF, 0.0)
    score = min(ratio * years * 10, 100)
    return {"score":score, "stress_pct":round(score)}

def geocode(address: str):
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
        print("Warning: AIRNOW_API_KEY not set")
        return []
    url = "https://www.airnowapi.org/aq/observation/latLong/current/"
    params = {
        "format": "application/json",
        "latitude": lat,
        "longitude": lon,
        "distance": distance_miles,
        "API_KEY": AIRNOW_KEY
    }
    
    print(f"Fetching AirNow data for lat={lat}, lon={lon}, distance={distance_miles}mi")
    
    try:
        r = requests.get(url, params=params, timeout=10)
        print(f"AirNow API response: {r.status_code}")
        if r.status_code != 200:
            print(f"AirNow API error: {r.text}")
            return []
        
        raw_data = r.json()
        print(f"AirNow returned {len(raw_data)} observations")
        
    except requests.exceptions.Timeout:
        print(f"AirNow API timeout for lat={lat}, lon={lon}")
        return []
    except Exception as e:
        print(f"AirNow API error: {e}")
        return []
    
    rows = []
    pmap = {"PM2.5":"pm25","PM10":"pm10","O3":"o3","NO2":"no2","CO":"co","SO2":"so2"}
    
    for obs in raw_data:
        try:
            pollutant = pmap.get(obs.get("ParameterName"), obs.get("ParameterName"))
            hour = str(obs.get("HourObserved", 0)).zfill(2)
            date_obs = obs.get("DateObserved", "")
            if not date_obs:
                continue
                
            ts = f"{date_obs}T{hour}:00:00Z"
            
            # Get both AQI and raw concentration value
            aqi_val = obs.get("AQI")
            raw_val = obs.get("Value")
            
            # Skip if we have neither
            if aqi_val is None and raw_val is None:
                continue
            
            row = {
                "@timestamp": ts,
                "pollutant": pollutant,
                "value": raw_val,          # concentration for analytics
                "aqi": aqi_val,            # AQI number for display
                "unit": obs.get("Unit") or "AQI",
                "location": {"lat": obs.get("Latitude"), "lon": obs.get("Longitude")},
                "location_name": obs.get("ReportingArea"),
                "aqi_category": (obs.get("Category") or {}).get("Name"),
                "source": "EPA AirNow"
            }
            rows.append(row)
        except Exception as e:
            print(f"Error processing observation: {e}")
            continue
    
    print(f"Normalized {len(rows)} observations")
    return rows

def index_docs_idempotent(rows: List[Dict[str, Any]]) -> int:
    if not rows: 
        return 0
    actions = []
    for r in rows:
        doc_id = f"{r.get('location_name')}|{r.get('pollutant')}|{r.get('@timestamp')}"
        actions.append({"_index": INDEX, "_id": doc_id, "_op_type": "index", "_source": r})
    
    try:
        helpers.bulk(es, actions)
        print(f"Indexed {len(actions)} documents")
    except Exception as e:
        print(f"Error indexing documents: {e}")
        return 0
    
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

# Ensure index exists on startup
@app.on_event("startup")
def ensure_index():
    if not es.indices.exists(index=INDEX):
        es.indices.create(index=INDEX, body={
            "mappings": {
                "properties": {
                    "@timestamp": {"type": "date"},
                    "pollutant": {"type": "keyword"},
                    "value": {"type": "float"},
                    "aqi": {"type": "integer"},
                    "location": {"type": "geo_point"},
                    "location_name": {"type": "keyword"}
                }
            }
        })
        print(f"Created index: {INDEX}")
    else:
        print(f"Index {INDEX} already exists")

# ----- Debug Endpoint -----
@app.get("/api/test-es")
def test_es(lat: float = 37.9716, lon: float = -87.5711, radius_km: float = 25.0):
    """Debug endpoint to test Elasticsearch queries"""
    
    # Test 1: Can we connect?
    try:
        es.ping()
        connection_ok = True
    except Exception as e:
        return {"error": f"ES connection failed: {e}"}
    
    # Test 2: How many docs total?
    count = es.count(index=INDEX)
    
    # Test 3: Latest query (what your backend uses)
    latest_q = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"range": {"@timestamp": {"gte": "now-3h"}}},
            {"geo_distance": {"distance": f"{radius_km}km", "location": {"lat": lat, "lon": lon}}}
        ]}},
        "aggs": {"by_pollutant": {"terms": {"field": "pollutant", "size": 10},
                 "aggs": {"latest": {"top_hits": {"size": 1, "sort": [{"@timestamp": "desc"}],
                           "_source": {"includes": ["aqi","value","unit","location_name"]}}}}}}
    }
    
    try:
        latest_res = es.search(index=INDEX, body=latest_q)
        buckets = latest_res["aggregations"]["by_pollutant"]["buckets"]
    except Exception as e:
        return {"error": f"Query failed: {e}", "query": latest_q}
    
    return {
        "connection_ok": connection_ok,
        "total_docs": count['count'],
        "buckets_found": len(buckets),
        "buckets": buckets,
        "sample_query": latest_q
    }

# ----- Main API -----
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
        print(f"Geocoded address '{address}' to lat={lat}, lon={lon}")
    elif zip:
        lat, lon = geocode(zip)
        print(f"Geocoded ZIP '{zip}' to lat={lat}, lon={lon}")
    
    if lat is None or lon is None:
        raise HTTPException(400, "Provide lat/lon or address/zip")

    # 2) Latest per pollutant from ES (last 24h to catch older data)
    latest_q = {
        "size": 0,
        "query": {"bool": {"filter": [
            {"range": {"@timestamp": {"gte": "now-24h"}}},
            {"geo_distance": {"distance": f"{radius_km}km", "location": {"lat": lat, "lon": lon}}}
        ]}},
        "aggs": {"by_pollutant": {"terms": {"field": "pollutant", "size": 10},
                 "aggs": {"latest": {"top_hits": {"size": 1, "sort": [{"@timestamp": "desc"}],
                           "_source": {"includes": ["aqi","value","unit","location_name"]}}}}}}
    }
    
    try:
        latest_res = es.search(index=INDEX, body=latest_q)
        buckets = latest_res["aggregations"]["by_pollutant"]["buckets"]
        print(f"Found {len(buckets)} pollutant buckets in ES")
    except Exception as e:
        print(f"Elasticsearch query failed: {e}")
        raise HTTPException(500, f"Elasticsearch query failed: {e}")

    # 3) If sparse, try live-fetch from AirNow and index, then rerun
    if len(buckets) < 2:
        print(f"Only {len(buckets)} pollutants found, fetching from AirNow...")
        fetched = airnow_latest(lat, lon, distance_miles=int(radius_km * 0.621))
        
        if fetched:
            print(f"Fetched {len(fetched)} observations from AirNow")
            indexed = index_docs_idempotent(fetched)
            print(f"Indexed {indexed} documents")
            
            # Force ES to refresh and wait
            try:
                es.indices.refresh(index=INDEX)
                print("Forced ES index refresh")
            except Exception as e:
                print(f"ES refresh warning: {e}")
            
            import time
            time.sleep(1.0)  # Longer delay
            
            try:
                latest_res = es.search(index=INDEX, body=latest_q)
                buckets = latest_res["aggregations"]["by_pollutant"]["buckets"]
                print(f"After AirNow fetch: {len(buckets)} pollutant buckets")
                
                # If still no buckets, query the raw docs to debug
                if len(buckets) == 0:
                    debug_q = {
                        "size": 5,
                        "query": {"match_all": {}},
                        "sort": [{"@timestamp": "desc"}]
                    }
                    debug_res = es.search(index=INDEX, body=debug_q)
                    print(f"DEBUG: Total docs in index: {debug_res['hits']['total']['value']}")
                    if debug_res['hits']['hits']:
                        print(f"DEBUG: Sample doc: {debug_res['hits']['hits'][0]['_source']}")
                        
            except Exception as e:
                print(f"Elasticsearch requery failed: {e}")
                raise HTTPException(500, f"Elasticsearch requery failed: {e}")
        else:
            print("No data returned from AirNow API")

    rows: List[PollutantRow] = []
    area_name = None
    for b in buckets:
        hits = b["latest"]["hits"]["hits"]
        if not hits:
            continue
        src = hits[0]["_source"]
        
        # Get AQI - this should always be present
        aqi_val = src.get("aqi")
        
        # Get raw value, but if null and we have AQI, estimate from AQI
        raw_val = src.get("value")
        if raw_val is None and aqi_val is not None and b["key"] == "pm25":
            # Rough conversion: PM2.5 AQI to µg/m³ (simplified)
            if aqi_val <= 50:
                raw_val = aqi_val * 0.24  # 0-50 AQI = 0-12 µg/m³
            elif aqi_val <= 100:
                raw_val = 12 + (aqi_val - 50) * 0.28  # 51-100 = 12.1-35.4
            else:
                raw_val = 35.4 + (aqi_val - 100) * 0.289  # rough estimate
        
        rows.append(PollutantRow(
            pollutant=b["key"],
            latest_aqi=aqi_val,
            latest_value=raw_val,
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
        "aggs": {"by_pollutant": {"terms": {"field": "pollutant", "size": 10},
                 "aggs": {
                     "avg_value": {"avg": {"field": "value"}},
                     "avg_aqi": {"avg": {"field": "aqi"}}
                 }}}
    }
    
    try:
        avg_res = es.search(index=INDEX, body=avg_q)
        avg_map = {}
        for b in avg_res["aggregations"]["by_pollutant"]["buckets"]:
            val = b["avg_value"].get("value")
            # If value is null, estimate from AQI for PM2.5
            if val is None and b["key"] == "pm25":
                aqi_avg = b["avg_aqi"].get("value")
                if aqi_avg is not None:
                    if aqi_avg <= 50:
                        val = aqi_avg * 0.24
                    elif aqi_avg <= 100:
                        val = 12 + (aqi_avg - 50) * 0.28
                    else:
                        val = 35.4 + (aqi_avg - 100) * 0.289
            avg_map[b["key"]] = val
    except Exception as e:
        print(f"24h average query failed: {e}")
        avg_map = {}

    # Update rows with 24h averages
    for r in rows:
        r.avg24_value = avg_map.get(r.pollutant)

    # 5) Overall category & exposure
    overall_aqi_vals = [r.latest_aqi for r in rows if r.latest_aqi is not None]
    overall_aqi = max(overall_aqi_vals) if overall_aqi_vals else None
    overall = aqi_category(overall_aqi)
    pm25_avg = avg_map.get("pm25")
    exposure = exposure_score(pm25_avg, years=10.0)

    print(f"Returning: area={area_name}, aqi={overall_aqi}, {len(rows)} pollutants")

    return {
        "area_name": area_name,
        "overall_aqi": overall_aqi,
        "overall_category": overall,
        "rows": [r.dict() for r in rows],
        "exposure": exposure
    }

# FEV1 prediction endpoint
@app.get("/api/predict")
def predict_fev1(location: str = Query(...)):
    """Predict FEV1 lung capacity decline based on location's air quality"""
    try:
        # Get coordinates from location
        lat, lon = geocode(location)
        print(f"FEV1 prediction for {location}: lat={lat}, lon={lon}")
        
        # Get 24h average PM2.5 from ES
        avg_q = {
            "size": 0,
            "query": {"bool": {"filter": [
                {"range": {"@timestamp": {"gte": "now-24h"}}},
                {"geo_distance": {"distance": "50km", "location": {"lat": lat, "lon": lon}}},
                {"term": {"pollutant": "pm25"}}
            ]}},
            "aggs": {
                "avg_pm25_value": {"avg": {"field": "value"}},
                "avg_pm25_aqi": {"avg": {"field": "aqi"}}
            }
        }
        
        try:
            result = es.search(index=INDEX, body=avg_q)
            pm25_avg = result["aggregations"]["avg_pm25_value"].get("value")
            
            # If raw value is null, estimate from AQI
            if pm25_avg is None:
                pm25_aqi = result["aggregations"]["avg_pm25_aqi"].get("value")
                if pm25_aqi is not None:
                    print(f"Estimating PM2.5 from AQI: {pm25_aqi}")
                    if pm25_aqi <= 50:
                        pm25_avg = pm25_aqi * 0.24
                    elif pm25_aqi <= 100:
                        pm25_avg = 12 + (pm25_aqi - 50) * 0.28
                    else:
                        pm25_avg = 35.4 + (pm25_aqi - 100) * 0.289
                        
        except Exception as e:
            print(f"ES query failed for FEV1: {e}")
            pm25_avg = None
        
        # If no ES data, try AirNow
        if pm25_avg is None:
            print("No PM2.5 data in ES, fetching from AirNow...")
            fetched = airnow_latest(lat, lon, distance_miles=30)
            if fetched:
                index_docs_idempotent(fetched)
                pm25_vals = [d["value"] for d in fetched if d.get("pollutant") == "pm25" and d.get("value") is not None]
                pm25_avg = sum(pm25_vals) / len(pm25_vals) if pm25_vals else None
        
        # Calculate FEV1 decline (simplified model)
        if pm25_avg is None:
            # Default to moderate air quality assumption
            pm25_avg = 12.0
            print(f"No PM2.5 data available, using default: {pm25_avg}")
        else:
            print(f"Average PM2.5: {pm25_avg}")
        
        # Simple linear model: baseline 100%, lose ~0.5% per year per 10 µg/m³ above 10
        baseline_fev1 = 100.0
        years = 5.0
        pm25_threshold = 10.0
        decline_rate = 0.5  # % per year per 10 µg/m³
        
        excess_pm25 = max(0, pm25_avg - pm25_threshold)
        annual_decline = (excess_pm25 / 10.0) * decline_rate
        total_decline = annual_decline * years
        projected_capacity = max(baseline_fev1 - total_decline, 60.0)  # floor at 60%
        
        # Determine risk level
        if projected_capacity >= 90:
            risk_level = "low"
        elif projected_capacity >= 80:
            risk_level = "moderate"
        else:
            risk_level = "high"
        
        return {
            "location": location,
            "projected_capacity_percent": round(projected_capacity, 1),
            "risk_level": risk_level,
            "pm25_avg": round(pm25_avg, 1) if pm25_avg else None,
            "years_projected": years
        }
        
    except Exception as e:
        print(f"FEV1 prediction error: {e}")
        raise HTTPException(500, f"Failed to predict FEV1: {e}")

@app.get("/health")
def health():
    ok = es.ping()
    return {"ok": ok}

@app.post("/api/subscribe")
def subscribe_alerts(subscription: AlertSubscription):
    """Subscribe to air quality alerts"""
    import sys
    sys.path.append('.')
    from notifications import add_user
    
    # Detect if it's a ZIP code or address
    location_type = "zip" if subscription.location.isdigit() else "address"
    result = add_user(subscription.email, location_type, subscription.location, subscription.threshold)
    
    if result.get('success'):
        return {"success": True, "message": "Successfully signed up for alerts!"}
    else:
        raise HTTPException(400, detail=result.get('error', 'Failed to sign up'))