# Architecture Notes

## Backend

- `accounts`: users, profiles, auth helpers
- `content`: lessons and exercises
- `progress`: achievements, progress snapshots, recommendations
- `challenges`: challenge catalog, submissions, score events
- `sandbox`: safe command verification engine for interactive Git exercises

## Frontend

- Marketing-first landing page
- Auth flows
- Dashboard and community metrics
- Lesson detail pages with terminal practice panel
- Challenge center and leaderboard pages

## Safety

Exercise verification accepts only known Git-learning commands and validates them against expected patterns and state transitions.

