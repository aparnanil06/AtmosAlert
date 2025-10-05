// src/components/LungVisualization.js
import React from 'react';
import './LungVisualization.css';

function LungVisualization({ exposureScore, aqi }) {
  return (
    <div className="lung-visualization">
      <div className="placeholder-content">
        <div className="placeholder-box">
          <h3>🫁 Lung Visualization</h3>
          <p>Your partner's visualization component will go here</p>
          <div className="data-preview">
            <p><strong>Exposure Score:</strong> {exposureScore?.score || 0}</p>
            <p><strong>Current AQI:</strong> {aqi || 'N/A'}</p>
          </div>
          <p className="instruction">
            Replace this component with your partner's lung visualization.
            The component receives <code>exposureScore</code> and <code>aqi</code> as props.
          </p>
        </div>
      </div>
    </div>
  );
}

export default LungVisualization;