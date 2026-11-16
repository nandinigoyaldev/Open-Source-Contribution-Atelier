import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, test } from "node:test";
import { checkRouteChunks } from "./check-route-chunks.mjs";

const directories = [];
afterEach(() => {
  while (directories.length) fs.rmSync(directories.pop(), { recursive: true, force: true });
});

function fixture(files, requiredRoutes = { DashboardPage: 1 }) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "route-budget-"));
  directories.push(root);
  const assets = path.join(root, "assets");
  fs.mkdirSync(assets);
  for (const [name, content] of Object.entries(files)) fs.writeFileSync(path.join(assets, name), content);
  const budget = path.join(root, "budget.json");
  fs.writeFileSync(budget, JSON.stringify({ defaultMaxGzipKB: 2, requiredRoutes }));
  return { assets, budget };
}

test("accepts a required route and a second route within budget", () => {
  const { assets, budget } = fixture({ "DashboardPage-abC-_.js": "export default 1;", "LessonPage-Z12.js": "export default 2;", "index-hash.js": "ignored" });
  const result = checkRouteChunks(assets, budget);
  assert.deepEqual(result.violations, []);
  assert.equal(result.measured.length, 2);
  assert.equal(result.measured[0].limitKB, 1);
});

test("reports a missing or renamed required route", () => {
  const { assets, budget } = fixture({ "OverviewPage-ab12.js": "export default 1;" });
  assert.match(checkRouteChunks(assets, budget).violations.join("\n"), /Expected one DashboardPage-\*\.js chunk.*found 0/);
});

test("reports the oversized artifact and its budget", () => {
  const { assets, budget } = fixture({ "DashboardPage-ab12.js": Buffer.from(Array.from({ length: 4096 }, (_, i) => i % 251)) }, { DashboardPage: 0.01 });
  assert.match(checkRouteChunks(assets, budget).violations.join("\n"), /DashboardPage-ab12\.js: .* exceeds 0\.01 KiB route budget/);
});
