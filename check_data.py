from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os

load_dotenv()
es = Elasticsearch(os.getenv('ELASTIC_URL'), api_key=os.getenv('ELASTIC_API_KEY'))

print("=== Checking tempo-exposure index ===\n")

# Count total docs
count = es.count(index="tempo-exposure")
print(f"Total documents: {count['count']}\n")

# Get all documents
result = es.search(index="tempo-exposure", body={"query": {"match_all": {}}, "size": 20})

print(f"Retrieved {len(result['hits']['hits'])} documents:\n")

for hit in result['hits']['hits']:
    src = hit['_source']
    print(f"Timestamp: {src.get('@timestamp')}")
    print(f"Location: {src.get('location')}")
    print(f"Location Name: {src.get('location_name')}")
    print(f"Pollutant: {src.get('pollutant')} = {src.get('value')} (AQI: {src.get('aqi')})")
    print("-" * 60)

# Test a geo query for Evansville coordinates
print("\n=== Testing geo query near Evansville ===")
geo_test = es.search(index="tempo-exposure", body={
    "query": {
        "bool": {
            "filter": [
                {"geo_distance": {"distance": "50km", "location": {"lat": 37.9716, "lon": -87.5711}}}
            ]
        }
    },
    "size": 10
})

print(f"Geo query found {len(geo_test['hits']['hits'])} documents")

# Test timestamp filter (last 3 hours)
print("\n=== Testing timestamp filter (last 3h) ===")
time_test = es.search(index="tempo-exposure", body={
    "query": {
        "range": {"@timestamp": {"gte": "now-3h"}}
    },
    "size": 10
})

print(f"Time query found {len(time_test['hits']['hits'])} documents")

# Combined query (what your backend uses)
print("\n=== Testing combined query (geo + time) ===")
combined_test = es.search(index="tempo-exposure", body={
    "query": {
        "bool": {
            "filter": [
                {"range": {"@timestamp": {"gte": "now-3h"}}},
                {"geo_distance": {"distance": "50km", "location": {"lat": 37.9716, "lon": -87.5711}}}
            ]
        }
    },
    "size": 10
})

print(f"Combined query found {len(combined_test['hits']['hits'])} documents")