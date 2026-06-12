# Implement Automatic API Fallback if VITE_API_BASE_URL is blank

- **Difficulty**: Medium
- **Category**: Deployment
- **Beginner Friendliness**: Yes, environment fix.

---

### Description
If the base URL is unset, the app breaks. Fallback dynamically to the browser origin.

### Expected Outcome
App guesses backend route using host mappings.

### Acceptance Criteria
- [ ] Configure fallback string inside api.ts.

### Files Likely Affected
- [frontend/src/lib/api.ts](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/frontend/src/lib/api.ts)
