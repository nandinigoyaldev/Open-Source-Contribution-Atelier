import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

export function checkRouteChunks(assetsDir, budgetPath) {
  if (!fs.existsSync(assetsDir)) {
    throw new Error(`Missing client assets at ${assetsDir}; run the frontend build first.`);
  }
  const budget = JSON.parse(fs.readFileSync(budgetPath, "utf8"));
  const { defaultMaxGzipKB, requiredRoutes } = budget;
  if (!Number.isFinite(defaultMaxGzipKB) || defaultMaxGzipKB <= 0 || !requiredRoutes || typeof requiredRoutes !== "object") {
    throw new Error(`Invalid route chunk budget at ${budgetPath}`);
  }
  for (const [route, limit] of Object.entries(requiredRoutes)) {
    if (!Number.isFinite(limit) || limit <= 0) throw new Error(`Invalid budget for ${route}`);
  }

  const files = fs.readdirSync(assetsDir).filter((file) => /^.+Page-[\w-]+\.js$/.test(file));
  const violations = [];
  if (files.length === 0) violations.push(`No route Page-*.js chunks found in ${assetsDir}; check the build output or naming convention.`);

  for (const [route] of Object.entries(requiredRoutes)) {
    const matches = files.filter((file) => file.startsWith(`${route}-`));
    if (matches.length !== 1) {
      violations.push(`Expected one ${route}-*.js chunk in ${assetsDir}, found ${matches.length}; update the route budget if the chunk was renamed.`);
    }
  }

  const measured = files.map((file) => {
    const route = file.match(/^(.+Page)-[\w-]+\.js$/)[1];
    const sizeKB = zlib.gzipSync(fs.readFileSync(path.join(assetsDir, file))).length / 1024;
    const limitKB = requiredRoutes[route] ?? defaultMaxGzipKB;
    if (sizeKB > limitKB) {
      violations.push(`${file}: ${sizeKB.toFixed(1)} KiB gzip exceeds ${limitKB} KiB route budget.`);
    }
    return { file, sizeKB, limitKB };
  });
  return { measured, violations };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const assetsDir = path.resolve(process.argv[2] ?? path.join(frontendRoot, "dist/client/assets"));
    const budgetPath = path.resolve(process.argv[3] ?? path.join(frontendRoot, "route-chunk-budget.json"));
    const { measured, violations } = checkRouteChunks(assetsDir, budgetPath);
    console.log(`Checked ${measured.length} route chunks in ${assetsDir}.`);
    if (violations.length) {
      for (const violation of violations) console.error(`Route budget: ${violation}`);
      process.exitCode = 1;
    } else {
      console.log("All route chunks meet their gzip budgets.");
    }
  } catch (error) {
    console.error(`Route budget: ${error.message}`);
    process.exitCode = 1;
  }
}
