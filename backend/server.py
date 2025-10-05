from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from .predict_pm25 import predict_lung_health_5_years

app = FastAPI(title="Air Quality Prediction API")

# Allow requests from frontend (React/Three.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:5173"] if using Vite
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/predict")
def predict(location: str = Query(..., description="City, State (e.g. Chicago, IL)")):
    result = predict_lung_health_5_years(location=location, use_real_data=False)
    # normalize key name
    fev1 = result.get("fev1_prediction") or result.get("fev1")
    return {
        "location": location,
        "projected_capacity_percent": fev1["projected_capacity_percent"],
        "risk_level": fev1["risk_level"]
    }