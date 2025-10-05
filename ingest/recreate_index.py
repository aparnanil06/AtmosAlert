from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
ELASTIC_URL = os.getenv("ELASTIC_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")

if not ELASTIC_URL or not ELASTIC_API_KEY:
    raise RuntimeError("Set ELASTIC_URL and ELASTIC_API_KEY in .env")

# Connect to Elasticsearch
es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY)

INDEX_NAME = "tempo-exposure"

print(f"Checking if index '{INDEX_NAME}' exists...")

# Delete old index if it exists
if es.indices.exists(index=INDEX_NAME):
    print(f"Deleting existing index '{INDEX_NAME}'...")
    es.indices.delete(index=INDEX_NAME)
    print("✓ Deleted old index")
else:
    print(f"Index '{INDEX_NAME}' does not exist yet")

# Create new index with proper mappings
print(f"\nCreating index '{INDEX_NAME}' with proper mappings...")

es.indices.create(
    index=INDEX_NAME,
    body={
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "pollutant": {"type": "keyword"},
                "value": {"type": "float"},
                "aqi": {"type": "integer"},
                "location": {"type": "geo_point"},  # This is the critical fix
                "location_name": {"type": "keyword"},
                "aqi_category": {"type": "keyword"},
                "unit": {"type": "keyword"},
                "source": {"type": "keyword"}
            }
        }
    }
)

print("✓ Created new index with geo_point mapping")

# Verify the mapping
mapping = es.indices.get_mapping(index=INDEX_NAME)
print(f"\nVerified mapping for '{INDEX_NAME}':")
print(f"  - location field type: {mapping[INDEX_NAME]['mappings']['properties']['location']['type']}")

print("\n" + "="*60)
print("SUCCESS! Index is ready.")
print("="*60)
print("\nNext steps:")
print("1. Run: python3 ingest/airnow.py")
print("2. Test API: http://localhost:8090/api/aqi?address=Chicago")