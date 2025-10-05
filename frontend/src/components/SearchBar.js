// src/components/SearchBar.js
import React, { useState } from 'react';
import './SearchBar.css';

function SearchBar({ onSearch, loading }) {
  const [location, setLocation] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (location.trim()) {
      onSearch(location);
    }
  };

  return (
    <div className="search-bar">
      <form onSubmit={handleSubmit}>
        <div className="search-input-group">
          <input
            type="text"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            placeholder="Enter ZIP code, city, or address..."
            className="search-input"
            disabled={loading}
          />
          <button 
            type="submit" 
            className="search-button"
            disabled={loading || !location.trim()}
          >
            {loading ? 'Searching...' : 'Check Air Quality'}
          </button>
        </div>
      </form>
      <p className="search-hint">Try: "Chicago", "90210", or "New York, NY"</p>
    </div>
  );
}

export default SearchBar;