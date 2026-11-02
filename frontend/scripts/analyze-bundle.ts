import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";
import { buildMarkdownReport, sortBundles } from "./bundle-report";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, "..");
const DIST_DIR = fs.existsSync(path.join(ROOT_DIR, "dist", "client", "assets"))
  ? path.join(ROOT_DIR, "dist", "client", "assets")
  : path.join(ROOT_DIR, "dist", "assets");
const BUDGET_FILE = path.join(ROOT_DIR, "performance-budget.json");
// Save to public/ so it's available during 'npm run dev' and copied to dist/ during build
const OUTPUT_FILE = path.join(ROOT_DIR, "public", "performance.json");

function analyzeBundle() {
  if (!fs.existsSync(BUDGET_FILE)) {
    console.error("❌ performance-budget.json not found");
    process.exit(1);
  }

  if (!fs.existsSync(DIST_DIR)) {
    console.error("❌ Build output not found. Did you run `npm run build`?");
    process.exit(1);
  }

  const budget = JSON.parse(fs.readFileSync(BUDGET_FILE, "utf-8"));
  const files = fs.readdirSync(DIST_DIR);

  let totalJsGzip = 0;
  let totalCssGzip = 0;
  const chunks: { name: string; sizeKB: number; type: string }[] = [];
  const violations: string[] = [];

  for (const file of files) {
    const filePath = path.join(DIST_DIR, file);
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) continue;

    const raw = fs.readFileSync(filePath);
    const gzipped = zlib.gzipSync(raw);
    const gzipKB = Math.round(gzipped.length / 1024);

    if (
      file.endsWith(".map") ||
      file.endsWith(".js.gz") ||
      file.endsWith(".js.br") ||
      file.endsWith(".css.gz") ||
      file.endsWith(".css.br")
    ) {
      continue;
    }

    if (file.endsWith(".js")) {
      totalJsGzip += gzipKB;
      chunks.push({ name: file, sizeKB: gzipKB, type: "JS" });
      if (gzipKB > budget.bundle.singleChunkMaxKB) {
        violations.push(
          `Chunk \`${file}\` (${gzipKB}KB) exceeds limit of ${budget.bundle.singleChunkMaxKB}KB`,
        );
      }
    } else if (file.endsWith(".css")) {
      totalCssGzip += gzipKB;
      chunks.push({ name: file, sizeKB: gzipKB, type: "CSS" });
    } else {
      chunks.push({ name: file, sizeKB: gzipKB, type: "Asset" });
    }
  }

  const sortedChunks = sortBundles(chunks);
  const top10Chunks = sortedChunks.slice(0, 10);

  const report = {
    timestamp: new Date().toISOString(),
    metrics: {
      totalJsGzipKB: totalJsGzip,
      totalCssGzipKB: totalCssGzip,
    },
    budget: budget.bundle,
    top10Chunks,
    violations,
    status:
      violations.length > 0 ||
      totalJsGzip > budget.bundle.totalJsGzipKB ||
      totalCssGzip > budget.bundle.totalCssGzipKB
        ? "failed"
        : "passed",
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(report, null, 2));
  console.log(`✅ Performance report saved to ${OUTPUT_FILE}`);

  // Show the largest bundles to reviewers: job summary plus warning annotations.
  const { markdown, warnings } = buildMarkdownReport(
    chunks,
    { totalJsGzipKB: totalJsGzip, totalCssGzipKB: totalCssGzip },
    budget.bundle,
  );
  console.log(markdown);
  if (process.env.GITHUB_STEP_SUMMARY) {
    fs.appendFileSync(
      process.env.GITHUB_STEP_SUMMARY,
      `${markdown}
`,
    );
  }
  warnings.forEach((w) =>
    console.log(`::warning title=Bundle near budget::${w}`),
  );

  if (totalJsGzip > budget.bundle.totalJsGzipKB) {
    console.error(
      `❌ Total JS bundle (${totalJsGzip}KB) exceeds budget of ${budget.bundle.totalJsGzipKB}KB`,
    );
    process.exit(1);
  }

  if (totalCssGzip > budget.bundle.totalCssGzipKB) {
    console.error(
      `❌ Total CSS bundle (${totalCssGzip}KB) exceeds budget of ${budget.bundle.totalCssGzipKB}KB`,
    );
    process.exit(1);
  }

  if (violations.length > 0) {
    console.error("❌ One or more chunks exceed the single-chunk size budget:");
    violations.forEach((v) => console.error(`  - ${v}`));
    process.exit(1);
  }

  console.log("✅ Bundle sizes are within the performance budget!");
}

analyzeBundle();
