# Contributing to Open Source Contribution Atelier

Thank you for your interest in contributing! We want this repository to be a model of open-source best practices and a friendly playground for developers of all levels.

---

## 🌟 Our Contribution Philosophy
- **Inclusivity First**: We welcome contributions from absolute beginners (typo fixes, documentation rewrites) to advanced developers.
- **Clear Communication**: Respect volunteer maintainers' time. Explain *what* your PR accomplishes and *why*.
- **Quality Over Quantity**: Trivial PRs opened just to boost stats (e.g. adding empty lines or formatting comments) will be marked as spam. Focus on meaningful edits!

---

## 🛣️ The Contributor Journey

```
1. Find an Issue ──> 2. Request Assignment ──> 3. Fork & Clone ──> 4. Create Branch
                                                                        │
5. PR Merge ◄── 8. Review & Revisions ◄── 7. Open Pull Request ◄── 6. Develop & Test
```

### 1. Find an Issue
Explore open tasks on the [Issues Board](https://github.com/goyaljiiiiii/Open-Source-Contribution-Atelier/issues).
- Look for `good first issue` or `beginner-friendly` labels if you are a newcomer.
- Look for `bug`, `enhancement`, or `curriculum` depending on your interest.

### 2. Request Assignment
Comment on the issue explaining how you plan to solve it, and ask to be assigned. **Do not start coding until a maintainer assigns the issue to you!** This prevents duplicate work.

### 3. Fork & Clone
1. Click the **Fork** button on GitHub.
2. Clone your personal fork locally:
   ```bash
   git clone https://github.com/your-username/Open-Source-Contribution-Atelier.git
   ```

### 4. Create a Feature Branch
Keep your default `main` branch synchronized with the upstream project. Always do work on a feature branch:
```bash
git checkout -b feat/add-git-rebase-lesson
# or using switch
git switch -c feat/add-git-rebase-lesson
```
**Branch Naming Conventions:**
- `feat/...` for new features or lessons.
- `fix/...` for bugs or UI fixes.
- `docs/...` for updates to documentation.
- `refactor/...` for cleaning up code.

### 5. Develop & Run Local Tests
Follow the setup in [README.md](README.md) to run the client and server.
Run testing and formatting commands locally before pushing:

**Testing:**
- Frontend: `cd frontend && npm run test`
- Backend: `cd backend && pytest`

**Lint & Format Checklist:**
- `cd frontend && npm run lint` — Check for ESLint errors
- `cd frontend && npm run format` — Auto-format code with Prettier
- `cd backend && black --check .` — Verify Python Pep8 compliance

Run all checks above before opening a pull request to avoid CI failures.

### 6. Submit a Pull Request
Push your branch to your fork on GitHub and click **New Pull Request**.

> [!IMPORTANT]
> **Automated PR Check: Linked Issue Required**
> Every pull request must reference a related issue in its description. If you don't link an issue, the automated **Check Linked Issue** workflow will fail, and a warning comment will be added.
>
> You can link an issue by adding one of the following keywords followed by the issue number in the PR description (e.g., `Closes #123`, `Fixes #123`, `Resolves #123`, `related to #123`, or `ref #123`).

Use the template below for your description:
```markdown
### Summary
Describe what your PR changes and the technical approach.

### Related Issues
Closes #issue_number

### Testing & Verification
List how you tested your changes (e.g., screenshot, Vitest log, manual terminal output).
```

---

## ✍️ Contribution Paths

### 1. Contributing Content (Lessons & Quizzes)
If you want to add a lesson, write a quiz, or edit the curriculum, you **do not** need to write code. Please refer to our detailed **[Content Guide](CONTENT_GUIDE.md)**.

### 2. Contributing Code (React or Django)
- Keep components small, modular, and accessible.
- Maintain type safety inside TypeScript files.
- Python code should conform to Pep8 standard formatting (e.g., using `black`).
- Do not commit sensitive details, `.env` configurations, or generated build directories.

---

## 💬 Code of Conduct
We enforce a respectful, safe, and professional environment. Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).
