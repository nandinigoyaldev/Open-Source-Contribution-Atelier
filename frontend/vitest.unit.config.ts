import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dirname = typeof __dirname !== "undefined"
  ? __dirname
  : path.dirname(fileURLToPath(import.meta.url));

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
