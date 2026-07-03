# Site Audit Report
**Date:** 2026-07-02
**Project:** Open-Source-Contribution-Atelier
**Detected stack:**
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS (Neobrutalist Theme), Framer Motion, TanStack React Virtual, React Query, i18next
- **Backend:** Django 4.x, Django REST Framework, Simple JWT, Python 3.9+, PostgreSQL (Docker), Celery + Redis, WSGI/ASGI entry points
- **Build/Deploy:** Vercel monorepo, Docker‑Compose, npm scripts, pre‑commit hooks (`black`, `isort`)

**Detected audience/goal:**
A learning platform aimed at beginner open‑source contributors. The UI guides users through a gamified curriculum, quizzes, badges, and a hall‑of‑fame. Primary goals are onboarding, skill building, and community visibility.

**Design system maturity:**
Partially tokenized – Tailwind config extends a custom color palette and font families, but many components still use hard‑coded hex values (e.g., CSS background colours, box‑shadows). Dark‑mode support exists via `html.dark` and a high‑contrast mode, but token usage is inconsistent.

---

## Anti‑Pattern Verdict
**Does this look AI‑generated?** **Partially** – several AI‑style cues are present:
- Repeated indigo‑purple gradient in Tailwind config (`blue‑500`, `primary‑container`) – a common “AI default” palette.
- Hero copy in README uses generic emojis and lofty claims without concrete metrics.
- Card‑grid layout is pervasive (many `<section>` elements wrapped in shadowed containers).
- Fonts are limited to generic Google fonts (`Outfit`, `Inter`).
- CTA buttons on landing page have equal visual weight (sign‑in vs. explore).

Score: **2 / 4** (some AI‑generated patterns but also bespoke content).

---

## Audit Health Score

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 3/4 | Mostly good ARIA usage, focus‑visible outlines, but a few missing `alt` text on decorative images. |
| 2 | Performance | 3/4 | Lazy‑loading absent on some `<img>` tags; a few heavy CSS animations on layout properties (`transform` vs `top`). |
| 3 | Security | 2/4 | `dangerouslySetInnerHTML` in `DashboardPage.tsx` (line 685) and `eval` in `CodeSandbox.tsx` (line 70) expose XSS risk. |
| 4 | Theming & design system | 2/4 | Colors hard‑coded in `styles.css` and Tailwind `extend.colors`; token usage inconsistent. |
| 5 | Responsive design | 3/4 | Mostly fluid, but several components use fixed `min‑width: 320px` and touch targets < 44 × 44 px (e.g., close icons). |
| 6 | Anti‑patterns | 2/4 | AI‑generated palette, over‑use of card containers, generic fonts, duplicated curriculum data. |
|   | **Total** | **15/24** | **Acceptable** |

**Legal & compliance flags:**
- Privacy Policy – present (linked from CookieConsentBanner).
- Terms & Conditions – missing (no `TERMS.md` or link).
- Cookie consent – present (Banner component).
- GDPR signals – present (mentions in settings, but no explicit data‑export endpoint).
- COPPA – not applicable (no under‑13 targeting indicated).

---

## Executive Summary
The codebase is a well‑structured monorepo that already implements many modern practices (type‑checked front‑end, Django‑REST API, CI linting hooks). The most pressing issues are **XSS vectors** (dangerously‑set HTML and eval) and **missing legal terms**. Accessibility is largely solid, with a few image‑alt gaps. Performance can be nudged higher by adding lazy‑loading and refining animation properties. The design system needs consolidation to eliminate hard‑coded colors.

**Total findings:** P0 = 2 · P1 = 3 · P2 = 7 · P3 = 5

---

## Quick Wins
1. **Remove `dangerouslySetInnerHTML`** (P0) – replace with a safe markdown renderer or sanitize HTML before insertion.
2. **Eliminate `eval` usage** (P0) – refactor `CodeSandbox.tsx` to use a sandboxed interpreter library.
3. **Add missing Terms & Conditions link** (P1) – create `TERMS.md` and reference it in the footer.
4. **Add `alt` attributes** to decorative images in README/hero section (P2).
5. **Enable `loading="lazy"`** on all `<img>` components (P2).

---

## Findings

### P0 — Blocking
#### XSS via `dangerouslySetInnerHTML`
- **Category:** Security
- **Location:** `frontend/src/pages/DashboardPage.tsx:685`
- **Issue:** Direct insertion of `user.bio_html` without sanitization.
- **User impact:** A malicious contributor could inject script tags, compromising other users’ sessions.
- **Fix:** Use a sanitizing library (e.g., DOMPurify) or convert markdown to safe HTML server‑side.

#### `eval` in Code Sandbox
- **Category:** Security
- **Location:** `frontend/src/components/ui/CodeSandbox.tsx:70`
- **Issue:** Executes arbitrary code strings with `eval`.
- **User impact:** Remote code execution on the client, enabling XSS or data exfiltration.
- **Fix:** Replace with a sandboxed interpreter (e.g., `iframe` sandbox or `vm2` in a backend service).

### P1 — Major
| Title | Category | Location | Issue | Impact | Fix |
|-------|----------|----------|-------|--------|-----|
| Missing Terms & Conditions | Legal | Footer (no file) | No `TERMS.md` or link. | Users have no legal contract; potential liability. | Add `TERMS.md` and link in footer. |
| Hard‑coded colors in CSS | Theming | `frontend/src/styles.css` lines 23‑24, 31‑34 | Hex values (`#000000`, `#fdfbf7`) bypass Tailwind tokens. | Inconsistent branding, makes theming painful. | Replace with Tailwind utility classes or CSS variables referencing `theme`. |
| Fixed touch targets | Responsive | Various icon buttons (`<svg>` close icons) – size ≈ 24 px | Targets < 44 × 44 px. | Hard for finger users; accessibility violation. | Increase hit‑area with padding or larger clickable element. |
| No image lazy‑loading | Performance | All `<img>` components (e.g., hero images) | Images load eagerly. | Slower first paint on mobile. | Add `loading="lazy"` and `srcset` where appropriate. |
| Duplicate curriculum data | Architecture | `frontend/public/content/curriculum.json` + backend models | Two sources of truth. | Risk of out‑of‑sync content, higher maintenance cost. | Consolidate to a single source (e.g., backend API with static export). |

### P2 — Minor
- **Alt text missing** on decorative badges in README (lines 2‑6).
- **CSS animation on `top`/`left`** in `.shake-error` (line 55) – less performant than `transform`.
- **`innerHTML` usage in test files** (`LogoutConfirmModal.test.tsx`, `ErrorBoundary.test.tsx`) – harmless but noisy.
- **No CSP header** in `nginx.conf` – could be added for extra security.
- **Global `boxShadow` values** use absolute pixel values instead of design tokens.

### P3 — Polish
- Minor spelling inconsistencies in documentation.
- Redundant `@keyframes` definitions (`shake`, `flash`) could be merged.
- Some components (e.g., `BadgeToast`) use both Tailwind and custom CSS; unify style source.
- Commented‑out `console.log` statements found in a few dev files.

---

## Systemic Patterns
1. **Hard‑coded colors** – appear in `styles.css`, Tailwind `extend.colors`, and inline `style` attributes across ~15 components.
2. **Touch target size** – < 44 px for icons in modals, navigation, and toast dismiss buttons (≈12 occurrences).
3. **Duplicate curriculum storage** – both a JSON file and Django models (2 separate code paths).
4. **Security‑risky APIs** – `dangerouslySetInnerHTML` and `eval` in production code (2 occurrences).
5. **Legal gaps** – Terms & Conditions absent, GDPR mention present but no data‑export endpoint (systemic compliance shortfall).

---

## Strengths
1. **Strong ARIA coverage** – most interactive components include appropriate `aria‑*` attributes, focus‑visible outlines, and live regions.
2. **Well‑structured monorepo** – clear separation of `frontend/`, `backend/`, `services/`, and `infra/` with consistent tooling (pre‑commit, Docker compose).
3. **High‑contrast mode** – comprehensive CSS overrides (`html.high‑contrast`) provide an accessible fallback for visually impaired users.

---

## Recommended Priority Order
1. **Sanitize or remove `dangerouslySetInnerHTML`** (security, P0).
2. **Replace `eval` with a safe sandbox** (security, P0).
3. **Create and link Terms & Conditions** (legal, P1).
4. **Consolidate curriculum data source** (architecture, P1).
5. **Add `alt` text to images and lazy‑load them** (accessibility & performance, P2).
6. **Normalize color usage via Tailwind tokens** (theming, P2).
7. **Increase touch target sizes** (accessibility, P2).

---

*End of report.*
