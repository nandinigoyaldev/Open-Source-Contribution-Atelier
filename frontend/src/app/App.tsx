import React, { useState } from 'react';
import XPCounter from '../components/XPCounter'; // Adjust path if needed

export default function App() {
  // Temporary state to test the animation
  const [currentXP, setCurrentXP] = useState(1250);

  return (
    <div className="min-h-screen bg-gray-950 p-10 flex flex-col items-center gap-8">
      <h1 className="text-2xl font-bold text-white">Issue #120: XP Ticker Test</h1>
      
      {/* 1. Render the component and pass the state */}
      <XPCounter xp={currentXP} />

      {/* 2. A button to trigger the XP gain */}
      <button 
        onClick={() => setCurrentXP(prev => prev + 50)}
        className="px-6 py-2 bg-emerald-600 text-white font-bold rounded-lg hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-600/20"
      >
        Simulate +50 XP Gain
      </button>
    </div>
  );
}