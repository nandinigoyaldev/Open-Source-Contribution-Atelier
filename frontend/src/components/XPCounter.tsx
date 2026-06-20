import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// Define the expected prop types
interface XPCounterProps {
  xp?: number;
}

const XPCounter: React.FC<XPCounterProps> = ({ xp = 0 }) => {
  return (
    <div className="flex items-center gap-3 bg-gray-900 px-5 py-3 rounded-2xl border border-gray-800 shadow-2xl w-fit">
      <span className="text-sm font-bold tracking-widest text-gray-400 uppercase">
        XP
      </span>
      
      {/* The container acts as a fixed 'window' for the animation */}
      <div className="relative h-10 w-20 overflow-hidden text-3xl font-black text-emerald-400 drop-shadow-[0_0_10px_rgba(16,185,129,0.5)]">
        <AnimatePresence mode="popLayout">
          <motion.div
            key={xp} // Changing the key triggers the unmount/mount animation
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: -40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 400, damping: 35 }}
            className="absolute inset-0 flex items-center tabular-nums"
          >
            {xp}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
};

export default XPCounter;