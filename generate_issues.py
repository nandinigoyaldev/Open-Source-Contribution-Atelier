import json
import random

issues = [
    # Frontend (React 19, Tailwind, Vite)
    {"title": "Add skeleton loaders to Dashboard grid", "body": "Currently the dashboard shows a blank screen while loading data. We should add Tailwind skeleton loaders for better UX.", "label": "easy", "type": "feature"},
    {"title": "Fix mobile layout overflow on Community Page", "body": "On screens smaller than 375px, the Community grid overflows the x-axis, causing horizontal scrolling.", "label": "easy", "type": "bug"},
    {"title": "Implement dark mode persistence", "body": "The dark mode toggle works but doesn't persist across page reloads. We should save the user's preference in localStorage.", "label": "easy", "type": "feature"},
    {"title": "Upgrade Vite to latest minor version", "body": "We should keep our build tools up to date to benefit from performance improvements.", "label": "easy", "type": "feature"},
    {"title": "Add unit tests for useWebPush hook", "body": "The useWebPush hook currently lacks unit tests. We should use Vitest and React Testing Library to cover its states.", "label": "medium", "type": "feature"},
    {"title": "Fix accessibility contrast ratio on primary buttons", "body": "The primary blue color on white text fails WCAG AA contrast ratio. We need to slightly darken the blue.", "label": "easy", "type": "bug"},
    {"title": "Implement virtual scrolling for long leaderboards", "body": "When the leaderboard has 1000+ entries, DOM rendering becomes slow. We should implement react-window or tanstack-virtual.", "label": "hard", "type": "feature"},
    {"title": "Refactor organizations grid to use CSS grid instead of flex", "body": "The organizations grid is using complex flex math. It should be refactored to use Tailwind's grid-cols.", "label": "easy", "type": "feature"},
    {"title": "Add i18n support for the landing page", "body": "To reach a wider audience, we should setup react-i18next and extract the landing page strings.", "label": "medium", "type": "feature"},
    {"title": "Fix unhandled promise rejection in ChatContainer", "body": "If the websocket connection fails, the error isn't caught, leading to an unhandled promise rejection in the console.", "label": "medium", "type": "bug"},
    {"title": "Add error boundary to LessonPage", "body": "If a markdown file is malformed, the entire LessonPage crashes. We need a targeted ErrorBoundary.", "label": "easy", "type": "feature"},
    {"title": "Optimize image loading on landing page", "body": "We should use modern formats (WebP) and native lazy loading for images below the fold.", "label": "easy", "type": "feature"},
    {"title": "Create reusable Tooltip component", "body": "We need a standard Tooltip component using Radix UI or pure Tailwind to use across the app.", "label": "easy", "type": "feature"},
    {"title": "Fix stale state in CommandPalette", "body": "When navigating via the CommandPalette, the search term is not cleared upon closing.", "label": "easy", "type": "bug"},
    {"title": "Add E2E tests for the signup flow", "body": "We should add Playwright tests to cover the complete user registration flow including magic links.", "label": "hard", "type": "feature"},
    
    # Backend (Django, DRF)
    {"title": "Fix N+1 query in Dashboard analytics view", "body": "The dashboard API is making N+1 queries when fetching user progress. We should use select_related or prefetch_related.", "label": "medium", "type": "bug"},
    {"title": "Add rate limiting to authentication endpoints", "body": "To prevent brute force attacks, we need to implement Django REST Framework throttling on the login/signup endpoints.", "label": "medium", "type": "feature"},
    {"title": "Implement Celery task for weekly summary emails", "body": "We need a periodic Celery task that gathers user progress and sends out the weekly summary email.", "label": "hard", "type": "feature"},
    {"title": "Add caching to the organizations list API", "body": "The organizations list changes rarely. We should cache this endpoint in Redis for 1 hour.", "label": "easy", "type": "feature"},
    {"title": "Fix timezone handling in UserProfile model", "body": "When saving timezones, the backend sometimes fails to validate against pytz. We should add strict choices.", "label": "medium", "type": "bug"},
    {"title": "Add Swagger/OpenAPI documentation for Chat app", "body": "The Chat API endpoints are missing drf-spectacular decorators for the Swagger documentation.", "label": "easy", "type": "feature"},
    {"title": "Implement fuzzy searching in the Search API", "body": "Currently the search only does exact substring matches. We should use PostgreSQL Trigram similarity for fuzzy matching.", "label": "hard", "type": "feature"},
    {"title": "Fix 500 error when submitting invalid Sandbox code", "body": "If a user submits code with specific syntax errors, the Sandbox verifier throws an unhandled exception.", "label": "medium", "type": "bug"},
    {"title": "Add data export feature for users (GDPR)", "body": "We need an endpoint that aggregates all user data and returns it as a downloadable JSON file.", "label": "medium", "type": "feature"},
    {"title": "Write factory boy factories for the Content app", "body": "Testing the Content app requires complex setup. We should create factory_boy factories to simplify test creation.", "label": "easy", "type": "feature"},
    {"title": "Fix duplicate notifications generation", "body": "Under certain race conditions, the notification signals generate two identical notifications for the same event.", "label": "hard", "type": "bug"},
    {"title": "Add API pagination to webhooks history", "body": "The webhooks history endpoint returns all records, which will eventually cause performance issues. Add PageNumberPagination.", "label": "easy", "type": "feature"},
    {"title": "Implement soft delete for User accounts", "body": "Instead of hard deleting users and cascading everything, implement a soft delete mechanism using an is_deleted flag.", "label": "medium", "type": "feature"},
    {"title": "Upgrade Django to latest security patch", "body": "We need to bump the Django version in requirements.txt to address recent minor security advisories.", "label": "easy", "type": "feature"},
    {"title": "Add Prometheus metrics endpoint", "body": "To monitor backend performance, we should add django-prometheus and expose a /metrics endpoint.", "label": "medium", "type": "feature"},
    {"title": "Fix inconsistent camelCase conversion in API responses", "body": "Some nested JSON objects in the Content API are not being properly converted to camelCase for the frontend.", "label": "medium", "type": "bug"},
    {"title": "Add bulk creation endpoint for Challenges", "body": "Administrators need a way to upload a JSON file to bulk create new coding challenges.", "label": "medium", "type": "feature"},
    {"title": "Refactor signals in Accounts app to use dedicated receivers file", "body": "The signals in the accounts app are scattered. They should be moved to a signals.py file and connected in apps.py.", "label": "easy", "type": "feature"},
    
    # Infrastructure / Docker
    {"title": "Optimize Dockerfile multi-stage build for frontend", "body": "The current frontend Docker build image size is too large. We should use a distroless or alpine runner stage.", "label": "medium", "type": "feature"},
    {"title": "Add healthcheck to Redis service in docker-compose", "body": "The backend sometimes starts before Redis is fully ready. Add a proper healthcheck to the Redis container.", "label": "easy", "type": "bug"},
    {"title": "Implement GitHub Actions workflow for Python formatting", "body": "We have Black locally but no CI check. Add a workflow that fails if the python code isn't formatted.", "label": "easy", "type": "feature"},
    {"title": "Fix missing volume mount for Celery worker", "body": "The Celery worker in docker-compose.yml isn't mounting the codebase, meaning it uses stale code during local dev.", "label": "easy", "type": "bug"},
    
    # Mix / Sandbox / Other
    {"title": "Add syntax highlighting support for Rust in Sandbox", "body": "We want to expand the learning platform to support Rust. Add the necessary verifier and frontend syntax highlighting.", "label": "hard", "type": "feature"},
    {"title": "Fix markdown parsing of tables in lessons", "body": "Complex markdown tables in the curriculum are rendering incorrectly in the frontend MarkdownRenderer.", "label": "medium", "type": "bug"},
    {"title": "Implement achievement badges system", "body": "Create the backend models and frontend UI to award users badges (e.g. 'First PR', '7 Day Streak').", "label": "hard", "type": "feature"},
    {"title": "Add copy to clipboard button on code blocks", "body": "All code blocks in the lessons should have a small 'Copy' icon in the top right corner.", "label": "easy", "type": "feature"},
    {"title": "Fix scroll position jumping when navigating between lessons", "body": "When clicking 'Next Lesson', the page scroll position is retained instead of scrolling to the top.", "label": "easy", "type": "bug"},
    {"title": "Add search analytics tracking", "body": "We should track what terms users are searching for to identify missing curriculum content.", "label": "medium", "type": "feature"},
    {"title": "Implement offline mode using Service Workers", "body": "Make the core curriculum available offline by aggressively caching /content/ requests in the service worker.", "label": "hard", "type": "feature"},
    {"title": "Fix focus trap in generic Modal component", "body": "When a modal is open, users can still tab to elements behind it. Implement a proper focus trap.", "label": "medium", "type": "bug"},
    {"title": "Add visual progress bar to the top of the window", "body": "As users scroll through a long lesson, a thin progress bar at the top should indicate how far they are.", "label": "easy", "type": "feature"},
    {"title": "Refactor ProfileSettingsForm to use react-hook-form", "body": "The profile settings form is using manual state management. Migrate it to react-hook-form + zod.", "label": "medium", "type": "feature"},
    {"title": "Add webhook retries with exponential backoff", "body": "If a webhook delivery fails, the backend should retry up to 3 times with exponential backoff.", "label": "hard", "type": "feature"},
    {"title": "Fix z-index collision on mobile navigation menu", "body": "The mobile hamburger menu sometimes appears behind the Markdown content's sticky headers.", "label": "easy", "type": "bug"},
    {"title": "Add feature flags system", "body": "We need a simple mechanism (database table + context processor) to toggle features on/off without deploying.", "label": "medium", "type": "feature"}
]

with open('issues.json', 'w') as f:
    json.dump(issues, f, indent=2)
print(f"Generated {len(issues)} issues.")
