import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SRC_DIR = path.resolve(__dirname, "../src");
const CSS_PATH = path.join(SRC_DIR, "styles.css");
const TAILWIND_CONFIG_PATH = path.resolve(__dirname, "../tailwind.config.ts");

/**
 * Recursively collect all .ts/.tsx/.js/.jsx files under a directory.
 */
function collectSourceFiles(dir, files = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      collectSourceFiles(fullPath, files);
    } else if (/\.(tsx?|jsx?)$/.test(entry.name)) {
      files.push(fullPath);
    }
  }
  return files;
}

/**
 * Extract custom class selectors from a plain CSS file.
 *
 * Deliberately ignores @tailwind directives, @media/@keyframes blocks'
 * internals, and bare element/pseudo selectors -- we only care about
 * hand-authored classes that Tailwind's own content-scanning JIT
 * compiler doesn't already track for us.
 */
export function extractCssClasses(cssContent) {
  const classes = new Set();
  // Matches .class-name occurrences used as selectors (not inside comments).
  const withoutComments = cssContent.replace(/\/\*[\s\S]*?\*\//g, "");
  const classRegex = /\.([a-zA-Z_-][a-zA-Z0-9_-]*)/g;
  let match;
  while ((match = classRegex.exec(withoutComments)) !== null) {
    classes.add(match[1]);
  }
  return classes;
}

/**
 * Extract custom theme tokens (colors, boxShadow, animation keys) defined
 * in tailwind.config.ts's `extend` block. These aren't covered by
 * Tailwind's own unused-utility purging, since they're config entries,
 * not generated utility classes.
 */
export function extractTailwindThemeTokens(configContent) {
  const tokens = [];
  const sectionRegex = /(colors|boxShadow|animation)\s*:\s*{([^}]*)}/gs;
  let sectionMatch;
  while ((sectionMatch = sectionRegex.exec(configContent)) !== null) {
    const [, sectionName, body] = sectionMatch;
    const keyRegex = /["']?([a-zA-Z0-9_-]+)["']?\s*:/g;
    let keyMatch;
    while ((keyMatch = keyRegex.exec(body)) !== null) {
      tokens.push({ section: sectionName, name: keyMatch[1] });
    }
  }
  return tokens;
}

/**
 * Check whether a given identifier appears anywhere across the provided
 * source file contents (string match, not AST-aware -- intentionally
 * simple so it catches className strings, clsx() calls, and template
 * literals alike).
 */
export function isReferenced(identifier, sourceContents) {
  return sourceContents.some((content) => content.includes(identifier));
}

function main() {
  console.log("Scanning for unused custom CSS classes and theme tokens...\n");

  if (!fs.existsSync(CSS_PATH)) {
    console.warn(
      `No stylesheet found at ${CSS_PATH}, skipping CSS class check.`,
    );
    return;
  }

  const sourceFiles = collectSourceFiles(SRC_DIR);
  const sourceContents = sourceFiles.map((file) =>
    fs.readFileSync(file, "utf-8"),
  );

  const cssContent = fs.readFileSync(CSS_PATH, "utf-8");
  const cssClasses = extractCssClasses(cssContent);

  const unusedClasses = [...cssClasses].filter(
    (className) => !isReferenced(className, sourceContents),
  );

  let hasFindings = false;

  if (unusedClasses.length > 0) {
    hasFindings = true;
    console.log(
      `Unused custom CSS classes in ${path.relative(process.cwd(), CSS_PATH)}:`,
    );
    for (const className of unusedClasses) {
      console.log(`  - .${className}`);
    }
    console.log("");
  } else {
    console.log("No unused custom CSS classes found.\n");
  }

  if (fs.existsSync(TAILWIND_CONFIG_PATH)) {
    const configContent = fs.readFileSync(TAILWIND_CONFIG_PATH, "utf-8");
    const tokens = extractTailwindThemeTokens(configContent);
    const unusedTokens = tokens.filter(
      (token) => !isReferenced(token.name, sourceContents),
    );

    if (unusedTokens.length > 0) {
      hasFindings = true;
      console.log("Unused Tailwind theme tokens in tailwind.config.ts:");
      for (const token of unusedTokens) {
        console.log(`  - ${token.section}.${token.name}`);
      }
      console.log("");
    } else {
      console.log("No unused Tailwind theme tokens found.\n");
    }
  }

  console.log(
    "Note: Tailwind's own JIT compiler already excludes unused utility\n" +
      "classes (e.g. bg-red-500) from the production build automatically,\n" +
      "based on the `content` globs in tailwind.config.ts. This script\n" +
      "only checks for things Tailwind's tooling doesn't cover: hand-written\n" +
      "custom CSS classes and custom theme tokens.\n\n" +
      "Caution: classes belonging to third-party libraries that inject their\n" +
      "own markup at runtime (e.g. EasyMDE's .editor-toolbar/.editor-preview/\n" +
      ".editor-statusbar) will show up as 'unused' even though they're still\n" +
      "needed, since this script only scans your own .ts/.tsx/.js/.jsx source\n" +
      "files and can't see DOM a library generates internally. Always verify\n" +
      "manually before deleting anything this script flags.",
  );

  if (hasFindings) {
    process.exitCode = 1;
  }
}

main();
