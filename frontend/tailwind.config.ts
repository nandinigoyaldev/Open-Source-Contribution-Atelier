import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{js,jsx,ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        light: {
          bg: "#ffffff",
          text: "#111827",
          card: "#f9fafb",
          border: "#e5e7eb",
          primary: "#7c3aed",
          secondary: "#6b7280",
          muted: "#9ca3af",
        },
        dark: {
          bg: "#0f172a",
          text: "#f3f4f6",
          card: "#1e293b",
          border: "#334155",
          primary: "#8b5cf6",
          secondary: "#9ca3af",
          muted: "#64748b",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
