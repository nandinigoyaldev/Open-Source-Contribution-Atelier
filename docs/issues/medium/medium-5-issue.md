# Implement LocalStorage Caching Fallback for GitHub Contributors API

- **Difficulty**: Medium
- **Category**: GitHub Integration
- **Beginner Friendliness**: Yes, data parsing.

---

### Description
The GitHub contributors API has an hourly rate limit of 60 hits for unauthenticated calls. Cache results locally.

### Expected Outcome
Page loads details from LocalStorage cache if API call fails.

### Acceptance Criteria
- [ ] Implement caching logic in DashboardPage.
- [ ] Store results with a 24-hour expiration token.

### Files Likely Affected
- [frontend/src/pages/DashboardPage.tsx](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/frontend/src/pages/DashboardPage.tsx)
