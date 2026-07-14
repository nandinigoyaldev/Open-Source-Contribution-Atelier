import React, { useEffect, useState } from "react";
import "./ProgressRing.css";

interface ProgressRingPops {
  percentage: number;
  size?: number;
  color?: string;
  label?: string;
}

export function ProgressRing({
  percentage,
  size = 80,
  color = "#6c63ff",
  label,
}: ProgressRingPops) {
  const strokeWidth = 8;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (percentage / 100) * circumference;

  return (
    <div className="progress-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size}>
        <circle
          className="progress-ring__base"
          stroke="#e6e6e6"
          strokeWidth={strokeWidth}
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          className="progress-ring__progress"
          stroke={color}
          strokeWidth={strokeWidth}
          fill="transparent"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          r={radius}
          cx={size / 2}
          cy={size / 2}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      {label && <div className="progress-ring__label">{label}</div>}
    </div>
  );
}
