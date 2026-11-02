# Performance Budget

`frontend/performance-budget.json` holds the performance limits for the frontend.
The `Performance Budget` workflow (`.github/workflows/performance-budget.yml`) runs
on every PR that touches `frontend/` and fails if a limit is broken.

## What gets checked

| Section      | Checked by                                                                 | In CI |
| ------------ | -------------------------------------------------------------------------- | ----- |
| `bundle`     | `frontend/scripts/analyze-bundle.ts` (`npm run perf:budget`)               | yes   |
| `lighthouse` | Lighthouse CI with `frontend/lighthouserc.cjs` (`npm run perf:lighthouse`) | yes   |
| `api`        | nothing yet, target values only                                            | no    |
| `database`   | nothing yet, target values only                                            | no    |

### Bundle

Sizes are gzipped KB of the files in `dist/client/assets` (source maps and the
precompressed `.gz` / `.br` copies are skipped).

- `totalJsGzipKB`: all JS chunks added together, including lazy loaded routes
- `singleChunkMaxKB`: the biggest single JS chunk
- `totalCssGzipKB`: all CSS files added together

The script also writes a report to `frontend/public/performance.json`, which the
admin performance dashboard reads.

#### Bundle report and review threshold

`npm run perf:budget` also prints a Markdown report (totals plus the 10 largest
files, with budget usage) and, in CI, adds it to the workflow run's job summary
so reviewers can open it from the PR checks. The report has no timestamp and
sorts equal sizes by file name, so the same build always gives the same report.

`reviewThresholdPct` in the `bundle` section (default 90) is the review
threshold. At or above that share of a limit the report marks the row `REVIEW`
and the workflow adds a warning annotation. Above the limit the row is
`OVER BUDGET` and the job fails, as before. When a PR gets a `REVIEW` row,
reviewers should ask whether the growth is intended.

On pull requests the workflow also builds the base branch and posts a comment with the
JS and CSS size change (`frontend/scripts/bundle-size-report.ts`). The comment is best
effort on fork PRs, where the token is read only; the same report is in the job summary.

### Lighthouse

`lighthouserc.cjs` reads its thresholds straight from the `lighthouse` section of
the budget file, so there is only one place to change them. Category scores are
0 to 100 in the budget file (Lighthouse CI wants 0 to 1, the config converts).

It builds nothing itself. It starts `npm run preview` on port 4173 and audits `/`
and `/learn` three times each with the default mobile throttling. No backend is
needed because both pages are prerendered.

## Current numbers

Measured by the workflow on GitHub Actions (Ubuntu, Chrome) against `main`
in October 2026:

| Metric                             | Measured                | Budget   |
| ---------------------------------- | ----------------------- | -------- |
| Total JS (gzip)                    | about 3100 KB           | 3500 KB  |
| Biggest chunk (entry `index-*.js`) | 941 KB                  | 1000 KB  |
| Total CSS (gzip)                   | 63 KB                   | 100 KB   |
| Performance score                  | 64                      | 50       |
| Accessibility                      | 94 (`/`), 89 (`/learn`) | 85       |
| Best practices                     | 96                      | 90       |
| SEO                                | 91                      | 90       |
| Largest Contentful Paint           | about 8.9 s             | 10000 ms |
| Cumulative Layout Shift            | 0                       | 0.1      |
| Time to Interactive (warning only) | about 8.9 s             | 12000 ms |

The limits are set a little above what the app does today, so they catch
regressions without failing every PR. Treat them as a ratchet: when a PR makes
things faster or smaller, lower the matching number in the budget file in the
same PR. `singleChunkMaxKB` matches the 1000 KB chunk limit that `vite.config.ts`
already enforces during the build.

Known gaps worth fixing next:

- the entry chunk is about 940 KB gzipped and loads on every page, splitting it
  is the biggest performance win
- accessibility on `/learn` loses points for `color-contrast` and `skip-link`
- local numbers can differ from CI. A Windows build splits chunks differently
  and a local Chrome or Edge scores differently, so trust the CI run

## Running the checks locally

From `frontend/`:

```bash
npm install
npm run build              # full production build into dist/
npm run perf:budget        # bundle size check
npm run perf:lighthouse    # Lighthouse CI, needs Chrome or Chromium installed
```

`npm run analyze-bundle` still works too, it rebuilds the client first and then
runs the same bundle check.

If Lighthouse can't find Chrome, point it at any Chromium based browser:

```bash
CHROME_PATH="/path/to/chrome" npm run perf:lighthouse
```

Lighthouse uploads the report to temporary public storage and prints the link.
To keep the reports local instead:

```bash
npx lhci autorun --upload.target=filesystem --upload.outputDir=.lighthouseci
```

`npm run perf:budget` rewrites `frontend/public/performance.json`. Don't commit
that change unless you mean to update the dashboard data. `.lighthouseci/` is
gitignored.
