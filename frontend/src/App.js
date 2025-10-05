// src/App.js
import React, { useState } from 'react';
import './App.css';
import SearchBar from './components/SearchBar';
import AQIDisplay from './components/AQIDisplay';
import LungVisualization from './components/LungVisualization';
import PollutantTable from './components/PollutantTable';
import AlertSignup from './components/AlertSignup';

function App() {
  const [aqiData, setAqiData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fev1Data, setFev1Data] = useState(null);

  const handleSearch = async (location) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`http://localhost:8090/api/aqi?address=${encodeURIComponent(location)}`);
      
      if (!response.ok) {
        throw new Error('Failed to fetch air quality data');
      }
      
      const data = await response.json();
      setAqiData(data);
      // FEV1 5-year projection
try {
  const resp = await fetch(
    `http://127.0.0.1:8000/api/predict?location=${encodeURIComponent(location)}`
  );

  // Read raw text first so we can surface backend errors that aren’t JSON
  const text = await resp.text();
  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${text.slice(0,200)}`);
  }

  // Parse JSON safely
  let fev1;
  try {
    fev1 = JSON.parse(text);
  } catch {
    throw new Error(`Invalid JSON from API: ${text.slice(0,200)}`);
  }

  // Expect { projected_capacity_percent, risk_level, location }
  if (typeof fev1.projected_capacity_percent !== "number") {
    throw new Error("API missing projected_capacity_percent");
  }

  setFev1Data(fev1);
} catch (e) {
  console.error("FEV1 fetch failed:", e);
  setFev1Data(null);
  // optional: setError(String(e));
}
    } catch (err) {
      setError(err.message);
      setAqiData(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>AtmosAlert</h1>
        <p className="tagline">Real-time Air Quality Monitoring & Alerts</p>
      </header>

      <main className="container">
        <SearchBar onSearch={handleSearch} loading={loading} />

        {error && (
          <div className="error-message">
            <p>{error}</p>
          </div>
        )}

        {loading && (
          <div className="loading">
            <div className="spinner"></div>
            <p>Fetching air quality data...</p>
          </div>
        )}

        {aqiData && !loading && (
          <div className="content-grid">
            <div className="left-column">
              <AQIDisplay data={aqiData} />
              <PollutantTable pollutants={aqiData.rows} />
              <AlertSignup location={aqiData.area_name} />
            </div>
            
            <div className="right-column">
              <div className="visualization-section">
                <h2>Long-term Exposure Impact</h2>
                {fev1Data ? (
                  <LungVisualization projectedCapacityPercent={fev1Data.projected_capacity_percent} />
                ) : (
                  <div style={{ height: 260 }} />  // optional spacer/skeleton
                )}
              </div>
            </div>
          </div>
        )}

        {!aqiData && !loading && !error && (
          <div className="welcome-message">
            <h2>Welcome to AtmosAlert</h2>
            <p>Enter your location above to check air quality and sign up for alerts</p>
            <div className="info-cards">
              <div className="info-card">
                <h3>Real-time AQI</h3>
                <p>Get current air quality index for any US location</p>
              </div>
              <div className="info-card">
                <h3>Health Guidance</h3>
                <p>Receive personalized recommendations based on air quality</p>
              </div>
              <div className="info-card">
                <h3>Email Alerts</h3>
                <p>Get notified when air quality becomes unhealthy</p>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="App-footer">
        <p>Data provided by EPA AirNow | AtmosAlert 2025</p>
      </footer>
    </div>
  );
}

export default App;