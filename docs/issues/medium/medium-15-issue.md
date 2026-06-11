# Create Database Index on LessonProgress user and lesson ID fields

- **Difficulty**: Medium
- **Category**: Performance
- **Beginner Friendliness**: No, Django models indices.

---

### Description
Retrieving progress queries filters on user IDs. Add explicit indexes to database fields to speed up queries.

### Expected Outcome
Faster dashboard load query times.

### Acceptance Criteria
- [ ] Configure unique index schemas inside LessonProgress model Meta.

### Files Likely Affected
- [backend/apps/progress/models.py](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/backend/apps/progress/models.py)
