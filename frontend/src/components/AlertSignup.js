// src/components/AlertSignup.js
import React, { useState } from 'react';
import './AlertSignup.css';

function AlertSignup({ location }) {
  const [email, setEmail] = useState('');
  const [threshold, setThreshold] = useState(100);
  const [status, setStatus] = useState({ type: '', message: '' });
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setStatus({ type: '', message: '' });

    try {
      // Note: You'll need to add this endpoint to your backend
      const response = await fetch('http://localhost:8090/api/subscribe', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          location: location || 'Unknown',
          threshold
        })
      });

      if (response.ok) {
        setStatus({
          type: 'success',
          message: '✓ Successfully signed up for alerts!'
        });
        setEmail('');
      } else {
        setStatus({
          type: 'error',
          message: 'Failed to sign up. Please try again.'
        });
      }
    } catch (error) {
      setStatus({
        type: 'error',
        message: 'Error connecting to server. Please try again later.'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="alert-signup">
      <h2>Get Air Quality Alerts</h2>
      <p className="subtitle">
        Receive email notifications when air quality becomes unhealthy
      </p>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="email">Email Address</label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your.email@example.com"
            required
            disabled={loading}
          />
        </div>

        <div className="form-group">
          <label htmlFor="threshold">
            Alert Threshold (AQI)
            <span className="threshold-value">{threshold}</span>
          </label>
          <input
            type="range"
            id="threshold"
            min="50"
            max="200"
            step="10"
            value={threshold}
            onChange={(e) => setThreshold(Number(e.target.value))}
            disabled={loading}
          />
          <div className="threshold-labels">
            <span>50 (Moderate)</span>
            <span>200 (Unhealthy)</span>
          </div>
        </div>

        <button type="submit" className="signup-button" disabled={loading}>
          {loading ? 'Signing up...' : 'Sign Up for Alerts'}
        </button>

        {status.message && (
          <div className={`status-message ${status.type}`}>
            {status.message}
          </div>
        )}
      </form>
    </div>
  );
}

export default AlertSignup;