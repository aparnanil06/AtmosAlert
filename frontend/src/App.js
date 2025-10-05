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
                <LungVisualization 
                  exposureScore={aqiData.exposure} 
                  aqi={aqiData.overall_aqi}
                />
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