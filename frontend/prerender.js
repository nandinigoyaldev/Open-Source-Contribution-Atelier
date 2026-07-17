import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const toAbsolute = (p) => path.resolve(__dirname, p);

async function prerender() {
  const template = fs.readFileSync(toAbsolute('dist/client/index.html'), 'utf-8');
  
  // Import the server entrypoint
  const { render } = await import('./dist/server/entry-server.js');
  
  // Define public routes to pre-render
  const routesToPrerender = [
    {
      path: '/',
      title: 'Open Source Contribution Atelier',
      description: 'Master git workflows, open source contributions, and interactive playground sandbox challenges.',
      output: 'dist/client/index.html'
    },
    {
      path: '/learn',
      title: 'Lesson Catalog - Git & Open Source',
      description: 'Explore curated lessons covering git merge, rebase, conflicts, pull requests, and standard workflows.',
      output: 'dist/client/learn.html'
    },
    {
      path: '/docs',
      title: 'Documentation - Open Source Contribution Atelier',
      description: 'Find guides, references, and developer documentation for Git tutorials and sandbox operations.',
      output: 'dist/client/docs.html'
    }
  ];

  console.log('Starting server-side rendering (SSR) prerendering...');

  for (const route of routesToPrerender) {
    try {
      const appHtml = render(route.path);
      
      // Inject app HTML and SEO meta tags
      let html = template.replace('<div id="root"></div>', `<div id="root">${appHtml}</div>`);
      
      // Update title tag
      html = html.replace(/<title>(.*?)<\/title>/, `<title>${route.title}</title>`);
      
      // Inject description meta tag
      const metaDescription = `<meta name="description" content="${route.description}" />`;
      html = html.replace('</head>', `  ${metaDescription}\n</head>`);
      
      // Ensure parent directory exists
      const outPath = toAbsolute(route.output);
      fs.mkdirSync(path.dirname(outPath), { recursive: true });
      
      fs.writeFileSync(outPath, html, 'utf-8');
      console.log(`✓ Pre-rendered: ${route.path} -> ${route.output}`);
    } catch (err) {
      console.error(`✗ Failed to pre-render route ${route.path}:`, err);
    }
  }
  
  console.log('Prerendering completed successfully.');
}

prerender();
