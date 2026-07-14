import React from "react";

interface StreakFlameProps {
  animate?: boolean;
  className?: string;
}

export function StreakFlame({
  animate = false,
  className = "",
}: StreakFlameProps) {
  return (
    <div
      className={[
        "relative inline-flex items-center justify-center",
        className,
      ].join(" ")}
      aria-hidden="true"
    >
      {/* Glow layer (kept small + uses opacity/transform only) */}
      <div
        className={
          animate
            ? "streak-flame-glow"
            : "streak-flame-glow streak-flame-glow--static"
        }
      />

      {/* SVG flame */}
      <svg
        width="54"
        height="54"
        viewBox="0 0 64 64"
        className={animate ? "streak-flame streak-flame--anim" : "streak-flame"}
        role="img"
        focusable="false"
        style={{ color: "var(--flame-fg, #ff7a18)" }}
      >
        <defs>
          <linearGradient id="streakFlameGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="1" />
            <stop offset="45%" stopColor="#ffcc33" stopOpacity="1" />
            <stop offset="100%" stopColor="#ff3b30" stopOpacity="1" />
          </linearGradient>

          {/* Subtle inner highlight gradient */}
          <linearGradient id="streakFlameHi" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#fff2c2" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#ffffff" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Flame shape */}
        <path
          d="M32 6c1.6 10.3-4.2 14.8-8.2 19.6C19.7 31.4 19 37.2 21.2 42.4c2.2 5.2 7.2 10.6 10.8 15.6 0.7 1 1.4 1 2.1 0 3.6-5 8.6-10.4 10.8-15.6 2.2-5.2 1.5-11-2.6-16.8C36.2 20.8 30.4 16.3 32 6z"
          fill="url(#streakFlameGrad)"
          stroke="rgba(0,0,0,0.35)"
          strokeWidth="1"
          strokeLinejoin="round"
        />

        {/* Inner highlight */}
        <path
          d="M32.2 12.5c1.1 7.4-3.3 10.8-6.3 14.5-3.1 3.8-3.6 8.2-1.9 12.1 1.7 3.9 5.4 7.8 8.2 11.9 0.4 0.6 0.9 0.6 1.3 0 2.8-4.1 6.5-8 8.2-11.9 1.7-3.9 1.2-8.3-1.9-12.1-3-3.7-7.4-7.1-6.6-14.5z"
          fill="url(#streakFlameHi)"
          opacity="0.75"
        />

        {/* Outer ember specks (tiny, low cost) */}
        <circle cx="22" cy="39" r="1.3" fill="#ffd45a" opacity="0.9" />
        <circle cx="42" cy="34" r="1.1" fill="#ffd45a" opacity="0.8" />
        <circle cx="31" cy="46" r="1.0" fill="#ffd45a" opacity="0.7" />
      </svg>
    </div>
  );
}
