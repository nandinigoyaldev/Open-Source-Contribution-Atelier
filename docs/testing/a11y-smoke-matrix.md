# Accessibility smoke matrix

A small Playwright suite (tag `@a11y-smoke`) that runs the same sign in and lesson flows in every supported browser and checks keyboard use, focus and screen reader announcements. It is a smoke test, not an axe audit: `e2e/accessibility/a11y-ci.spec.ts` still covers WCAG rules per route, and [a11y-conformance.md](a11y-conformance.md) is the gate for critical journeys.

## Browsers

`docs/CONTRIBUTING.md` lists Chrome, Firefox, Safari, Edge and mobile browsers as the browsers to verify. Edge runs on Chromium, so it has no project of its own.

| Project                | Engine   | Profile         |
| ---------------------- | -------- | --------------- |
| `matrix-chromium`      | Chromium | Desktop Chrome  |
| `matrix-firefox`       | Firefox  | Desktop Firefox |
| `matrix-webkit`        | WebKit   | Desktop Safari  |
| `matrix-mobile-chrome` | Chromium | Pixel 5         |

The projects live in `frontend/playwright.a11y-matrix.config.ts`. The default `playwright.config.ts` ignores `e2e/a11y-matrix/`, so `npm run test:e2e` and `npm run test:a11y` are unchanged.

## Running it

```bash
cd frontend
npx playwright install chromium firefox webkit   # only the ones you need
npm run test:a11y:matrix                         # all four projects
npm run test:a11y:matrix -- --project=matrix-firefox
npm run test:a11y:matrix -- --repeat-each 3 --workers 4   # parallel safety check
```

The config starts the Vite dev server itself (or reuses one on port 5173). Use `A11Y_MATRIX_PORT=5421` to pick another port. On Linux, WebKit needs system libraries: `npx playwright install --with-deps webkit`.

CI runs one job per project (`smoke-matrix` in `.github/workflows/accessibility.yml`) and installs only that job's browser. Traces, screenshots and video are kept only for failures and are uploaded as an artifact.

## Flows

| Flow id                 | What it checks                                                                                                                                                                                                                                      |
| ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `sign-in`               | Keyboard-only login (Tab to the field, type, Enter). Lands on `/dashboard`, the token is stored, focus is reset instead of stranded on the removed form, the first Tab reaches the skip link.                                                       |
| `sign-in-error`         | A rejected login reaches a `role="alert"` region, the page stays on `/login`, the typed username is kept.                                                                                                                                           |
| `lesson-open`           | Opening `/lessons/<slug>` puts focus in the command input.                                                                                                                                                                                          |
| `lesson-complete`       | A wrong command is announced in an alert region, the right one in a status region, and after the 3 second debounce "Lesson completion saved." appears in the polite status region and the POST to `/progress/bulk-update/` carries the lesson slug. |
| `lesson-complete-error` | A failed save ("Could not save lesson completion...") reaches an alert region.                                                                                                                                                                      |
| `lesson-next`           | After finishing a lesson, `Alt+ArrowRight` routes to the next lesson and the next Tab reaches a real control.                                                                                                                                       |
| `shortcuts-dialog`      | `?` opens the shortcuts dialog, it is modal and named, Tab never leaves it, Escape closes it and focus goes back to the control that opened it.                                                                                                     |

### Known gaps

Two tests in the second `describe` assert behaviour the app does not have yet and are marked `test.fail()`. They pass while the gap exists and fail once it is fixed, which is the signal to delete the `test.fail()` line and move the test up.

- `lesson-next-focus`: focus does not move into the new lesson after a lesson to lesson route change.
- `lesson-tab-out`: the command input swallows Tab (for completion), so keyboard users cannot reach the buttons below it.

## How the suite stays parallel safe

- Every test gets a fresh user (`generateUniqueTestUser`) and a lesson with a random slug.
- The backend is fully mocked with `page.route` (the `mocked` and `signedIn` fixtures in `e2e/a11y-matrix/support.ts`). A catch-all `/api/**` route is registered first, so a call nobody mocked returns an empty 200 instead of reaching a real server.
- Service workers are blocked in the config, otherwise the PWA worker answers requests before `page.route` sees them.
- No test reads state another test wrote, and `fullyParallel` is on.

## Failure output

Every assertion message starts with the flow and the project, for example `[lesson-complete on matrix-firefox] role=status live region should say "Lesson completion saved."`. `tabTo()` lists the last elements Tab visited when it cannot reach a control. On failure an `a11y-state.txt` attachment records the URL, the focused element, every live region with its text, the Tab trail and console errors.

## Adding a flow

1. Add a `test("<flow-id>: <what it proves>", ...)` in `e2e/a11y-matrix/smoke-matrix.spec.ts`. Keep the flow id before the colon, `ctx` uses it.
2. Take the `signedIn` fixture for a logged in page or `mocked` for a public one. Add `page.route` mocks for any extra endpoint, and use `makeLesson()` instead of a fixed slug.
3. Drive it with the keyboard (`page.keyboard`, `tabTo()`), not `click()`, and wrap each assertion in `expect(x, ctx("what should be true"))`.
4. For messages use `expectAnnounced(page, "status" | "alert", text, ctx)`, which also checks the region is not `aria-live="off"`.
5. If the app does not do the right thing yet, write the test for the right behaviour and add `test.fail(true, "reason")` in the known gaps block.
6. Add the flow to the table above and run `--repeat-each 3 --workers 4` on at least chromium and firefox.
