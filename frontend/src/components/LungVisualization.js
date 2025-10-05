// src/components/LungVisualization.js
import React from "react";
import "./LungVisualization.css";

export default function LungVisualization({ projectedCapacityPercent = 85 }) {
  const pct = Math.max(0, Math.min(100, projectedCapacityPercent));
  
  // More dramatic color changes with wider bands
  const color =
    pct >= 98 ? "#10b981" :  // green (98-100%)
    pct >= 95 ? "#84cc16" :  // lime (95-98%)
    pct >= 90 ? "#fbbf24" :  // yellow (90-95%)
    pct >= 85 ? "#f59e0b" :  // amber (85-90%)
    pct >= 80 ? "#f97316" :  // orange (80-85%)
    pct >= 70 ? "#ef4444" :  // red (70-80%)
    "#dc2626";               // dark red (<70%)
  
  // Keep opacity fairly high so lungs are visible
  const opacity = Math.max(0.75, pct / 100);
  
  return (
    <div className="lung-visualization">
      <svg width="400" height="350" viewBox="0 0 400 350" style={{ display: "block", margin: "0 auto" }}>
        <defs>
          {/* Gradient for depth */}
          <radialGradient id="lungGradient" cx="30%" cy="30%">
            <stop offset="0%" stopColor={color} stopOpacity={opacity} />
            <stop offset="100%" stopColor={color} stopOpacity={Math.max(0.5, opacity - 0.3)} />
          </radialGradient>
          
          {/* Texture pattern for lung tissue */}
          <pattern id="lungTexture" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
            <circle cx="5" cy="5" r="1.5" fill={color} opacity="0.15" />
            <circle cx="15" cy="12" r="1.5" fill={color} opacity="0.12" />
            <circle cx="10" cy="15" r="1" fill={color} opacity="0.1" />
          </pattern>
        </defs>
        
        {/* Trachea */}
        <rect x="195" y="30" width="12" height="50" fill="#e5e7eb" opacity="0.8" rx="6" />
        
        {/* Left bronchus */}
        <path 
          d="M200,80 Q180,100 165,120" 
          stroke="#d1d5db" 
          strokeWidth="8" 
          fill="none" 
          opacity="0.7"
        />
        
        {/* Right bronchus */}
        <path 
          d="M202,80 Q220,100 235,120" 
          stroke="#d1d5db" 
          strokeWidth="8" 
          fill="none" 
          opacity="0.7"
        />
        
        {/* Left lung with gradient and texture */}
        <g>
          <path
            d="M165,120 C135,100 95,115 80,160 C68,205 85,265 125,290 C150,305 175,288 185,265 C193,245 190,205 183,170 C179,145 173,135 165,120 Z"
            fill="url(#lungGradient)"
            style={{ 
              filter: "drop-shadow(0 12px 30px rgba(0,0,0,0.3))",
              transition: "all 0.5s ease"
            }}
          />
          <path
            d="M165,120 C135,100 95,115 80,160 C68,205 85,265 125,290 C150,305 175,288 185,265 C193,245 190,205 183,170 C179,145 173,135 165,120 Z"
            fill="url(#lungTexture)"
          />
          {/* Lobes separation lines */}
          <path 
            d="M155,155 Q140,180 130,215" 
            stroke={color} 
            strokeWidth="2" 
            fill="none" 
            opacity="0.3"
          />
          <path 
            d="M168,175 Q160,200 155,230" 
            stroke={color} 
            strokeWidth="2" 
            fill="none" 
            opacity="0.3"
          />
        </g>
        
        {/* Right lung with gradient and texture */}
        <g>
          <path
            d="M235,120 C265,100 305,115 320,160 C332,205 315,265 275,290 C250,305 225,288 215,265 C207,245 210,205 217,170 C221,145 227,135 235,120 Z"
            fill="url(#lungGradient)"
            style={{ 
              filter: "drop-shadow(0 12px 30px rgba(0,0,0,0.3))",
              transition: "all 0.5s ease"
            }}
          />
          <path
            d="M235,120 C265,100 305,115 320,160 C332,205 315,265 275,290 C250,305 225,288 215,265 C207,245 210,205 217,170 C221,145 227,135 235,120 Z"
            fill="url(#lungTexture)"
          />
          {/* Lobes separation lines */}
          <path 
            d="M245,155 Q260,180 270,215" 
            stroke={color} 
            strokeWidth="2" 
            fill="none" 
            opacity="0.3"
          />
          <path 
            d="M232,175 Q240,200 245,230" 
            stroke={color} 
            strokeWidth="2" 
            fill="none" 
            opacity="0.3"
          />
          <path 
            d="M250,185 Q255,205 260,235" 
            stroke={color} 
            strokeWidth="2" 
            fill="none" 
            opacity="0.3"
          />
        </g>
        
        {/* Small bronchioles (branching) */}
        <g opacity="0.4">
          <path d="M165,130 L150,150 M150,150 L140,165 M150,150 L155,168" stroke={color} strokeWidth="2.5" fill="none" />
          <path d="M178,145 L170,165 M170,165 L160,180 M170,165 L175,185" stroke={color} strokeWidth="2.5" fill="none" />
          <path d="M235,130 L250,150 M250,150 L260,165 M250,150 L245,168" stroke={color} strokeWidth="2.5" fill="none" />
          <path d="M222,145 L230,165 M230,165 L240,180 M230,165 L225,185" stroke={color} strokeWidth="2.5" fill="none" />
        </g>
      </svg>
      
      <div style={{ textAlign: "center", marginTop: "20px" }}>
        <div style={{ fontSize: "36px", fontWeight: "bold", color: color }}>
          {pct.toFixed(1)}%
        </div>
        <div style={{ fontSize: "15px", color: "#666", marginTop: "5px" }}>
          Projected Lung Capacity (5 years)
        </div>
        <div style={{ fontSize: "14px", color: "#666", marginTop: "8px", fontStyle: "italic" }}>
          {pct >= 98 && "Excellent lung health expected"}
          {pct >= 95 && pct < 98 && "Very good lung health with minimal impact"}
          {pct >= 90 && pct < 95 && "Good lung health with minor reduction"}
          {pct >= 85 && pct < 90 && "Moderate impact on lung capacity"}
          {pct >= 80 && pct < 85 && "Noticeable lung capacity reduction"}
          {pct >= 70 && pct < 80 && "Significant lung impact expected"}
          {pct < 70 && "Major lung capacity reduction expected"}
        </div>
      </div>
    </div>
  );
}