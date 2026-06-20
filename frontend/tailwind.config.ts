import type { Config } from "tailwindcss";

export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        surface: "#FFF9F0",
        "surface-lowest": "#FFFFFF",
        "surface-low": "#FFEBC2",
        "surface-high": "#FFD580",
        "surface-highest": "#FFAA00",
        primary: "#FF3B30",
        "primary-container": "#FFC0B3",
        tertiary: "#FF9500",
        accent: "#FFCC00",
        outline: "#000000",
        text: "#1F1A15",
        muted: "#6B5A49",
      },
      fontFamily: {
        display: ["Outfit", "Inter", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      boxShadow: {
        card: "4px 4px 0px 0px rgba(0, 0, 0, 1)",
        "card-lg": "8px 8px 0px 0px rgba(0, 0, 0, 1)",
        "card-sm": "2px 2px 0px 0px rgba(0, 0, 0, 1)",
        gel: "0px 8px 0px 0px rgba(230, 40, 20, 1), 0px -4px 0px 0px rgba(255,100,80,1) inset",
      },
      scale: {
        "102": "1.02",
      },
      keyframes: {
        shake: {
          "0%": { transform: "translateX(0)" },
          "10%, 30%, 50%, 70%, 90%": { transform: "translateX(-8px)" },
          "20%, 40%, 60%, 80%": { transform: "translateX(8px)" },
          "100%": { transform: "translateX(0)" },
        },
        flash: {
          "0%": { backgroundColor: "transparent" },
          "50%": { backgroundColor: "rgba(255, 0, 0, 0.06)" }, // subtle red flash for errors
          "100%": { backgroundColor: "transparent" },
        },
      },
      animation: {
        shake: "shake 600ms cubic-bezier(.36,.07,.19,.97)",
        flash: "flash 350ms ease-in-out",
      },
    },
  },
  plugins: [],
} satisfies Config;
