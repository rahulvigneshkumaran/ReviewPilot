"use client";

import React from "react";

interface RiskMeterProps {
  score: number;
}

export default function RiskMeter({ score }: RiskMeterProps) {
  // Normalize score between 0 and 100
  const normalizedScore = Math.max(0, Math.min(100, score));
  
  // Calculate needle angle rotation (speedometer arc from -90deg to +90deg)
  const angle = (normalizedScore / 100) * 180 - 90;

  // Determine category color classes
  let colorClass = "text-green-400";
  let bgClass = "bg-green-500/10 border-green-500/20";
  let label = "LOW";

  if (normalizedScore > 75) {
    colorClass = "text-red-500";
    bgClass = "bg-red-500/10 border-red-500/20";
    label = "CRITICAL";
  } else if (normalizedScore > 50) {
    colorClass = "text-orange-500";
    bgClass = "bg-orange-500/10 border-orange-500/20";
    label = "HIGH";
  } else if (normalizedScore > 25) {
    colorClass = "text-yellow-500";
    bgClass = "bg-yellow-500/10 border-yellow-500/20";
    label = "MEDIUM";
  }

  return (
    <div className="flex flex-col items-center justify-center p-6 bg-card border border-border/40 rounded-xl relative overflow-hidden">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-textSecondary mb-4">Pull Request Risk</h4>
      
      {/* Speedometer Arc Wrapper */}
      <div className="relative w-48 h-24 flex items-center justify-center">
        {/* SVG speedometer base arc */}
        <svg className="absolute top-0 left-0 w-full h-full" viewBox="0 0 100 50">
          {/* Base Arc track */}
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="#1E293B"
            strokeWidth="8"
            strokeLinecap="round"
          />
          {/* Colored gradient overlay */}
          <path
            d="M 10 50 A 40 40 0 0 1 90 50"
            fill="none"
            stroke="url(#riskGradient)"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray="125.6"
            strokeDashoffset={125.6 - (normalizedScore / 100) * 125.6}
          />
          <defs>
            <linearGradient id="riskGradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#4ADE80" />   {/* Green */}
              <stop offset="40%" stopColor="#FACC15" />  {/* Yellow */}
              <stop offset="75%" stopColor="#F97316" />  {/* Orange */}
              <stop offset="100%" stopColor="#EF4444" /> {/* Red */}
            </linearGradient>
          </defs>
        </svg>

        {/* Speedometer Needle */}
        <div
          className="absolute bottom-0 left-[calc(50%-2px)] w-1 h-16 origin-bottom rounded-full bg-white shadow-lg transition-transform duration-1000 ease-out"
          style={{ transform: `rotate(${angle}deg)` }}
        >
          <div className="absolute top-0 left-[-3px] w-2.5 h-2.5 rounded-full bg-white shadow"></div>
        </div>

        {/* Center hub */}
        <div className="absolute bottom-0 w-4 h-2 bg-white rounded-t-full"></div>
      </div>

      {/* Visual score values */}
      <div className="text-center mt-3 z-10">
        <span className="font-outfit text-3xl font-extrabold text-textPrimary">{normalizedScore}</span>
        <span className="text-xs text-textSecondary">/100</span>
        <div className={`mt-1.5 text-xs font-bold px-3 py-0.5 rounded-full border ${bgClass} ${colorClass}`}>
          {label} RISK
        </div>
      </div>
    </div>
  );
}
