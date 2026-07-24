#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { parse } from "acorn";
import * as walk from "acorn-walk";

function collectExports(filePath) {
  const source = fs.readFileSync(filePath, "utf8");
  const exports = new Set();
  let ast;
  try {
    ast = parse(source, {
      ecmaVersion: "latest",
      sourceType: "module",
      allowHashBang: true,
    });
  } catch {
    return exports;
  }

  walk.simple(ast, {
    ExportNamedDeclaration(node) {
      if (node.declaration?.declarations) {
        for (const declaration of node.declaration.declarations) {
          if (declaration.id?.name) exports.add(declaration.id.name);
        }
      } else if (node.declaration?.id?.name) {
        exports.add(node.declaration.id.name);
      }
      for (const specifier of node.specifiers || []) {
        if (specifier.exported?.name) exports.add(specifier.exported.name);
      }
    },
    ExportDefaultDeclaration() {
      exports.add("default");
    },
  });
  return exports;
}

function walkFiles(root) {
  const results = [];
  if (!fs.existsSync(root)) return results;
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    const full = path.join(root, entry.name);
    if (entry.isDirectory()) {
      if (!["node_modules", "test", "tests", "__tests__"].includes(entry.name)) {
        results.push(...walkFiles(full));
      }
    } else if (/\.(mjs|js|cjs)$/.test(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

function packageExports(root) {
  const exports = new Set();
  for (const file of walkFiles(root)) {
    for (const name of collectExports(file)) exports.add(name);
  }
  return exports;
}

const [oldDir, newDir] = process.argv.slice(2);
if (!oldDir || !newDir) {
  console.error("Usage: compare_npm_exports.mjs <old-package-dir> <new-package-dir>");
  process.exit(2);
}

const oldExports = packageExports(oldDir);
const newExports = packageExports(newDir);
const removed = [...oldExports].filter((name) => !newExports.has(name)).sort();
const added = [...newExports].filter((name) => !oldExports.has(name)).sort();

process.stdout.write(JSON.stringify({
  oldExportCount: oldExports.size,
  newExportCount: newExports.size,
  removed,
  added,
}, null, 2));
