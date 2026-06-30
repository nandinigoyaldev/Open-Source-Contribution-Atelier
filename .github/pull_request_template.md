<!-- 
  IMPORTANT: Please review the guidelines below. 
  PRs that do not contain proof of manual testing or do not link to a valid issue will be closed automatically.
-->

> Please checkmark if you are contributing under SSoC 2026:
- [ ] I am a SSoC26 contributor

## 📋 Description of Changes
<!-- 
  Provide a detailed description of the changes introduced by this pull request.
  List what was added, modified, or removed. Avoid vague descriptions.
-->

- 
- 

## 🔗 Related Issue
<!-- 
  You MUST link to the issue you are resolving. 
  Format: Closes #123 or Fixes #123
-->
Closes #

## 🧪 Proof of Manual Testing (MANDATORY)
<!-- 
  PRs without proof of manual testing will be closed immediately.
  
  For UI / Frontend changes:
  - Attach screenshots, a GIF, or a video demonstrating the changes.
  
  For Backend API / Database / Verifier changes:
  - Attach a terminal output log, curl commands with request/response headers, or test execution logs proving the changes work.
-->

<details>
<summary><b>Click to expand and paste screenshots / logs</b></summary>

### Visual Changes (UI/Frontend)
<!-- Paste images/gifs here -->

### API / Terminal / Test Logs
```bash
# Paste command output here showing the changes run successfully
```
</details>

## ⚙️ Verification Logs (Automated Tests)
<!-- 
  Run tests locally before submitting and paste the summary of output below.
  
  Backend: cd backend && pytest
  Frontend: cd frontend && npm run test
-->

```bash
# Paste verification command output here
```

## 📝 Pre-Submission Checklist
<!-- Please check all boxes that apply. If not checked, the PR may be rejected. -->

- [ ] My PR title follows the Conventional Commits format (e.g. `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
- [ ] My branch name starts with a standard prefix (`feat/`, `fix/`, `docs/`, `refactor/`).
- [ ] I have linked a related issue in the "Related Issue" section above.
- [ ] I have verified that all existing tests pass and added new tests if applicable.
- [ ] I have formatted my changes locally (`cd frontend && npm run format` and `cd backend && black . && isort .`).
- [ ] No API keys, credentials, or sensitive configurations are committed.
