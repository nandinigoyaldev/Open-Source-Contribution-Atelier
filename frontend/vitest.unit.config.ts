import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";



export default defineConfig({
  plugins: [react()],
  resolve: {
    dedupe: ["react", "react-dom", "react-i18next"],
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.unit.ts",
    include: ["src/test/**/*.test.{ts,tsx}"],
  },
});
