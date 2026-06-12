import os

ISSUES = [
    # --- EASY ISSUES (20) ---
    {
        "id": "easy-1",
        "title": "Fix Typo in Project README.md Description",
        "difficulty": "Easy",
        "category": "Documentation",
        "description": "The main project README.md file contains several minor typographical errors in the Stack and Role-Based Dashboard descriptions.",
        "outcome": "A clean, grammatically correct README.md description.",
        "criteria": [
            "Inspect README.md and correct any spelling and grammar errors.",
            "Maintain the existing markdown layout format and shields structure."
        ],
        "files": ["README.md"],
        "beginner_friendly": "Yes, suitable for first-time open source contributors."
    },
    {
        "id": "easy-2",
        "title": "Add Hover Micro-Animations to Side Navigation Menu Items",
        "difficulty": "Easy",
        "category": "UI/UX",
        "description": "Navigation sidebar items feel flat. Add subtle scale transitions and shadow shifts when hovering over sidebar links.",
        "outcome": "Smooth transition effects on navigation items matching the neobrutalist visual identity.",
        "criteria": [
            "Add CSS classes or Tailwind styles to Navigation.tsx.",
            "Include scale-102 and shadow-card hover states.",
            "Verify transition is smooth (150ms-200ms ease)."
        ],
        "files": ["frontend/src/components/layout/Navigation.tsx"],
        "beginner_friendly": "Yes, great beginner frontend styling issue."
    },
    {
        "id": "easy-3",
        "title": "Implement Accessibility aria-labels on Light/Dark Mode Switcher",
        "difficulty": "Easy",
        "category": "Accessibility",
        "description": "The theme toggler button lack descriptive labels, making it hard for screen readers to explain what it does.",
        "outcome": "Proper aria-labels that reflect the current active theme.",
        "criteria": [
            "Add aria-label to the theme toggle button in Navigation.tsx.",
            "The label should change from 'Switch to dark mode' to 'Switch to light mode' dynamically."
        ],
        "files": ["frontend/src/components/layout/Navigation.tsx"],
        "beginner_friendly": "Yes, ideal accessibility intro task."
    },
    {
        "id": "easy-4",
        "title": "Add SEO Metadata Meta Tags to index.html Template",
        "difficulty": "Easy",
        "category": "Deployment",
        "description": "The primary frontend entry point lacks basic search engine meta elements (like meta description, viewport, and keywords).",
        "outcome": "Index page populated with standard SEO tag records.",
        "criteria": [
            "Insert description and keywords meta tags in frontend/index.html header.",
            "Add Open Graph meta tags (og:title, og:description, og:image) for link previews."
        ],
        "files": ["frontend/index.html"],
        "beginner_friendly": "Yes, basic HTML issue."
    },
    {
        "id": "easy-5",
        "title": "Refactor Staging Sandbox Terminal Placeholder Text",
        "difficulty": "Easy",
        "category": "Frontend",
        "description": "The input placeholder in the Sandbox terminal panel should tell the user what command category they should focus on.",
        "outcome": "Informative placeholder text inside the sandbox terminal input.",
        "criteria": [
            "Modify the placeholder of input element in LessonPage.tsx to dynamically output help context if available."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "Yes, simple JSX change."
    },
    {
        "id": "easy-6",
        "title": "Add API Unit Test for Accounts MeView Endpoint",
        "difficulty": "Easy",
        "category": "Testing",
        "description": "The current account information endpoint (/api/auth/me/) does not have dedicated unit tests verifying token authorization responses.",
        "outcome": "A unit test confirming the endpoint returns 200 for validated users and 401 for anonymous hits.",
        "criteria": [
            "Create a test case in backend/tests/test_auth_and_sandbox.py called test_me_endpoint.",
            "Assert correct JSON payload fields: id, username, email, is_staff."
        ],
        "files": ["backend/tests/test_auth_and_sandbox.py"],
        "beginner_friendly": "Yes, great introduction to Django rest testing."
    },
    {
        "id": "easy-7",
        "title": "Create Pull Request Template inside .github/ Folder",
        "difficulty": "Easy",
        "category": "Open Source Experience",
        "description": "Contributors submit PRs with varying formats. A unified PULL_REQUEST_TEMPLATE.md is required to clean up code reviews.",
        "outcome": "An active Pull Request template that pre-fills description checklists on GitHub.",
        "criteria": [
            "Create .github/PULL_REQUEST_TEMPLATE.md containing summary, related issues, and testing checklists."
        ],
        "files": [".github/PULL_REQUEST_TEMPLATE.md"],
        "beginner_friendly": "Yes, documentation and configuration issue."
    },
    {
        "id": "easy-8",
        "title": "Fix ESLint Warning Regarding Unused Import Declarations",
        "difficulty": "Easy",
        "category": "Frontend",
        "description": "The React routing file has several imported modules that are not used, throwing warnings during the build step.",
        "outcome": "Zero ESLint warnings in compile console log logs.",
        "criteria": [
            "Scan frontend files (especially router.tsx) and remove unused imports."
        ],
        "files": ["frontend/src/app/router.tsx"],
        "beginner_friendly": "Yes, simple cleanup task."
    },
    {
        "id": "easy-9",
        "title": "Format Mentor Response SLA SLA Metric with User Local Timezone",
        "difficulty": "Easy",
        "category": "UI/UX",
        "description": "The SLA metrics represent hardcoded text values. Adapt the visual render to state standard time zones.",
        "outcome": "Localized timezone display next to SLA numbers.",
        "criteria": [
            "Detect local user timezone inside CommunityPage.tsx.",
            "Display timezone string (e.g., IST, EST) next to the metric."
        ],
        "files": ["frontend/src/pages/CommunityPage.tsx"],
        "beginner_friendly": "Yes, minor JS enhancement."
    },
    {
        "id": "easy-10",
        "title": "Update CONTRIBUTING.md Guidelines with Lint Checklist Pointers",
        "difficulty": "Easy",
        "category": "Documentation",
        "description": "Contributors are unaware they need to run formatting tools locally. Add clear commands for lint verification.",
        "outcome": "Clear instructions in CONTRIBUTING.md detailing npm run format and npm run lint.",
        "criteria": [
            "Document the linting commands inside CONTRIBUTING.md.",
            "Verify links point to the correct sections."
        ],
        "files": ["CONTRIBUTING.md"],
        "beginner_friendly": "Yes, documentation-only change."
    },
    {
        "id": "easy-11",
        "title": "Create a Floating Scroll-to-Top Button on the Dashboard",
        "difficulty": "Easy",
        "category": "UI/UX",
        "description": "The dashboard page grows long when populated with multiple cards and timelines. Add a neobrutalist floating scroll-to-top button.",
        "outcome": "A responsive scroll-to-top button that appears when scrolling down.",
        "criteria": [
            "Add button that appears after scrolling 300px.",
            "Smooth scroll window to top upon clicking.",
            "Style button with neobrutalist thick borders."
        ],
        "files": ["frontend/src/pages/DashboardPage.tsx"],
        "beginner_friendly": "Yes, standard CSS/JS issue."
    },
    {
        "id": "easy-12",
        "title": "Create Documentation Suggestion Issue Template",
        "difficulty": "Easy",
        "category": "Open Source Experience",
        "description": "Newcomers often find typos in docs. Create a dedicated issue template for documentation corrections.",
        "outcome": "A .github/ISSUE_TEMPLATE/docs_suggestion.md template configuration.",
        "criteria": [
            "Create issue template detailing title, files affected, and suggested edits."
        ],
        "files": [".github/ISSUE_TEMPLATE/docs_suggestion.md"],
        "beginner_friendly": "Yes, configuration issue."
    },
    {
        "id": "easy-13",
        "title": "Highlight Active Module Directory Item in Sidebar Outline",
        "difficulty": "Easy",
        "category": "UI/UX",
        "description": "The course sidebar highlights active lessons, but the module parent header looks unselected. Add dynamic active header colors.",
        "outcome": "Module header background highlights when any child lesson is currently active.",
        "criteria": [
            "Determine active module in LessonPage.tsx.",
            "Add background color or custom borders to active module blocks in sidebar."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "Yes, frontend styling."
    },
    {
        "id": "easy-14",
        "title": "Add CSS print Rules to Hide Navigation when Printing Certificates",
        "difficulty": "Easy",
        "category": "Performance",
        "description": "When a user prints a certificate of completion, the dashboard sidebar and header are included, spoiling the formatting.",
        "outcome": "A print-safe certificate view where only the certificate card is rendered.",
        "criteria": [
            "Use CSS print media query (@media print) inside styles.css.",
            "Hide nav sidebar, header, and backdrops when printing is triggered."
        ],
        "files": ["frontend/src/styles.css"],
        "beginner_friendly": "Yes, straightforward CSS."
    },
    {
        "id": "easy-15",
        "title": "Keyboard Accessibility: Submit Terminal Checks on Cmd+Enter",
        "difficulty": "Easy",
        "category": "Accessibility",
        "description": "Clicking the 'Run' button manually is tedious. Enable Cmd+Enter or Ctrl+Enter keyboard listener inside the terminal input form.",
        "outcome": "User can execute and check terminal inputs via keyboard shortcuts.",
        "criteria": [
            "Add onKeyDown event handler to the terminal input in LessonPage.tsx.",
            "Listen for Meta/Control and Enter keys to trigger command runs."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "Yes, event-handling introduction."
    },
    {
        "id": "easy-16",
        "title": "Enforce cursor-pointer Style Feedback on Neobrutalist Cards",
        "difficulty": "Easy",
        "category": "UI/UX",
        "description": "Interactive neobrutalist cards (like resume catalog elements) look clickable but maintain the default text cursor.",
        "outcome": "Pointer cursor feedback on hover across all dashboard cards.",
        "criteria": [
            "Add cursor-pointer classes to interactive Link elements in DashboardPage.tsx."
        ],
        "files": ["frontend/src/pages/DashboardPage.tsx"],
        "beginner_friendly": "Yes, quick CSS fix."
    },
    {
        "id": "easy-17",
        "title": "Fix Typographical Errors in Staging and Commit Markdown Lessons",
        "difficulty": "Easy",
        "category": "Content System",
        "description": "The markdown files inside Module 2 contain minor spelling errors (e.g. 'stageing', 'imperatve').",
        "outcome": "Spelling corrected across all static assets.",
        "criteria": [
            "Check public/content/module-2 files.",
            "Fix spelling errors."
        ],
        "files": ["frontend/public/content/module-2/git-workflow.md", "frontend/public/content/module-2/repositories-and-commits.md"],
        "beginner_friendly": "Yes, content typo fix."
    },
    {
        "id": "easy-18",
        "title": "Validate Email Input Format on Signup Form Frontend",
        "difficulty": "Easy",
        "category": "Authentication",
        "description": "The signup page allows submitting invalid emails without warnings, causing backend validation failures.",
        "outcome": "Validation checks and error labels on client-side signup inputs.",
        "criteria": [
            "Use email regex validation inside SignupPage.tsx.",
            "Display an input validation warning if the email format is invalid."
        ],
        "files": ["frontend/src/pages/SignupPage.tsx"],
        "beginner_friendly": "Yes, standard form validation."
    },
    {
        "id": "easy-19",
        "title": "Display Visual Lock Icon Next to Unearned Badge Achievements",
        "difficulty": "Easy",
        "category": "Gamification",
        "description": "Locked achievements look faded, but showing a lock symbol next to the badge icon would clarify locked state.",
        "outcome": "A locked padlock symbol overlaid on locked badges.",
        "criteria": [
            "Display a lock icon (from lucide-react) inside DashboardPage badge grid if isEarned is false."
        ],
        "files": ["frontend/src/pages/DashboardPage.tsx"],
        "beginner_friendly": "Yes, gamification UI tweak."
    },
    {
        "id": "easy-20",
        "title": "Add Warning Callouts about Local OAuth Configuration in Setup Docs",
        "difficulty": "Easy",
        "category": "Documentation",
        "description": "Many newcomers get stuck on OAuth errors because their VITE_GOOGLE_CLIENT_ID env variable is not configured. Add warning logs.",
        "outcome": "An informative note in README.md explaining how to obtain credentials.",
        "criteria": [
            "Add step-by-step instructions to create OAuth IDs inside README.md."
        ],
        "files": ["README.md"],
        "beginner_friendly": "Yes, documentation task."
    },

    # --- MEDIUM ISSUES (20) ---
    {
        "id": "medium-1",
        "title": "Build Search and Category Filtering on Challenges Page",
        "difficulty": "Medium",
        "category": "Frontend",
        "description": "The challenges board lists drills but lacks search inputs. Build frontend-driven filters to slice drills by difficulty.",
        "outcome": "An active search input and dropdown filter in ChallengePage.",
        "criteria": [
            "Implement search input filtering challenges list dynamically.",
            "Add difficulty category selectors (beginner, intermediate, advanced)."
        ],
        "files": ["frontend/src/pages/ChallengePage.tsx"],
        "beginner_friendly": "Yes, standard React filtering."
    },
    {
        "id": "medium-2",
        "title": "Create Dynamic XP Counter Ticker Animation",
        "difficulty": "Medium",
        "category": "Gamification",
        "description": "When loading the dashboard, the contributor XP jumps immediately. Add a neat count-up animation to make dashboard loads engaging.",
        "outcome": "An XP counter that smoothly increments from 0 to target on load.",
        "criteria": [
            "Implement count-up interval script in DashboardPage.",
            "Ensure animation doesn't cause browser frame lags."
        ],
        "files": ["frontend/src/pages/DashboardPage.tsx"],
        "beginner_friendly": "Yes, advanced styling and logic."
    },
    {
        "id": "medium-3",
        "title": "Create GitHub Actions CI Script to Run Formatting Checks on Pushes",
        "difficulty": "Medium",
        "category": "Deployment",
        "description": "The repo has checks for tests, but linting checking is missing. Setup a Prettier/ESLint checking task in GitHub workflows.",
        "outcome": "A failing workflow run if code formatting violates rules.",
        "criteria": [
            "Add formatting check steps inside .github/workflows/ci.yml.",
            "Ensure lint check runs on Node environment."
        ],
        "files": [".github/workflows/ci.yml"],
        "beginner_friendly": "No, requires CI config knowledge."
    },
    {
        "id": "medium-4",
        "title": "Add API Tests for Dynamic Lesson Stub Creation in progress views",
        "difficulty": "Medium",
        "category": "Testing",
        "description": "We added dynamic lesson registrations. Create tests verifying placeholder lesson creations.",
        "outcome": "A Django test suite validating that post requests create lesson database instances.",
        "criteria": [
            "Write pytest methods in backend tests.",
            "Assert created database attributes match expected stubs."
        ],
        "files": ["backend/tests/test_auth_and_sandbox.py"],
        "beginner_friendly": "Yes, testing focus."
    },
    {
        "id": "medium-5",
        "title": "Implement LocalStorage Caching Fallback for GitHub Contributors API",
        "difficulty": "Medium",
        "category": "GitHub Integration",
        "description": "The GitHub contributors API has an hourly rate limit of 60 hits for unauthenticated calls. Cache results locally.",
        "outcome": "Page loads details from LocalStorage cache if API call fails.",
        "criteria": [
            "Implement caching logic in DashboardPage.",
            "Store results with a 24-hour expiration token."
        ],
        "files": ["frontend/src/pages/DashboardPage.tsx"],
        "beginner_friendly": "Yes, data parsing."
    },
    {
        "id": "medium-6",
        "title": "Build a Neobrutalist Modal Window for Logout Confirmation",
        "difficulty": "Medium",
        "category": "UI/UX",
        "description": "Clicking logout instantly signs the user out. Build a confirmation modal with neobrutalist borders.",
        "outcome": "A confirmation modal before executing logouts.",
        "criteria": [
            "Show modal dialog on logout click.",
            "Add 'Cancel' and 'Confirm' buttons styled with bold neobrutalist aesthetics."
        ],
        "files": ["frontend/src/components/layout/Navigation.tsx"],
        "beginner_friendly": "Yes, React state handler."
    },
    {
        "id": "medium-7",
        "title": "Build a Quiz Analytics Logger Endpoint on Django Backend",
        "difficulty": "Medium",
        "category": "Content System",
        "description": "Track which quiz questions are most challenging. Build a logging endpoint to track student answers.",
        "outcome": "A API endpoint accepting logs of failed/correct quiz attempts.",
        "criteria": [
            "Create a model QuizAttempt in backend.",
            "Expose POST endpoint /api/progress/quiz-attempts/."
        ],
        "files": ["backend/apps/progress/models.py", "backend/apps/progress/views.py"],
        "beginner_friendly": "No, Django developer task."
    },
    {
        "id": "medium-8",
        "title": "Add Password Strength Indicator UI Feedback on Signup Page",
        "difficulty": "Medium",
        "category": "Authentication",
        "description": "Users sign up using weak passwords. Add a dynamic strength estimator bar on frontend.",
        "outcome": "Visual color bars (weak, medium, strong) based on password complexity.",
        "criteria": [
            "Add strength meter bar under signup password inputs.",
            "Check length, symbols, numbers, and toggle colors dynamically."
        ],
        "files": ["frontend/src/pages/SignupPage.tsx"],
        "beginner_friendly": "Yes, frontend logic."
    },
    {
        "id": "medium-9",
        "title": "Build a Mobile Navigation Drawer Layout for Sidebar Outline",
        "difficulty": "Medium",
        "category": "UI/UX",
        "description": "The course sidebar on mobile gets cut off. Build a neat sliding drawer layout that handles outline directory clicks.",
        "outcome": "A smooth slide-in sidebar outline drawer on mobile views.",
        "criteria": [
            "Refactor responsive sidebar trigger states in LessonPage.tsx.",
            "Ensure drawer closes upon click outs."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "Yes, layout focus."
    },
    {
        "id": "medium-10",
        "title": "Setup Swagger OpenAPI Documentation Schema Configurations",
        "difficulty": "Medium",
        "category": "Documentation",
        "description": "The project uses drf-spectacular but lacks specific view schemas. Annotate APIs with details.",
        "outcome": "Interactive swagger pages displaying correct payload parameters.",
        "criteria": [
            "Add extend_schema decorators to accounts/views.py.",
            "Document progress view models."
        ],
        "files": ["backend/apps/accounts/views.py", "backend/apps/progress/views.py"],
        "beginner_friendly": "No, DRF schema knowledge."
    },
    {
        "id": "medium-11",
        "title": "Refactor LessonProgress Model to Record Attempt Counter Stats",
        "difficulty": "Medium",
        "category": "Content System",
        "description": "We need to track user attempts before getting a lesson correct. Add an attempt counter field.",
        "outcome": "A counter field incrementing on every progress post check.",
        "criteria": [
            "Add field attempt_count to LessonProgress model.",
            "Increment and migrate Django db configuration."
        ],
        "files": ["backend/apps/progress/models.py", "backend/apps/progress/views.py"],
        "beginner_friendly": "No, database migration focus."
    },
    {
        "id": "medium-12",
        "title": "Build a Custom Hook for LocalStorage Progress Synchronizations",
        "difficulty": "Medium",
        "category": "Frontend",
        "description": "Progress is loaded directly. Create a useLocalSync hook to manage backup operations.",
        "outcome": "Encapsulated logic syncing localStorage and REST states.",
        "criteria": [
            "Create useLocalSync.ts inside frontend hooks.",
            "Wired hooks into progress contexts."
        ],
        "files": ["frontend/src/hooks/useUserProgress.ts"],
        "beginner_friendly": "Yes, React architecture."
    },
    {
        "id": "medium-13",
        "title": "Add aria-live Speech Screen Reader Labels to Quiz Alert Blocks",
        "difficulty": "Medium",
        "category": "Accessibility",
        "description": "When checking quiz answers, screen readers miss the immediate feedback labels. Install aria-live tags.",
        "outcome": "Screen readers read correct/incorrect announcements immediately.",
        "criteria": [
            "Use aria-live='assertive' or role='alert' on feedback elements in LessonPage.tsx."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "Yes, accessibility enhancement."
    },
    {
        "id": "medium-14",
        "title": "Implement Shake Animation and Red Borders on Sandbox Terminal Errors",
        "difficulty": "Medium",
        "category": "UI/UX",
        "description": "If a user enters an incorrect Git command, the terminal feedback is static. Add a playful shake animation to the terminal container.",
        "outcome": "The input terminal container shakes when error feedback is triggered.",
        "criteria": [
            "Add custom CSS keyframes for shake animations.",
            "Trigger shake state inside LessonPage.tsx when feedback is 'error'."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx", "frontend/src/styles.css"],
        "beginner_friendly": "Yes, frontend anim focus."
    },
    {
        "id": "medium-15",
        "title": "Create Database Index on LessonProgress user and lesson ID fields",
        "difficulty": "Medium",
        "category": "Performance",
        "description": "Retrieving progress queries filters on user IDs. Add explicit indexes to database fields to speed up queries.",
        "outcome": "Faster dashboard load query times.",
        "criteria": [
            "Configure unique index schemas inside LessonProgress model Meta."
        ],
        "files": ["backend/apps/progress/models.py"],
        "beginner_friendly": "No, Django models indices."
    },
    {
        "id": "medium-16",
        "title": "Add Unit Tests verifying SimpleJWT Refresh Token Lifespans",
        "difficulty": "Medium",
        "category": "Testing",
        "description": "We need to verify refresh actions. Build tests verifying refresh tokens work.",
        "outcome": "Pytest logs checking token creations and updates.",
        "criteria": [
            "Verify /api/auth/token/refresh/ returns valid access tokens."
        ],
        "files": ["backend/tests/test_auth_and_sandbox.py"],
        "beginner_friendly": "Yes, testing focus."
    },
    {
        "id": "medium-17",
        "title": "Display Active GitHub Organizations Grid on Landing Gates",
        "difficulty": "Medium",
        "category": "UI/UX",
        "description": "Introduce student learners to organizational structures. Display a grid of top open source organization logos on the login page.",
        "outcome": "A beautiful, hoverable organization grid at the bottom of the Landing Page.",
        "criteria": [
            "Add styled card elements for organizations like Apache, CNCF, and Linux Foundation."
        ],
        "files": ["frontend/src/pages/LandingPage.tsx"],
        "beginner_friendly": "Yes, styling component."
    },
    {
        "id": "medium-18",
        "title": "Create a Cleanup Script for Obsolete Docker Volumes",
        "difficulty": "Medium",
        "category": "Deployment",
        "description": "Local development accumulates massive docker volumes. Build a simple script pruning redundant containers.",
        "outcome": "A scripts/clean_docker.sh script deleting obsolete volumes.",
        "criteria": [
            "Provide options clearing dev db states."
        ],
        "files": ["scripts/clean_docker.sh"],
        "beginner_friendly": "Yes, scripts/shell focus."
    },
    {
        "id": "medium-19",
        "title": "Build Dynamic Completion Graphs inside Mobile Dashboard views",
        "difficulty": "Medium",
        "category": "UI/UX",
        "description": "Recharts pie graphs are cut off on small viewports. Resize circular progress gauges inside mobile screens.",
        "outcome": "Adaptive circular gauges resizing dynamically using CSS.",
        "criteria": [
            "Wired ResponsiveContainer to adapt sizes on breakpoints inside DashboardPage."
        ],
        "files": ["frontend/src/pages/DashboardPage.tsx"],
        "beginner_friendly": "Yes, responsive layout."
    },
    {
        "id": "medium-20",
        "title": "Implement Automatic API Fallback if VITE_API_BASE_URL is blank",
        "difficulty": "Medium",
        "category": "Deployment",
        "description": "If the base URL is unset, the app breaks. Fallback dynamically to the browser origin.",
        "outcome": "App guesses backend route using host mappings.",
        "criteria": [
            "Configure fallback string inside api.ts."
        ],
        "files": ["frontend/src/lib/api.ts"],
        "beginner_friendly": "Yes, environment fix."
    },

    # --- HARD ISSUES (10) ---
    {
        "id": "hard-1",
        "title": "Implement Complete GitHub OAuth2 Authorization Flow",
        "difficulty": "Hard",
        "category": "Authentication",
        "description": "GitHub OAuth callbacks are defined but OAuth flow needs complete backend verification wiring.",
        "outcome": "Secure registration and token assignments using GitHub credentials.",
        "criteria": [
            "Setup OAuth verification handlers in accounts/views.py.",
            "Verify token exchanges and user lookup registrations."
        ],
        "files": ["backend/apps/accounts/views.py"],
        "beginner_friendly": "No, secure auth architecture."
    },
    {
        "id": "hard-2",
        "title": "Build a WebAssembly-based Git Terminal Sandbox Shell Mock",
        "difficulty": "Hard",
        "category": "Open Source Experience",
        "description": "The current terminal validates inputs against exact matching rules. Build a local git shell simulation utilizing WebAssembly.",
        "outcome": "A browser terminal allowing users to run git init and actually inspect files.",
        "criteria": [
            "Integrate a micro Git shell inside client pages.",
            "Validate state transitions dynamically."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "No, WebAssembly integration."
    },
    {
        "id": "hard-3",
        "title": "Implement Service Worker Progress Syncing Queue for Offline Mode",
        "difficulty": "Hard",
        "category": "Performance",
        "description": "Offline students lose completed status. Build a service worker queue syncing localstorage actions once the browser regains connections.",
        "outcome": "Automatic backend syncs when network connection resumes.",
        "criteria": [
            "Implement sync background queues.",
            "Verify no duplicated records occur."
        ],
        "files": ["frontend/src/main.tsx"],
        "beginner_friendly": "No, Service Worker architecture."
    },
    {
        "id": "hard-4",
        "title": "Build public Certificate Verification Validation Lookup Page",
        "difficulty": "Hard",
        "category": "Frontend",
        "description": "Certificates can be printed locally. Build a public lookup page allowing recruiters to query hashes and verify certificate completion.",
        "outcome": "A public route validating verification code hashes against database records.",
        "criteria": [
            "Create route /verify/:hash on frontend.",
            "Expose verification REST APIs backend-side."
        ],
        "files": ["frontend/src/app/router.tsx", "backend/apps/progress/views.py"],
        "beginner_friendly": "No, fullstack feature."
    },
    {
        "id": "hard-5",
        "title": "Implement Django Channels Websockets for Live Cohort Leaderboard Updates",
        "difficulty": "Hard",
        "category": "GitHub Integration",
        "description": "Leaderboards are polled. Implement websocket notifications pushed from the server when users complete lessons.",
        "outcome": "Real-time updates on the leaderboard page without reloads.",
        "criteria": [
            "Setup Django channels websocket configuration.",
            "Establish frontend listener hooks."
        ],
        "files": ["backend/config/asgi.py", "frontend/src/pages/CommunityPage.tsx"],
        "beginner_friendly": "No, websockets/channels focus."
    },
    {
        "id": "hard-6",
        "title": "Setup Automated Visual Regression Test Suite using Playwright",
        "difficulty": "Hard",
        "category": "Testing",
        "description": "The frontend lacks integration tests. Build play-wright visual testing suites validating layouts.",
        "outcome": "CI workflows executing visual layout reviews on push.",
        "criteria": [
            "Install playwright configs inside frontend.",
            "Establish screenshots comparison baselines."
        ],
        "files": ["frontend/package.json"],
        "beginner_friendly": "No, integration testing architecture."
    },
    {
        "id": "hard-7",
        "title": "Build Dynamic Badges Awards Evaluation Engine Rules",
        "difficulty": "Hard",
        "category": "Gamification",
        "description": "Badges are evaluated client-side. Migrate badge awards evaluation to a robust backend rule engine validator.",
        "outcome": "Database-triggered badge unlocks based on completed lesson statistics.",
        "criteria": [
            "Implement BadgeEvaluator engine in backend.",
            "Emit badge earned notifications upon lesson completion saves."
        ],
        "files": ["backend/apps/progress/models.py", "backend/apps/progress/views.py"],
        "beginner_friendly": "No, rules engine architecture."
    },
    {
        "id": "hard-8",
        "title": "Build Vector-based Semantic Search inside Curriculum catalog",
        "difficulty": "Hard",
        "category": "Performance",
        "description": "Simple string matches are inaccurate. Setup semantic search utilizing pgvector or local transformer models.",
        "outcome": "Search inputs fetching conceptual matches (e.g. searching 'push code' returns 'Remotes').",
        "criteria": [
            "Build semantic search routing queries.",
            "Maintain fast execution times."
        ],
        "files": ["backend/apps/content/views.py"],
        "beginner_friendly": "No, AI/Vector index database integration."
    },
    {
        "id": "hard-9",
        "title": "Implement Multi-tenant Scope boundaries for Cohort Mentors Support",
        "difficulty": "Hard",
        "category": "Authentication",
        "description": "Mentors should only review support cases in assigned modules. Implement mentor scope permissions.",
        "outcome": "Mentors can only access support tickets within assigned modules.",
        "criteria": [
            "Configure role mappings in Django models.",
            "Verify security scope limits inside progress views."
        ],
        "files": ["backend/apps/progress/views.py"],
        "beginner_friendly": "No, authorization scopes."
    },
    {
        "id": "hard-10",
        "title": "Design Advanced Staging Interactive git Merge Conflict Sandbox UI",
        "difficulty": "Hard",
        "category": "Frontend",
        "description": "The current terminal interface validates simple strings. Design an interactive graph representation of overlapping branches.",
        "outcome": "Visual visual nodes representing master/feature tree states.",
        "criteria": [
            "Embed dynamic SVG/Canvas timeline graphs.",
            "Show conflict boundaries when staging overlaps."
        ],
        "files": ["frontend/src/pages/LessonPage.tsx"],
        "beginner_friendly": "No, SVG graph rendering."
    }
]

def generate_issues():
    base_dir = "/Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/docs/issues"
    
    # Create directories if they do not exist
    os.makedirs(f"{base_dir}/easy", exist_ok=True)
    os.makedirs(f"{base_dir}/medium", exist_ok=True)
    os.makedirs(f"{base_dir}/hard", exist_ok=True)

    print("Generating issue files...")

    # Write issue files
    for issue in ISSUES:
        diff_lower = issue["difficulty"].lower()
        filepath = f"{base_dir}/{diff_lower}/{issue['id']}-issue.md"
        
        criteria_list = "\n".join([f"- [ ] {c}" for c in issue["criteria"]])
        files_list = "\n".join([f"- [{f}](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/{f})" for f in issue["files"]])
        
        md_content = f"""# {issue['title']}

- **Difficulty**: {issue['difficulty']}
- **Category**: {issue['category']}
- **Beginner Friendliness**: {issue['beginner_friendly']}

---

### Description
{issue['description']}

### Expected Outcome
{issue['outcome']}

### Acceptance Criteria
{criteria_list}

### Files Likely Affected
{files_list}
"""
        with open(filepath, "w") as f:
            f.write(md_content)
        print(f"Created: {filepath}")

    # Generate ISSUE_INDEX.md
    index_path = f"{base_dir}/ISSUE_INDEX.md"
    
    easy_links = []
    medium_links = []
    hard_links = []
    
    for issue in ISSUES:
        diff_lower = issue["difficulty"].lower()
        rel_link = f"./{diff_lower}/{issue['id']}-issue.md"
        line = f"| {issue['id']} | [{issue['title']}]({rel_link}) | {issue['category']} | {issue['difficulty']} |"
        
        if diff_lower == "easy":
            easy_links.append(line)
        elif diff_lower == "medium":
            medium_links.append(line)
        else:
            hard_links.append(line)

    easy_joined = "\n".join(easy_links)
    medium_joined = "\n".join(medium_links)
    hard_joined = "\n".join(hard_links)

    index_content = f"""# SSOC 2026 Contributor Issues Index

Welcome, SSOC 2026 contributors! Below is the curated list of 50 issues designed for various skill levels.

---

## Easy Issues (20)
| ID | Issue Title | Category | Difficulty |
| :--- | :--- | :--- | :--- |
{easy_joined}

---

## Medium Issues (20)
| ID | Issue Title | Category | Difficulty |
| :--- | :--- | :--- | :--- |
{medium_joined}

---

## Hard Issues (10)
| ID | Issue Title | Category | Difficulty |
| :--- | :--- | :--- | :--- |
{hard_joined}
"""

    with open(index_path, "w") as f:
        f.write(index_content)
    print(f"Created Index: {index_path}")

if __name__ == "__main__":
    generate_issues()
