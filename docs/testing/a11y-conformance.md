# Accessibility conformance gate

A Playwright suite (tag `@a11y-conformance`) that audits the critical journeys at three breakpoints and fails the PR with the route and the rule that broke. Its neighbours:

- `e2e/accessibility/a11y-ci.spec.ts` runs axe on a list of routes, without a signed in user or a backend.
- [The smoke matrix](a11y-smoke-matrix.md) runs sign in and the lesson flow in every browser.
- This gate signs in, mocks the data so the real page renders, and checks six things on each page.

## What it covers

Every entry is a surface in `e2e/a11y-conformance/surfaces.ts`.

| Journey           | Surface                | Route                   | State                                   |
| ----------------- | ---------------------- | ----------------------- | --------------------------------------- |
| authentication    | `login`                | `/login`                | Signed out                              |
|                   | `login-rejected`       | `/login`                | After a rejected login                  |
|                   | `signup`               | `/signup`               | Signed out                              |
| lesson completion | `lesson-open`          | `/lessons/:slug`        | Just opened                             |
|                   | `lesson-done`          | `/lessons/:slug`        | Right command entered, completion saved |
| dashboard         | `dashboard`            | `/dashboard`            | Contributor, also follows a nav link    |
| rooms             | `notes-room`           | `/collab-notes/:roomId` | Collaborative notes room, socket mocked |
|                   | `chat-room`            | `/chat/:roomId`         | Chat room, socket mocked                |
| administration    | `admin-dashboard`      | `/dashboard`            | Staff user                              |
|                   | `admin-audit`          | `/admin/audit`          | Staff user, one audit event             |
|                   | `admin-moderation`     | `/moderation`           | Staff user, one pending report          |
|                   | `admin-content-studio` | `/admin/content-studio` | Staff user                              |

Breakpoints are Playwright projects, all on Chromium:

| Project               | Viewport                               |
| --------------------- | -------------------------------------- |
| `conformance-desktop` | 1280 x 720                             |
| `conformance-tablet`  | 810 x 1080, touch                      |
| `conformance-mobile`  | Pixel 5 (393 x 727), touch             |
| `conformance-rules`   | No browser, checks the exceptions file |

### Not covered

- **Drawing rooms.** The app has no drawing room yet: there is no route, page or component for one, only the canvas used to export achievement cards. The `rooms` journey covers the real time rooms that do exist. When a drawing room route lands, add it as a surface.
- `/collab/:sessionId`, and the other admin routes (`/admin/backups`, `/admin/celery`, `/admin/security` and so on).
- The dark theme. Scans run in the default light theme.
- Empty and error states, other than the rejected login.
- Other browsers. Browser coverage is the job of the smoke matrix.
- Anything axe reports as "incomplete", for example contrast of text over a gradient or an image. The manual gate below picks those up.
- Canvas and script driven motion. `document.getAnimations()` only sees CSS and Web Animations, so the lesson confetti is not caught by `motion/keeps-animating`.

## What it checks

All checks run on every surface and report together, so one red run lists everything wrong with the route. Rule ids are `<dimension>/<rule>`. Rules that come from axe keep their axe id.

| Dimension            | How                                                               | Rules                                                                                                                                                                                                                |
| -------------------- | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Keyboard             | Tab through the whole page, then use the skip link                | `keyboard/tab-trap`, `keyboard/hidden-tab-stop`, `keyboard/no-focus-indicator`, `keyboard/main-control-unreachable`, `keyboard/skip-link`, plus axe rules such as `keyboard/scrollable-region-focusable`             |
| Focus management     | Open the shortcuts dialog, finish the journey, follow a nav link  | `focus/dialog-does-not-open`, `focus/dialog-focus-not-moved`, `focus/dialog-focus-escapes`, `focus/dialog-escape-ignored`, `focus/dialog-focus-not-returned`, `focus/lost-after-action`, `focus/route-change-silent` |
| Structure            | axe                                                               | `structure/landmark-one-main`, `structure/page-has-heading-one`, `structure/heading-order`, `structure/region` and others                                                                                            |
| Contrast             | axe                                                               | `contrast/color-contrast`                                                                                                                                                                                            |
| Reduced motion       | `prefers-reduced-motion: reduce`, then `document.getAnimations()` | `motion/keeps-animating`                                                                                                                                                                                             |
| Screen reader labels | axe                                                               | `labels/button-name`, `labels/label`, `labels/select-name`, `labels/link-name`, `labels/image-alt`, `labels/label-content-name-mismatch` and others                                                                  |

Axe runs the `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa` and `best-practice` tags.

`selftest.spec.ts` runs the same checks on a page that is broken on purpose. If a check goes blind, that test goes red.

## Running it

```bash
cd frontend
npx playwright install chromium
npm run test:a11y:conformance
npm run test:a11y:conformance -- --project=conformance-mobile
npm run test:a11y:conformance -- --grep admin-moderation
```

The config starts the Vite dev server itself, or reuses one on port 5173. `A11Y_MATRIX_PORT=5421` picks another port. CI runs it as the `conformance` job in `.github/workflows/accessibility.yml`, and traces and screenshots of a failure are uploaded as an artifact.

## Reading a failure

The message names the rule, the route and the breakpoint, then what to change:

```
1 accessibility finding. To waive one, add an entry with owner, rationale and expiry to e2e/a11y-conformance/exceptions.json.

motion/keeps-animating on /login at desktop
  element: spin on <h2.animate-spin>
  problem: this animation never stops, even though the user asked for reduced motion
  fix:     Stop it under @media (prefers-reduced-motion: reduce), or use motion-safe: on the Tailwind class
  docs:    https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions
```

If an exception matched but cannot be honoured, the finding gets a `note` line, for example `exception owned by Anshuu2004 does not count: expired on 2026-11-01`.

On CI the same text shows as an annotation on the PR. `a11y-findings.json` is attached to every test with both the blocking and the waived findings, and `a11y-state.txt` has the URL, focus, live regions and console errors of a failed run.

## Exceptions

Fix the problem if you can. If you cannot yet, add an entry to `e2e/a11y-conformance/exceptions.json`:

```json
{
  "rule": "keyboard/main-control-unreachable",
  "routes": ["/moderation"],
  "owner": "your-github-login",
  "rationale": "Report cards are div onClick, so a keyboard user cannot open one.",
  "expires": "2027-02-05"
}
```

| Field         | Required | Meaning                                                                                                                        |
| ------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `rule`        | yes      | The rule id from the failure message                                                                                           |
| `routes`      | yes      | Route patterns from `src/app/router.tsx`. `*` is for a defect in the shared app shell                                          |
| `owner`       | yes      | GitHub login of who is on the hook for the fix                                                                                 |
| `rationale`   | yes      | Why this cannot be fixed now, at least 20 characters                                                                           |
| `expires`     | yes      | Last day it counts, `YYYY-MM-DD`, UTC                                                                                          |
| `target`      | no       | Only waive elements whose selector or description contains this. Avoid it for axe rules: axe selectors can change between runs |
| `breakpoints` | no       | Only waive at these breakpoints                                                                                                |
| `maxFindings` | no       | Waive this many per surface and breakpoint, so anything new on the route still fails                                           |

An entry that is expired or is missing a required field waives nothing: the finding fails with a note saying why, and `conformance-rules` fails on its own without needing a browser. So on the day after `expires` the job goes red until someone fixes the defect or renews the entry with a new date and a reason. That is on purpose. It also means a red gate can show up on a PR that changed nothing related, the message says which entry to look at.

## Manual gate

Automation cannot tell whether a screen reader experience makes sense. When a PR changes one of the journeys above, or before a release, go through this for each journey touched and say in the PR what you ran.

- [ ] Keyboard only: finish the journey without a mouse, nothing is unreachable and focus is always visible.
- [ ] Screen reader: NVDA with Firefox on Windows or VoiceOver with Safari on macOS. Headings, landmarks, form labels, errors and the completion message are read out and make sense in order.
- [ ] Zoom: 200% browser zoom and 320 px wide, nothing is cut off or overlapping.
- [ ] Contrast over images and gradients, which axe cannot judge.
- [ ] Dark theme: repeat the contrast check, the gate only scans the light theme.
- [ ] Reduced motion: turn it on in the OS, the journey still makes sense and nothing moves on its own.

## How it stays stable

- The backend is mocked, sockets are cut off and anything outside the dev server is blocked, so results do not depend on the network. `VITE_PROXY_TARGET` points at a closed port for the same reason.
- A surface only counts as ready when its real content is visible, then the check waits for network idle and for one-shot animations to end.
- Toasts are left out of scans because they leave on a timer.
- Only endless animations count, and only if they are still there a second later, so a loading skeleton does not count.
- Transitions are off during the Tab walk, so a focus style is final when it is read.
- Exceptions match on rule and route, not on axe's generated selectors.
- Check with `npm run test:a11y:conformance -- --repeat-each 3 --workers 4` before you add a surface or a check.

## Adding a surface

1. Add an entry to `SURFACES` in `e2e/a11y-conformance/surfaces.ts`. `route` is the pattern from the router, `ready` proves the real content rendered, and `main` is the one control the journey cannot go on without.
2. Mock what the page reads in `open`. The catch all `/api/**` answers `[]`, which crashes pages that expect an object.
3. If the state only exists after an interaction, put it in `act`, driven by the keyboard.
4. Run it, fix what you can, and add an exception for the rest.
