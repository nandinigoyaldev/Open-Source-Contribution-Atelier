import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";
import process from "node:process";
import { storybookTest } from "@storybook/addon-vitest/vitest-plugin";
import viteCompression from "vite-plugin-compression";
import { visualizer } from "rollup-plugin-visualizer";
import zlib from "node:zlib";
import postcss from "postcss";

const dirname =
  typeof __dirname !== "undefined"
    ? __dirname
    : path.dirname(fileURLToPath(import.meta.url));

function visualizerThresholdPlugin(maxGzipKB = 250): Plugin {
  return {
    name: "visualizer-threshold-check",
    apply: "build",
    generateBundle(_, bundle) {
      for (const [fileName, chunk] of Object.entries(bundle)) {
        if (chunk.type === "chunk" && fileName.endsWith(".js")) {
          const gzipped = zlib.gzipSync(Buffer.from(chunk.code));
          const gzipKB = gzipped.length / 1024;
          if (gzipKB > maxGzipKB) {
            this.error(
              `Chunk "${fileName}" (${gzipKB.toFixed(1)} KB gzipped) exceeds the maximum allowed threshold of ${maxGzipKB} KB gzipped.`,
            );
          }
        }
      }
    },
  };
}

function buildMetadataPlugin(): Plugin {
  return {
    name: "build-metadata",
    apply: "build",
    generateBundle() {
      const metadata = {
        version: process.env.VERCEL_GIT_COMMIT_SHA || Date.now().toString(36),
        builtAt: new Date().toISOString(),
      };
      this.emitFile({
        type: "asset",
        fileName: "build-metadata.json",
        source: JSON.stringify(metadata, null, 2),
      });
    },
  };
}

function cssRouteSplittingPlugin(): Plugin {
  return {
    name: "css-route-splitting-pipeline",
    apply: "build",
    enforce: "post",
    generateBundle(_, bundle) {
      const entryCssKey = Object.keys(bundle)
        .filter((key) => key.endsWith(".css") && bundle[key].type === "asset")
        .sort(
          (a, b) =>
            (bundle[b] as any).source.length - (bundle[a] as any).source.length,
        )[0];
      if (!entryCssKey) return;

      const mainCssAsset = bundle[entryCssKey];
      if (mainCssAsset.type !== "asset") return;

      const rawCss = mainCssAsset.source.toString();

      function scanClasses(filePath: string): Set<string> {
        const fullPath = path.isAbsolute(filePath)
          ? filePath
          : path.join(dirname, filePath);
        if (!fs.existsSync(fullPath)) return new Set();
        const stat = fs.statSync(fullPath);
        const classes = new Set<string>();
        if (stat.isDirectory()) {
          const entries = fs.readdirSync(fullPath);
          for (const entry of entries) {
            const sub = scanClasses(path.join(fullPath, entry));
            sub.forEach((c) => classes.add(c));
          }
          return classes;
        }
        if (!/\.(tsx|ts|jsx|js|html)$/.test(fullPath)) return classes;
        const content = fs.readFileSync(fullPath, "utf8");
        const re =
          /(?:className|class)\s*=\s*["'`{]([^"'`{}]+)["'`}]|["']([a-zA-Z0-9_\-:/[\]%#]+)["']/g;
        let match;
        while ((match = re.exec(content)) !== null) {
          const val = match[1] || match[2] || "";
          val.split(/\s+/).forEach((token) => {
            const clean = token.replace(/^[^{]*\{|\}[^}]*$/g, "").trim();
            if (clean && clean.length < 60) classes.add(clean);
          });
        }
        return classes;
      }

      const initialRouteFiles = [
        "src/pages/LandingPage.tsx",
        "src/components/layout/PublicLayout.tsx",
        "src/components/layout/AppNavbar.tsx",
        "src/components/layout/Footer.tsx",
        "src/hooks/useTheme.tsx",
        "src/entry-client.tsx",
        "src/app/App.tsx",
        "index.html",
      ];
      const initialClasses = new Set<string>();
      initialRouteFiles.forEach((p) =>
        scanClasses(p).forEach((c) => initialClasses.add(c)),
      );

      const routeFiles: Record<string, string[]> = {
        auth: [
          "src/pages/LoginPage.tsx",
          "src/pages/SignupPage.tsx",
          "src/pages/ResetPasswordPage.tsx",
          "src/features/auth",
        ],
        lesson: [
          "src/pages/LessonPage.tsx",
          "src/pages/LearnPage.tsx",
          "src/pages/ChallengePage.tsx",
          "src/pages/SandboxPage.tsx",
          "src/features/lessons",
          "src/components/lessons",
        ],
        dashboard: [
          "src/pages/DashboardPage.tsx",
          "src/pages/AnalyticsDashboardPage.tsx",
          "src/pages/LeaderboardPage.tsx",
          "src/features/dashboard",
          "src/components/dashboard",
        ],
        admin: [
          "src/pages/AdminDashboard.tsx",
          "src/pages/ModerationDashboard.tsx",
          "src/pages/SecurityDashboardPage.tsx",
          "src/pages/admin",
        ],
      };

      const routeClasses: Record<string, Set<string>> = {};
      for (const [r, paths] of Object.entries(routeFiles)) {
        routeClasses[r] = new Set<string>();
        paths.forEach((p) =>
          scanClasses(p).forEach((c) => routeClasses[r].add(c)),
        );
      }

      const root = postcss.parse(rawCss);
      const buckets: Record<string, any> = {
        core: postcss.root(),
        auth: postcss.root(),
        lesson: postcss.root(),
        dashboard: postcss.root(),
        admin: postcss.root(),
      };

      function classifyRule(selector: string): string {
        if (/^(html|body|:root|::|\*)/i.test(selector.trim())) return "core";

        const matches = selector.match(/\.([a-zA-Z0-9_\-\\:/[\]%#]+)/g);
        if (!matches || matches.length === 0) return "core";

        const extracted = matches.map((m) => m.slice(1).replace(/\\/g, ""));
        if (extracted.some((c) => initialClasses.has(c))) return "core";

        for (const [r, set] of Object.entries(routeClasses)) {
          if (extracted.some((c) => set.has(c))) return r;
        }

        const lower = selector.toLowerCase();
        if (/auth|login|signup|password|2fa/i.test(lower)) return "auth";
        if (/lesson|quiz|monaco|markdown|katex/i.test(lower)) return "lesson";
        if (/dashboard|analytic|chart|heatmap|leaderboard/i.test(lower))
          return "dashboard";
        if (/admin|moderation|audit|tenant/i.test(lower)) return "admin";

        return "dashboard";
      }

      root.nodes.forEach((node) => {
        if (node.type === "rule") {
          const dest = classifyRule(node.selector);
          buckets[dest].append(node.clone());
        } else if (
          node.type === "atrule" &&
          (node.name === "media" || node.name === "supports")
        ) {
          const sub: Record<string, any[]> = {
            core: [],
            auth: [],
            lesson: [],
            dashboard: [],
            admin: [],
          };
          node.nodes?.forEach((child: any) => {
            if (child.type === "rule") {
              const dest = classifyRule(child.selector);
              sub[dest].push(child.clone());
            } else {
              sub.core.push(child.clone());
            }
          });
          for (const [d, list] of Object.entries(sub)) {
            if (list.length > 0) {
              const atClone = node.clone({ nodes: [] });
              list.forEach((i) => atClone.append(i));
              buckets[d].append(atClone);
            }
          }
        } else {
          buckets.core.append(node.clone());
        }
      });

      const coreCss = buckets.core.toString();
      mainCssAsset.source = coreCss;

      if (bundle[`${entryCssKey}.br`]) {
        (bundle[`${entryCssKey}.br`] as any).source = zlib.brotliCompressSync(
          Buffer.from(coreCss),
        );
      }
      if (bundle[`${entryCssKey}.gz`]) {
        (bundle[`${entryCssKey}.gz`] as any).source = zlib.gzipSync(
          Buffer.from(coreCss),
        );
      }

      const emittedChunks: Record<string, string> = {
        core: `/${entryCssKey}`,
      };

      const preloadTags: string[] = [];

      for (const route of ["auth", "lesson", "dashboard", "admin"]) {
        const chunkCss = buckets[route].toString();
        if (!chunkCss.trim()) continue;

        const hash = crypto
          .createHash("sha256")
          .update(chunkCss)
          .digest("hex")
          .slice(0, 8);
        const fileName = `assets/${route}-${hash}.css`;
        emittedChunks[route] = `/${fileName}`;

        this.emitFile({
          type: "asset",
          fileName,
          source: chunkCss,
        });

        preloadTags.push(
          `<link rel="preload" href="/${fileName}" as="style" onload="this.onload=null;this.rel='stylesheet'">\n    <noscript><link rel="stylesheet" href="/${fileName}"></noscript>`,
        );
      }

      this.emitFile({
        type: "asset",
        fileName: "route-css-manifest.json",
        source: JSON.stringify(emittedChunks, null, 2),
      });

      const htmlAsset = bundle["index.html"];
      if (htmlAsset && htmlAsset.type === "asset") {
        let htmlSource = htmlAsset.source.toString();
        if (preloadTags.length > 0) {
          const injectedPreloads = `\n    ${preloadTags.join("\n    ")}\n  `;
          htmlSource = htmlSource.replace(
            "</head>",
            `${injectedPreloads}</head>`,
          );
          htmlAsset.source = htmlSource;
        }
      }
    },
  };
}

export default defineConfig({
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    // Same-origin API in dev: forward API traffic to the Django backend so the
    // app works even without a VITE_API_BASE_URL entry (and without CORS
    // preflights). Override with VITE_PROXY_TARGET when the backend runs
    // somewhere else, e.g. VITE_PROXY_TARGET=http://localhost:8001.
    proxy: {
      "/api": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/admin": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/static": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/media": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000",
        ws: true,
        changeOrigin: true,
      },
    },
    ...(process.env.DOCKER === "true" && {
      hmr: {
        clientPort: 5173,
      },
      watch: {
        usePolling: true,
      },
    }),
  },
  build: {
    sourcemap: "hidden",
    minify: "terser",
    terserOptions: { maxWorkers: 2 },
  },
  define: {
    "process.env.VERCEL_GIT_COMMIT_SHA": JSON.stringify(
      process.env.VERCEL_GIT_COMMIT_SHA || "",
    ),
  },
  worker: {
    format: "es",
  },
  base: process.env.VITE_CDN_URL || "/",
  plugins: [
    buildMetadataPlugin(),
    cssRouteSplittingPlugin(),
    visualizerThresholdPlugin(1000),
    react(),
    viteCompression({ algorithm: "brotliCompress", ext: ".br" }),
    viteCompression({ algorithm: "gzip", ext: ".gz" }),
    visualizer({
      filename: "dist/stats.html",
      template: "treemap",
      gzipSize: true,
      brotliSize: true,
    }),
    VitePWA({
      strategies: "injectManifest",
      srcDir: "src",
      filename: "sw.js",
      registerType: "autoUpdate",
      injectManifest: {
        globPatterns: ["**/*.{js,css,ico,png,svg,json,md}"],
        maximumFileSizeToCacheInBytes: 7 * 1024 * 1024,
      },
      manifest: {
        name: "Contribution Atelier",
        short_name: "Atelier",
        theme_color: "#ffffff",
        display: "standalone",
        icons: [
          {
            src: "/icons/icon-192x192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "/icons/icon-512x512.png",
            sizes: "512x512",
            type: "image/png",
          },
        ],
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
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          globals: true,
          environment: "jsdom",
          setupFiles: "./src/test/setup.ts",
          include: ["src/**/*.test.{ts,tsx}"],
          exclude: ["**/*.stories.{ts,tsx}", "**/*.stories.{js,jsx}"],
          testTimeout: 15000,
        },
      },
      {
        extends: true,
        plugins: [
          storybookTest({
            configDir: path.join(dirname, ".storybook"),
          }),
        ],
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
      include: [
        "workbox-precaching",
        "workbox-routing",
        "workbox-strategies",
        "workbox-expiration",
        "@sentry/react",
        "comlink",
      ],
    },
  },
});
