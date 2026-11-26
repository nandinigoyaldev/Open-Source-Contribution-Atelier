import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import postcss from "postcss";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const toAbsolute = (p) => path.resolve(__dirname, p);

function extractCriticalCss(cssText, htmlContent) {
  try {
    const root = postcss.parse(cssText);
    const criticalRoot = postcss.root();

    root.walk((node) => {
      if (node.type === "rule") {
        const sel = node.selector;
        // Keep document-level variables, resets, and typography in critical styles
        if (/^(html|body|:root|::|\*)/i.test(sel.trim())) {
          criticalRoot.append(node.clone());
          return;
        }

        const classMatches = sel.match(/\.([a-zA-Z0-9_\-\\:\/\[\]%#]+)/g);
        if (classMatches) {
          const cleanClasses = classMatches.map((c) =>
            c.slice(1).replace(/\\/g, ""),
          );
          const isUsed = cleanClasses.some((cls) => htmlContent.includes(cls));
          if (isUsed) {
            criticalRoot.append(node.clone());
          }
        }
      } else if (
        node.type === "atrule" &&
        (node.name === "media" || node.name === "supports")
      ) {
        const matchingChildren = [];
        node.nodes?.forEach((child) => {
          if (child.type === "rule") {
            const sel = child.selector;
            if (/^(html|body|:root|::|\*)/i.test(sel.trim())) {
              matchingChildren.push(child.clone());
              return;
            }
            const classMatches = sel.match(/\.([a-zA-Z0-9_\-\\:\/\[\]%#]+)/g);
            if (classMatches) {
              const cleanClasses = classMatches.map((c) =>
                c.slice(1).replace(/\\/g, ""),
              );
              if (cleanClasses.some((cls) => htmlContent.includes(cls))) {
                matchingChildren.push(child.clone());
              }
            }
          }
        });
        if (matchingChildren.length > 0) {
          const atRuleClone = node.clone({ nodes: [] });
          matchingChildren.forEach((mc) => atRuleClone.append(mc));
          criticalRoot.append(atRuleClone);
        }
      }
    });

    return criticalRoot.toString();
  } catch (err) {
    console.warn(
      "Could not extract critical CSS, falling back to full CSS:",
      err,
    );
    return "";
  }
}

async function prerender() {
  const template = fs.readFileSync(
    toAbsolute("dist/client/index.html"),
    "utf-8",
  );

  // Import the server entrypoint
  const { render } = await import("./dist/server/entry-server.js");

  // Define public routes to pre-render
  const routesToPrerender = [
    {
      path: "/",
      title: "Open Source Contribution Atelier",
      description:
        "Master git workflows, open source contributions, and interactive playground sandbox challenges.",
      output: "dist/client/index.html",
    },
    {
      path: "/learn",
      title: "Lesson Catalog - Git & Open Source",
      description:
        "Explore curated lessons covering git merge, rebase, conflicts, pull requests, and standard workflows.",
      output: "dist/client/learn.html",
    },
    {
      path: "/docs",
      title: "Documentation - Open Source Contribution Atelier",
      description:
        "Find guides, references, and developer documentation for Git tutorials and sandbox operations.",
      output: "dist/client/docs.html",
    },
  ];

  console.log("Starting server-side rendering (SSR) prerendering...");

  const assetsDir = toAbsolute("dist/client/assets");
  let coreCss = "";
  let coreCssFile = "";
  if (fs.existsSync(assetsDir)) {
    coreCssFile =
      fs
        .readdirSync(assetsDir)
        .find((f) => f.startsWith("index-") && f.endsWith(".css")) || "";
    if (coreCssFile) {
      coreCss = fs.readFileSync(path.join(assetsDir, coreCssFile), "utf-8");
    }
  }

  for (const route of routesToPrerender) {
    try {
      const appHtml = render(route.path);

      // Inject app HTML
      let html = template.replace(
        '<div id="root"></div>',
        `<div id="root">${appHtml}</div>`,
      );

      // Update title tag
      html = html.replace(
        /<title>(.*?)<\/title>/,
        `<title>${route.title}</title>`,
      );

      // Extract and inline critical CSS for initial paint
      if (coreCss) {
        const criticalCss = extractCriticalCss(coreCss, appHtml);
        if (criticalCss.trim()) {
          const styleTag = `\n  <style id="critical-css">\n${criticalCss}\n  </style>`;
          html = html.replace("</head>", `${styleTag}\n</head>`);

          // Defer non-critical stylesheet to preload to unblock initial paint
          if (coreCssFile) {
            const linkRegex = new RegExp(
              `<link rel="stylesheet" crossorigin href="/assets/${coreCssFile}">`,
            );
            const asyncLink = `<link rel="preload" href="/assets/${coreCssFile}" as="style" onload="this.onload=null;this.rel='stylesheet'">\n  <noscript><link rel="stylesheet" href="/assets/${coreCssFile}"></noscript>`;
            html = html.replace(linkRegex, asyncLink);
          }
        }
      }

      // Add anti-FOUC hydration marker
      const antiFoucScript = `\n  <script>document.documentElement.classList.add('hydrated-styles-ready');</script>`;
      html = html.replace("</head>", `${antiFoucScript}\n</head>`);

      // Inject description meta tag
      const metaTags = `
  <meta name="description" content="${route.description}" />
  <meta property="og:title" content="${route.title}" />
  <meta property="og:description" content="${route.description}" />
  <meta property="og:image" content="/icons/icon-512x512.png" />
  <meta name="twitter:title" content="${route.title}" />
  <meta name="twitter:description" content="${route.description}" />
  <meta name="twitter:image" content="/icons/icon-512x512.png" />
`;
      html = html.replace("</head>", `${metaTags}\n</head>`);

      // Ensure parent directory exists
      const outPath = toAbsolute(route.output);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });

      fs.writeFileSync(outPath, html, "utf-8");
      console.log(`✓ Pre-rendered: ${route.path} -> ${route.output}`);
    } catch (err) {
      console.error(`✗ Failed to pre-render route ${route.path}:`, err);
    }
  }

  console.log("Prerendering completed successfully.");
}

prerender();
