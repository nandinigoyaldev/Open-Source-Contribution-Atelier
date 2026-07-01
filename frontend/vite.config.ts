/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { storybookTest } from '@storybook/addon-vitest/vitest-plugin';
const dirname = typeof __dirname !== 'undefined' ? __dirname : path.dirname(fileURLToPath(import.meta.url));

// More info at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon
export default defineConfig({
 feat/app-fully-accessible
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
  ],
  resolve: {
    dedupe: ["react", "react-dom", "react-i18next"],
  },

  plugins: [react()],
main
  test: {
    workspace: [{
      extends: true,
      test: {
        environment: "jsdom",
        setupFiles: "./src/test/setup.ts"
      }
    }, {
      extends: true,
      plugins: [
      // The plugin will run tests for the stories defined in your Storybook config
      // See options at: https://storybook.js.org/docs/next/writing-tests/integrations/vitest-addon#storybooktest
      storybookTest({
        configDir: path.join(dirname, '.storybook')
      })],
      test: {
        name: 'storybook',
        browser: {
          enabled: true,
          headless: true,
          provider: 'playwright',
          instances: [{
            browser: 'chromium'
          }]
        }
      }
    }]
  }
});
