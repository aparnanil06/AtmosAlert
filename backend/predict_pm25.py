"""
predict_pm25_timeseries.py

Forecast PM2.5 5 years ahead from historical data, then estimate FEV1 impact.
Users choose the location via CLI flag or interactive prompt.

Notes
- Expects PM2.5 in µg/m³ (not AQI).
- For demo only. RandomForest single-shot 5y prediction is not a true long-horizon forecast.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
from argparse import ArgumentParser
import warnings
warnings.filterwarnings('ignore')

# --- env ---
load_dotenv()
ELASTIC_URL = os.getenv("ELASTIC_URL")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY")

# --- data access ---

def fetch_historical_pm25_from_elastic(location_name: str, days_back=365) -> pd.DataFrame:
    """Fetch historical PM2.5 (µg/m³) from Elasticsearch for a location."""
    if not location_name:
        raise ValueError("location_name is required")

    try:
        es = Elasticsearch(ELASTIC_URL, api_key=ELASTIC_API_KEY)
        must = [
            {"term": {"pollutant": "pm25"}},
            {"range": {"@timestamp": {"gte": f"now-{days_back}d", "lte": "now"}}},
        ]
        # prefer keyword exact match when mapped
        must.append({"term": {"location_name.keyword": location_name}})
        query = {"bool": {"must": must}}

        resp = es.search(
            index="tempo-exposure",
            query=query,
            size=10000,
            sort=[{"@timestamp": "asc"}],
        )

        rows = []
        for hit in resp.get("hits", {}).get("hits", []):
            src = hit["_source"]
            val = src.get("pm25_ugm3") or src.get("value")
            if val is None:
                # do not guess from AQI
                continue
            rows.append(
                {
                    "timestamp": src["@timestamp"],
                    "pm25_value": float(val),
                    "location": src.get("location_name", location_name),
                }
            )
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.dropna(subset=["pm25_value"]).sort_values("timestamp")
        print(f"Fetched {len(df)} records for {location_name}")
        return df
    except Exception as e:
        print(f"Elasticsearch fetch error: {e}")
        return pd.DataFrame()


def generate_synthetic_historical_data(location: str, days=365) -> pd.DataFrame:
    """Synthetic daily PM2.5 for offline runs."""
    rng = np.random.default_rng(42)
    end = datetime.now()
    dates = [end - timedelta(days=i) for i in range(days, 0, -1)]
    base = 35
    seasonal = 15 * np.sin(np.linspace(0, 4 * np.pi, days) + np.pi / 2)
    trend = np.linspace(0, 5, days)
    noise = rng.normal(0, 8, days)
    weekly = np.array([5 if i % 7 < 5 else -3 for i in range(days)])
    pm = np.clip(base + seasonal + trend + noise + weekly, 5, 150)
    return pd.DataFrame({"timestamp": dates, "pm25_value": pm, "location": location})

# --- features ---

def create_time_series_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["year"] = df["timestamp"].dt.year
    df["month"] = df["timestamp"].dt.month
    df["day_of_year"] = df["timestamp"].dt.dayofyear
    df["day_of_week"] = df["timestamp"].dt.dayofweek
    df["week_of_year"] = df["timestamp"].dt.isocalendar().week.astype(int)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["day_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
    df["day_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)
    df["pm25_lag_1"] = df["pm25_value"].shift(1)
    df["pm25_lag_7"] = df["pm25_value"].shift(7)
    df["pm25_lag_30"] = df["pm25_value"].shift(30)
    df["pm25_rolling_7"] = df["pm25_value"].rolling(7, min_periods=1).mean()
    df["pm25_rolling_30"] = df["pm25_value"].rolling(30, min_periods=1).mean()
    df["pm25_rolling_std_7"] = df["pm25_value"].rolling(7, min_periods=1).std()
    df["days_since_start"] = (df["timestamp"] - df["timestamp"].min()).dt.days
    return df.dropna()

# --- model ---

def train_pm25_forecasting_model(df: pd.DataFrame):
    df_feat = create_time_series_features(df)
    feature_cols = [
        "year","month","day_of_year","day_of_week","week_of_year",
        "month_sin","month_cos","day_sin","day_cos",
        "pm25_lag_1","pm25_lag_7","pm25_lag_30",
        "pm25_rolling_7","pm25_rolling_30","pm25_rolling_std_7",
        "days_since_start",
    ]
    X = df_feat[feature_cols]
    y = df_feat["pm25_value"]
    split = int(len(X) * 0.8)
    Xtr, Xte = X[:split], X[split:]
    ytr, yte = y[:split], y[split:]
    model = RandomForestRegressor(
        n_estimators=100, max_depth=15, min_samples_split=5, min_samples_leaf=2,
        random_state=42, n_jobs=-1
    )
    model.fit(Xtr, ytr)
    yhat = model.predict(Xte)
    metrics = {
        "r2": r2_score(yte, yhat),
        "rmse": float(np.sqrt(mean_squared_error(yte, yhat))),
        "mae": float(mean_absolute_error(yte, yhat)),
    }
    return model, feature_cols, metrics

# --- single-shot 5y prediction (demo) ---

def predict_pm25_in_5_years(model, feature_cols, historical_df: pd.DataFrame, location: str):
    recent = historical_df.tail(90).copy()
    curr_mean = float(recent["pm25_value"].mean())
    curr_std = float(recent["pm25_value"].std())
    last_date = pd.to_datetime(recent["timestamp"].max())
    future_date = last_date + timedelta(days=5 * 365)

    row = pd.DataFrame([{
        "timestamp": future_date,
        "pm25_value": curr_mean,
        "location": location
    }])
    row["year"] = row["timestamp"].dt.year
    row["month"] = row["timestamp"].dt.month
    row["day_of_year"] = row["timestamp"].dt.dayofyear
    row["day_of_week"] = row["timestamp"].dt.dayofweek
    row["week_of_year"] = row["timestamp"].dt.isocalendar().week.astype(int)
    row["month_sin"] = np.sin(2 * np.pi * row["month"] / 12)
    row["month_cos"] = np.cos(2 * np.pi * row["month"] / 12)
    row["day_sin"] = np.sin(2 * np.pi * row["day_of_year"] / 365)
    row["day_cos"] = np.cos(2 * np.pi * row["day_of_year"] / 365)
    row["pm25_lag_1"] = recent["pm25_value"].iloc[-1]
    row["pm25_lag_7"] = recent["pm25_value"].tail(7).mean()
    row["pm25_lag_30"] = recent["pm25_value"].tail(30).mean()
    row["pm25_rolling_7"] = recent["pm25_value"].tail(7).mean()
    row["pm25_rolling_30"] = recent["pm25_value"].tail(30).mean()
    row["pm25_rolling_std_7"] = recent["pm25_value"].tail(7).std()
    first_date = pd.to_datetime(historical_df["timestamp"].min())
    row["days_since_start"] = (future_date - first_date).days

    pred = float(model.predict(row[feature_cols])[0])

    # trend stats (descriptive only)
    slope = np.polyfit(np.arange(len(recent)), recent["pm25_value"].values, 1)[0]
    annual_trend = float(slope * 365)
    five_year_trend = float(annual_trend * 5)

    return {
        "current_avg_pm25": round(curr_mean, 2),
        "predicted_pm25_5y": round(pred, 2),
        "prediction_date": future_date.strftime("%Y-%m-%d"),
        "current_date": last_date.strftime("%Y-%m-%d"),
        "annual_trend": round(annual_trend, 2),
        "five_year_trend": round(five_year_trend, 2),
        "location": location,
        "confidence_interval_low": round(pred - 1.96 * curr_std, 2),
        "confidence_interval_high": round(pred + 1.96 * curr_std, 2),
    }

# --- FEV1 mapping (demo) ---

def calculate_fev1_from_predicted_pm25(predicted_pm25: float):
    BASELINE_FEV1 = 4000.0
    NATURAL_DECLINE_RATE = 30.0
    pm25_impact_rate = (predicted_pm25 / 10.0) * 72.0
    non_linear = (predicted_pm25 / 35.0) ** 1.3 if predicted_pm25 > 35 else 1.0
    total_decline = NATURAL_DECLINE_RATE * 5 + pm25_impact_rate * non_linear
    projected = BASELINE_FEV1 - total_decline
    pct_capacity = projected / BASELINE_FEV1 * 100.0
    if pct_capacity < 70: risk = "Severe"
    elif pct_capacity < 80: risk = "High"
    elif pct_capacity < 90: risk = "Moderate"
    elif pct_capacity < 95: risk = "Low-Moderate"
    else: risk = "Low"
    return {
        "current_fev1": round(BASELINE_FEV1, 1),
        "projected_fev1": round(projected, 1),
        "current_capacity_percent": 100.0,
        "projected_capacity_percent": round(pct_capacity, 1),
        "capacity_loss_percent": round(100.0 - pct_capacity, 1),
        "total_decline_ml": round(total_decline, 1),
        "annual_decline_ml": round(total_decline / 5.0, 1),
        "risk_level": risk,
    }

# --- pipeline ---

def predict_lung_health_5_years(location: str, use_real_data=False, days_back=365):
    if not location:
        raise ValueError("Location is required")
    if use_real_data:
        hist = fetch_historical_pm25_from_elastic(location, days_back=days_back)
        if hist.empty:
            print("No real data. Falling back to synthetic.")
            hist = generate_synthetic_historical_data(location, days=days_back)
    else:
        hist = generate_synthetic_historical_data(location, days=days_back)

    model, feat_cols, metrics = train_pm25_forecasting_model(hist)
    pm25_pred = predict_pm25_in_5_years(model, feat_cols, hist, location)
    fev1_pred = calculate_fev1_from_predicted_pm25(pm25_pred["predicted_pm25_5y"])
    return {"location": location, "pm25": pm25_pred, "fev1": fev1_pred, "metrics": metrics}

# --- CLI ---

if __name__ == "__main__":
    ap = ArgumentParser(description="Predict PM2.5 in 5 years and estimate FEV1 impact.")
    ap.add_argument("--location", type=str, help='Location name, e.g. "Chicago, IL"')
    ap.add_argument("--real", action="store_true", help="Use Elasticsearch data")
    ap.add_argument("--days", type=int, default=365, help="Days of history to use")
    args = ap.parse_args()

    # Interactive prompt if no location passed
    location = args.location or input("Enter a location (e.g., 'Chicago, IL'): ").strip()
    if not location:
        raise SystemExit("No location provided. Exiting.")

    res = predict_lung_health_5_years(location=location, use_real_data=args.real, days_back=args.days)

    print("\n=== FINAL PREDICTION SUMMARY ===")
    print("Location:", res["location"])
    print("Current PM2.5 (avg recent):", res["pm25"]["current_avg_pm25"], "µg/m³")
    print("Predicted PM2.5 (5y):", res["pm25"]["predicted_pm25_5y"], "µg/m³")
    print("95% CI:", f"[{res['pm25']['confidence_interval_low']}, {res['pm25']['confidence_interval_high']}]")
    print("Projected FEV1 (5y):", res["fev1"]["projected_fev1"], "ml")
    print("Risk:", res["fev1"]["risk_level"])
