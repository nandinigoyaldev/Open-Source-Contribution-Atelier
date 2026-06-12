# Refactor LessonProgress Model to Record Attempt Counter Stats

- **Difficulty**: Medium
- **Category**: Content System
- **Beginner Friendliness**: No, database migration focus.

---

### Description
We need to track user attempts before getting a lesson correct. Add an attempt counter field.

### Expected Outcome
A counter field incrementing on every progress post check.

### Acceptance Criteria
- [ ] Add field attempt_count to LessonProgress model.
- [ ] Increment and migrate Django db configuration.

### Files Likely Affected
- [backend/apps/progress/models.py](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/backend/apps/progress/models.py)
- [backend/apps/progress/views.py](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/backend/apps/progress/views.py)
