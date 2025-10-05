from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .predict_pm25 import predict_lung_health_5_years

app = FastAPI(title="Air Quality Prediction API")

# Allow requests from frontend (React/Three.js)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173","http://localhost:5173","*"],  # or ["http://localhost:5173"] if using Vite
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/predict")
def predict(location: str = Query(..., description="City, State")):
    try:
        res = predict_lung_health_5_years(location=location, use_real_data=False)
        fev1 = res["fev1"]  # from your return shape
        pct = fev1.get("projected_capacity_percent")
        if pct is None and "capacity_loss_percent" in fev1:
            pct = 100.0 - float(fev1["capacity_loss_percent"])
        if pct is None and {"projected_fev1","current_fev1"} <= fev1.keys():
            pct = 100.0 * float(fev1["projected_fev1"]) / float(fev1["current_fev1"])
        if pct is None:
            raise KeyError("projected_capacity_percent missing in fev1")

        return {
            "location": res["location"],
            "projected_capacity_percent": float(pct),
            "risk_level": fev1.get("risk_level", "Unknown"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"prediction failed: {e}")