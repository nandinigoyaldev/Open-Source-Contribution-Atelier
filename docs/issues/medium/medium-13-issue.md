# Add aria-live Speech Screen Reader Labels to Quiz Alert Blocks

- **Difficulty**: Medium
- **Category**: Accessibility
- **Beginner Friendliness**: Yes, accessibility enhancement.

---

### Description
When checking quiz answers, screen readers miss the immediate feedback labels. Install aria-live tags.

### Expected Outcome
Screen readers read correct/incorrect announcements immediately.

### Acceptance Criteria
- [ ] Use aria-live='assertive' or role='alert' on feedback elements in LessonPage.tsx.

### Files Likely Affected
- [frontend/src/pages/LessonPage.tsx](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/frontend/src/pages/LessonPage.tsx)
