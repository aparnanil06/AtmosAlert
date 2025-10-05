// src/components/AQIDisplay.js
import React from 'react';
import './AQIDisplay.css';

function AQIDisplay({ data }) {
  const getAQIColor = (aqi) => {
    if (aqi === null) return '#999';
    if (aqi <= 50) return '#00e400';
    if (aqi <= 100) return '#ffff00';
    if (aqi <= 150) return '#ff7e00';
    if (aqi <= 200) return '#ff0000';
    if (aqi <= 300) return '#8f3f97';
    return '#7e0023';
  };

  const aqi = data.overall_aqi;
  const category = data.overall_category;

  return (
    <div className="aqi-display">
      <div className="aqi-header">
        <h2>Air Quality in {data.area_name || 'Your Location'}</h2>
      </div>
      
      <div className="aqi-main">
        <div 
          className="aqi-circle" 
          style={{ 
            background: `linear-gradient(135deg, ${getAQIColor(aqi)}, ${getAQIColor(aqi)}dd)`
          }}
        >
          <div className="aqi-value">
            {aqi !== null ? aqi : 'N/A'}
          </div>
          <div className="aqi-label">AQI</div>
        </div>

        <div className="aqi-info">
          <div 
            className="aqi-category"
            style={{ color: getAQIColor(aqi) }}
          >
            {category.label}
          </div>
          <p className="aqi-message">{category.message}</p>
        </div>
      </div>

      <div className="aqi-scale">
        <div className="scale-item" style={{background: '#00e400'}}>
          <span>0-50</span>
          <small>Good</small>
        </div>
        <div className="scale-item" style={{background: '#ffff00', color: '#333'}}>
          <span>51-100</span>
          <small>Moderate</small>
        </div>
        <div className="scale-item" style={{background: '#ff7e00'}}>
          <span>101-150</span>
          <small>Unhealthy for Sensitive</small>
        </div>
        <div className="scale-item" style={{background: '#ff0000'}}>
          <span>151-200</span>
          <small>Unhealthy</small>
        </div>
        <div className="scale-item" style={{background: '#8f3f97'}}>
          <span>201-300</span>
          <small>Very Unhealthy</small>
        </div>
        <div className="scale-item" style={{background: '#7e0023'}}>
          <span>301+</span>
          <small>Hazardous</small>
        </div>
      </div>
    </div>
  );
}

export default AQIDisplay;