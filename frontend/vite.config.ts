import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";
import { fileURLToPath } from "node:url";
import process from "node:process";
import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";

const dirname = typeof __dirname !== "undefined"
  ? __dirname
  : path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  worker: {
    format: "es",
  },
  base: process.env.VITE_CDN_URL || "/",
  plugins: [
    react(),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      registerType: "autoUpdate",
      injectManifest: {
        globPatterns: ["**/*.{js,css,html,ico,png,svg,json,md}"],
        maximumFileSizeToCacheInBytes: 7 * 1024 * 1024,
      },
      manifest: {
        name: "Contribution Atelier",
        short_name: "Atelier",
        theme_color: "#ffffff",
        display: "standalone",
      },
      devOptions: {
        enabled: true,
        type: "module",
      },
    }),
    storybookTest({
      configDir: path.join(dirname, ".storybook"),
    }),
  ],
  resolve: {
    dedupe: ["react", "react-dom", "react-i18next"],
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          environment: "jsdom",
          setupFiles: "./src/test/setup.ts",
          include: ["src/test/**/*.test.{ts,tsx}"],
          exclude: ["**/*.stories.{ts,tsx}", "**/*.stories.{js,jsx}"],
        },
      },
      {
        extends: true,
        test: {
          name: "storybook",
          browser: {
            enabled: true,
            headless: true,
            provider: "playwright",
            instances: [{ browser: "chromium" }],
          },
        },
      },
    ],
    optimizeDeps: {
      include: ["workbox-precaching", "workbox-routing", "workbox-strategies", "workbox-expiration"],
    },
  },
} as any);
