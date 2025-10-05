// src/components/PollutantTable.js
import React from 'react';
import './PollutantTable.css';

function PollutantTable({ pollutants }) {
  const getAQIColor = (aqi) => {
    if (aqi === null) return '#999';
    if (aqi <= 50) return '#00e400';
    if (aqi <= 100) return '#fbbf24';
    if (aqi <= 150) return '#ff7e00';
    if (aqi <= 200) return '#ff0000';
    if (aqi <= 300) return '#8f3f97';
    return '#7e0023';
  };

  const getPollutantName = (code) => {
    const names = {
      'pm25': 'PM2.5 (Fine Particles)',
      'pm10': 'PM10 (Coarse Particles)',
      'o3': 'Ozone (O₃)',
      'no2': 'Nitrogen Dioxide (NO₂)',
      'co': 'Carbon Monoxide (CO)',
      'so2': 'Sulfur Dioxide (SO₂)'
    };
    return names[code] || code.toUpperCase();
  };

  if (!pollutants || pollutants.length === 0) {
    return null;
  }

  return (
    <div className="pollutant-table">
      <h2>Pollutant Breakdown</h2>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Pollutant</th>
              <th>AQI</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {pollutants.map((pollutant, index) => (
              <tr key={index}>
                <td className="pollutant-name">
                  {getPollutantName(pollutant.pollutant)}
                </td>
                <td className="aqi-value">
                  {pollutant.latest_aqi !== null ? pollutant.latest_aqi : 'N/A'}
                </td>
                <td>
                  <span 
                    className="status-badge"
                    style={{ 
                      background: getAQIColor(pollutant.latest_aqi),
                      color: pollutant.latest_aqi > 50 && pollutant.latest_aqi <= 100 ? '#333' : 'white'
                    }}
                  >
                    {pollutant.latest_aqi <= 50 ? 'Good' :
                     pollutant.latest_aqi <= 100 ? 'Moderate' :
                     pollutant.latest_aqi <= 150 ? 'Unhealthy (Sensitive)' :
                     pollutant.latest_aqi <= 200 ? 'Unhealthy' :
                     pollutant.latest_aqi <= 300 ? 'Very Unhealthy' : 'Hazardous'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default PollutantTable;