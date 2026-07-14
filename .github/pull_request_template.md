## Description

<!-- Provide a clear and concise summary of your changes -->

Fixes #<!-- issue number -->

## Type of Change

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update (no code changes)
- [ ] ⚙️ CI/CD or build pipeline change
- [ ] ⚡ Performance optimization
- [ ] 🛠️ Refactoring (no functional changes)

## Screenshots / Recordings

<!-- For UI changes, paste before/after screenshots or screen recordings here. Delete this section if not applicable. -->

| Before | After |
|---|---|
| <!-- paste screenshot --> | <!-- paste screenshot --> |

## How Has This Been Tested?

<!-- Describe the tests that you ran to verify your changes -->

### Automated Tests
- [ ] Backend tests pass: `cd backend && pytest`
- [ ] Frontend tests pass: `cd frontend && npm run test`
- [ ] Frontend builds successfully: `cd frontend && npm run build`

### Manual Verification
<!-- Describe any manual testing performed (e.g. user flow verification, edge case testing) -->

## Pre-Push Checklist

> [!IMPORTANT]
> **All items below must be checked before requesting a review.** Our CI bot will automatically run the frontend build and backend tests on your PR. If CI fails, you will receive a comment explaining what went wrong.

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings or console errors
- [ ] I have run `npm run build` in `frontend/` and it completes with **0 errors**
- [ ] I have run `pytest` in `backend/` and all tests pass
- [ ] I have run `git diff` locally and verified my changes

## Deployment Notes

> [!NOTE]
> This project is deployed on **Vercel** (Frontend) and **Hugging Face** (Backend). The CI workflow simulates both deployment environments. If your PR passes CI, it is safe to merge.

<!-- Add any notes about deployment considerations, environment variables, or migration steps needed -->
