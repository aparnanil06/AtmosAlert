// src/components/LungVisualization.js
import React from "react";
import "./LungVisualization.css";

export default function LungVisualization({ projectedCapacityPercent = 85 }) {
  const pct = Math.max(0, Math.min(100, projectedCapacityPercent));
  const color =
    pct >= 95 ? "#10b981" : // green
    pct >= 90 ? "#84cc16" :
    pct >= 80 ? "#f59e0b" :
    pct >= 70 ? "#f97316" : "#ef4444";
  const opacity = Math.max(0.15, pct / 100); // keep visible even when low

  return (
    <div className="lung-visualization">
      <svg width="360" height="260" viewBox="0 0 360 260" style={{ display: "block" }}>
        {/* left lung */}
        <path
          d="M160,120 C120,60 85,80 80,130 C75,185 110,230 155,235 C175,237 180,210 180,190 C180,160 175,140 160,120 Z"
          fill={color}
          opacity={opacity}
          style={{ filter: "drop-shadow(0 8px 18px rgba(0,0,0,0.25))" }}
        />
        {/* right lung */}
        <path
          d="M200,120 C240,60 275,80 280,130 C285,185 250,230 205,235 C185,237 180,210 180,190 C180,160 185,140 200,120 Z"
          fill={color}
          opacity={opacity}
          style={{ filter: "drop-shadow(0 8px 18px rgba(0,0,0,0.25))" }}
        />
      </svg>
    </div>
  );
}
