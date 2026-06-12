# Build Dynamic Badges Awards Evaluation Engine Rules

- **Difficulty**: Hard
- **Category**: Gamification
- **Beginner Friendliness**: No, rules engine architecture.

---

### Description
Badges are evaluated client-side. Migrate badge awards evaluation to a robust backend rule engine validator.

### Expected Outcome
Database-triggered badge unlocks based on completed lesson statistics.

### Acceptance Criteria
- [ ] Implement BadgeEvaluator engine in backend.
- [ ] Emit badge earned notifications upon lesson completion saves.

### Files Likely Affected
- [backend/apps/progress/models.py](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/backend/apps/progress/models.py)
- [backend/apps/progress/views.py](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/backend/apps/progress/views.py)
