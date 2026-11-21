# Contributing to Open Source Contribution Atelier

Thank you for your interest in contributing! We welcome **all types of contributions**—not just code, but also UI/UX design, documentation, manual testing, translations, and bug reporting.

Whether you're a writer, designer, QA tester, translator, or software developer, there is a place for you here.

---

## 🎨 Non-Code Contributions

You don't need to write code to make an impact on Open Source Contribution Atelier. Here are the primary ways non-code contributors get involved:

### 1. 🐛 Reporting Bugs & UX Issues
Help us find glitches, accessibility gaps, or visual flaws before our users do.
- **Search First**: Check existing GitHub Issues to see if the bug has already been reported.
- **Open a Bug Report**: Use our Bug Report template on GitHub. Include:
  - Clear title and summary.
  - Steps to reproduce (1, 2, 3...).
  - Expected vs. actual behavior.
  - Screenshots or screen recordings.
  - Browser name, OS, and screen resolution.

### 2. 📝 Writing & Improving Documentation
Clear documentation helps everyone learn open source effectively.
- **Curriculum Lessons**: Improve markdown lessons in `frontend/public/content/` (fix typos, clarify explanations, improve code snippets).
- **Developer Documentation**: Enhance setup guides, architecture diagrams, and inline code comments in `docs/` and `infra/`.
- **Tutorials & Guides**: Author step-by-step guides for new open-source contributors.

### 3. 🎨 UI/UX Design Feedback, Mockups & Accessibility
Help shape our user interface, design system, and user experience.
- **Design Reviews**: Audit existing pages (`frontend/src/pages/`) for visual consistency, contrast ratios, and responsive layout issues.
- **Mockups & Wireframes**: Propose UI improvements by attaching Figma links, SVG wireframes, or annotated screenshots to GitHub issues with the `design` tag.
- **Accessibility (a11y) Audits**: Test pages using screen readers or keyboard-only navigation, and report WCAG compliance issues.

### 4. 🧪 Manual Testing & Quality Assurance (QA)
Ensure features work seamlessly across different platforms and environments.
- **Feature QA**: Test new pull requests locally or on staging builds. Validate edge cases (empty states, long inputs, network disconnects).
- **Cross-Browser Verification**: Verify layout rendering and interactivity on modern browsers (Chrome, Firefox, Safari, Edge, Mobile browsers).
- **Create QA Test Plans**: Write structured test cases in issue comments to help developers cover critical paths.

### 5. 🌐 Translations & Localization (i18n)
Help make Open Source Contribution Atelier accessible to non-English speakers worldwide!
- **Locale JSON Files**: Our translations live in `frontend/src/i18n/locales/` (`en.json`, `es.json`, `fr.json`, `de.json`, `hi.json`, `ja.json`, `ar.json`, `zh-CN.json`, `pt-BR.json`).
- **Translating Keys**: Translate string keys, fix grammar mistakes, or add localized ICU formatting.
- **New Languages**: Propose and add support for new language locales.

---

## 🏷️ How to Find & Claim Non-Code Issues

We tag non-code issues to make them easy to discover:

| Contribution Type | GitHub Issue Labels |
|---|---|
| Documentation | `documentation`, `docs`, `good-first-issue` |
| Design & UI/UX | `design`, `ui/ux`, `accessibility` |
| QA & Manual Testing | `qa`, `testing`, `bug` |
| Translations | `translation`, `i18n` |
| Performance & Benchmarks | `perf-review`, `performance` |

### How to Claim an Issue
1. Browse issues filterable by labels (e.g., `is:open label:documentation`).
2. Leave a comment on the issue asking to be assigned (e.g., `/claim` or "I'd like to work on this!").
3. Once assigned, you have a **48-Hour SLA** to open a Draft PR or submit your work to prevent automatic unassignment.

---

## 🛠️ Local Development Setup

If your non-code contribution involves editing markdown files, documentation, or locale JSON files directly:

1. **Install Dependencies**:
   ```bash
   make install
   ```
2. **Start Development Server**:
   ```bash
   make start
   # Or for frontend only:
   cd frontend && npm run dev
   ```
3. **Run Formatting & Linting**:
   ```bash
   make format
   ```
4. **Run Verification Checklist**:
   ```bash
   make verify
   ```

### Playwright E2E Tests

For progress and celebration components, follow the [reduced-motion pattern](frontend/REDUCED_MOTION.md) and verify the final state remains understandable when the preference is enabled.

Run the Playwright end-to-end suite locally from the `frontend/` directory:

```bash
cd frontend
npm run test:e2e
```

---

## 📋 Pull Request Requirements

We maintain strict quality controls on pull requests to ensure contributions align with project goals:

### 1. Linking an Issue
All pull requests must resolve a corresponding open issue. Reference the issue in your PR description using closing keywords (e.g., `Closes #2288` or `Fixes #2288`).

### 2. Scope Verification
The modified files must correspond to the scope promised in the linked issue. For non-code contributions, specify the appropriate scope exemption tag in your PR description if needed:
- `Docs only` / `Documentation`
- `Frontend only` / `only frontend`
- `Design` / `Translation`

### 3. Issue Assignment Cap
- Each contributor is limited to a maximum of **5 open assigned issues** at a time.
- Remember the **48-Hour SLA**: A draft PR or update must be provided within 48 hours of assignment.
