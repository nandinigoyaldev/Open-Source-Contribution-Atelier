import json
import logging
from typing import Any, Dict, List

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.content.models import Exercise, Lesson

logger = logging.getLogger(__name__)

CURRICULUM_LESSONS: List[Dict[str, Any]] = [
    # =========================================================================
    # LEVEL 1: WHAT IS OPEN SOURCE?
    # =========================================================================
    {
        "slug": "level-1-what-is-open-source",
        "category": "Level 1 — What is Open Source?",
        "difficulty": "beginner",
        "title": "Demystifying Open Source & Roles",
        "summary": "Understand what open source software means, how collaboration functions, and the key roles of Maintainers vs Contributors.",
        "content": (
            "### What is Open Source?\n"
            "Open source software (OSS) is software whose source code is publicly accessible, allowing anyone to inspect, modify, enhance, and distribute it freely.\n\n"
            "### The Open Source Ecosystem\n"
            "- **Maintainers**: Core stewards responsible for project direction, reviewing pull requests, enforcing quality, and publishing releases.\n"
            "- **Contributors**: Developers, designers, writers, and community members who report bugs, write documentation, suggest features, and submit code changes.\n"
            "- **Users**: Individuals and organizations who deploy the software and provide valuable real-world feedback.\n\n"
            "### Common Misconception\n"
            "> *Misconception*: 'Open source is only for elite senior developers writing complex algorithms.'\n"
            "> *Reality*: The vast majority of valuable contributions are fixing typos, improving documentation, writing tests, reproducing bugs, and adding beginner-friendly UI polish."
        ),
        "learning_objectives": [
            "Explain the definition of open source software",
            "Distinguish between Maintainers, Contributors, and Users",
            "Recognize that open source includes documentation, triage, testing, and code",
        ],
        "tips": [
            "Start by exploring repositories you already use in your daily workflow.",
            "Read the project's README and CONTRIBUTING guidelines before writing any code.",
        ],
        "order": 10,
        "estimated_minutes": 10,
        "exercises": [
            {
                "title": "Open Source Foundation Check",
                "prompt": "Which role in an open-source project is responsible for reviewing pull requests and merging code into the main repository? (maintainer / contributor / user)",
                "expected_command": "maintainer",
                "explanation": "Maintainers have write access and are responsible for reviewing, approving, and merging contributions.",
                "points": 15,
            }
        ],
    },
    {
        "slug": "level-1-licenses-and-releases",
        "category": "Level 1 — What is Open Source?",
        "difficulty": "beginner",
        "title": "Open Source Licenses & Governance",
        "summary": "Learn how licenses grant legal rights to use and modify code (MIT, Apache 2.0, GPL) and how releases work.",
        "content": (
            "### Why Licenses Matter\n"
            "If a public repository has no license file, default copyright laws apply. That means others cannot legally copy, modify, or distribute the code.\n\n"
            "### Major License Categories\n"
            "1. **Permissive Licenses** (MIT, Apache 2.0, BSD):\n"
            "   - Gives developers maximum freedom to use, modify, and distribute code, including in proprietary/commercial software, with minimal restrictions (usually just keeping the copyright notice).\n"
            "2. **Copyleft Licenses** (GPL v3, AGPL):\n"
            "   - Requires that any derivative works or distributed modifications must also be open-sourced under the same license terms.\n\n"
            "### Releases & Tags\n"
            "Maintainers package stable snapshots of a repository into **Releases** associated with Git tags (e.g. `v1.2.0`) following Semantic Versioning (`MAJOR.MINOR.PATCH`)."
        ),
        "learning_objectives": [
            "Understand why a LICENSE file is essential in every repository",
            "Differentiate between Permissive (MIT) and Copyleft (GPL) licenses",
            "Understand how semantic versioning tags mark stable project releases",
        ],
        "tips": [
            "Always inspect the `LICENSE` file before using open-source libraries in commercial applications.",
            "MIT is the most widely used permissive license for beginner-friendly projects.",
        ],
        "order": 20,
        "estimated_minutes": 12,
        "exercises": [
            {
                "title": "License Identification",
                "prompt": "Name a popular permissive open-source license that allows commercial use with minimal restrictions. (MIT / GPL / Proprietary)",
                "expected_command": "MIT",
                "explanation": "The MIT License is the industry standard for permissive open-source software.",
                "points": 15,
            }
        ],
    },

    # =========================================================================
    # LEVEL 2: GIT FUNDAMENTALS
    # =========================================================================
    {
        "slug": "level-2-git-three-trees-and-status",
        "category": "Level 2 — Git Fundamentals",
        "difficulty": "beginner",
        "title": "The Three Areas of Git & Working Tree State",
        "summary": "Master the 3-tree architecture of Git: Working Directory, Staging Area, and Repository snapshots.",
        "content": (
            "### The Three Trees of Git\n"
            "Understanding Git becomes intuitive once you visualize its three distinct areas:\n"
            "1. **Working Directory**: The actual files on your computer's filesystem that you are editing.\n"
            "2. **Staging Area (Index)**: The preparation area where you select and queue specific file changes before committing (`git add`).\n"
            "3. **Repository (Git History)**: The permanent, immutable record of committed snapshots (`git commit`).\n\n"
            "### Inspecting State with `git status`\n"
            "`git status` is your most vital command. It tells you:\n"
            "- What branch you are currently on\n"
            "- Which files are modified but untracked/unstaged\n"
            "- Which files are staged and ready for commit\n"
            "- Whether your local branch is ahead or behind the remote"
        ),
        "learning_objectives": [
            "Trace file lifecycle from Working Tree → Staging Area → Repository",
            "Use `git status` to interpret clean vs dirty states",
            "Use `git add <file>` to intentionally stage specific files",
        ],
        "tips": [
            "Run `git status` before and after every major Git command.",
            "Avoid blind `git add .` unless you have reviewed all changed files with `git diff`.",
        ],
        "order": 30,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Check Repository Status",
                "prompt": "Run the Git command to inspect the current branch, staged files, and modified working tree.",
                "expected_command": "git status",
                "explanation": "`git status` provides immediate visibility into your repository's working state.",
                "points": 15,
            }
        ],
    },
    {
        "slug": "level-2-branching-and-switching",
        "category": "Level 2 — Git Fundamentals",
        "difficulty": "beginner",
        "title": "Branching & Work Isolation",
        "summary": "Learn how branches isolate experiments and features so the main branch stays clean and deployable.",
        "content": (
            "### Why Feature Branches Are Mandatory\n"
            "In collaborative open source, you must **never commit directly on the `main` branch**.\n\n"
            "Branches allow you to:\n"
            "- Work on multiple independent fixes concurrently without cross-contamination\n"
            "- Discard experiments cleanly without breaking existing code\n"
            "- Submit isolated, reviewable pull requests\n\n"
            "### Modern Branching Commands\n"
            "- Create and switch to a new branch: `git switch -c <branch-name>` (or `git checkout -b <branch-name>`)\n"
            "- Switch to an existing branch: `git switch <branch-name>`\n"
            "- List all local branches: `git branch`\n\n"
            "### Conventional Branch Naming\n"
            "- `feat/user-avatar-upload`\n"
            "- `fix/issue-104-empty-title-validation`\n"
            "- `docs/update-installation-guide`"
        ),
        "learning_objectives": [
            "Explain why working on `main` causes conflicts in collaborative projects",
            "Create and switch to feature branches using `git switch -c`",
            "Apply clear, standard branch naming conventions",
        ],
        "tips": [
            "Always verify you branched off an up-to-date `main` branch.",
            "Use prefixes like `fix/`, `feat/`, or `docs/` in branch names.",
        ],
        "order": 40,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Create a Feature Branch",
                "prompt": "Create and switch to a new feature branch named fix/empty-title-validation.",
                "expected_command": "git switch -c fix/empty-title-validation",
                "explanation": "`git switch -c` creates the branch and immediately checks it out in your working tree.",
                "points": 20,
            }
        ],
    },
    {
        "slug": "level-2-atomic-commits-and-diffs",
        "category": "Level 2 — Git Fundamentals",
        "difficulty": "beginner",
        "title": "Atomic Commits & Clear Messages",
        "summary": "Learn how to craft atomic commits, inspect diffs with git diff, and write descriptive commit messages.",
        "content": (
            "### What Makes a Great Commit?\n"
            "A commit should be **atomic**: it represents one logical, self-contained unit of change. If you fixed a bug and also refactored an unrelated module, split them into two separate commits.\n\n"
            "### The Anatomy of a Commit Message\n"
            "Use conventional commit format in the imperative mood:\n"
            "```\n"
            "fix(validation): prevent creation of task with empty title (#104)\n"
            "\n"
            "- Add trim() check in TaskForm onSubmit handler\n"
            "- Display error toast when title is blank\n"
            "- Add unit test coverage for empty input\n"
            "```\n\n"
            "### Inspecting Diffs\n"
            "- Unstaged changes: `git diff`\n"
            "- Staged changes: `git diff --staged`"
        ),
        "learning_objectives": [
            "Use `git diff` and `git diff --staged` to verify changes before committing",
            "Write commit messages in imperative mood following conventional standards",
            "Structure commits atomically to facilitate review and rollback",
        ],
        "tips": [
            "Write 'Fix issue' instead of 'Fixed issue' or 'Fixing issue'.",
            "Review your diff line-by-line before running `git commit`.",
        ],
        "order": 50,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Create a Formatted Commit",
                "prompt": "Commit your staged changes with the message: fix(validation): prevent empty task title",
                "expected_command": 'git commit -m "fix(validation): prevent empty task title"',
                "explanation": "Using `-m` records the snapshot with a clear, conventional commit message.",
                "points": 20,
            }
        ],
    },

    # =========================================================================
    # LEVEL 3: GITHUB MECHANICS & ECOSYSTEM
    # =========================================================================
    {
        "slug": "level-3-fork-vs-clone-ecosystem",
        "category": "Level 3 — GitHub Mechanics",
        "difficulty": "beginner",
        "title": "Fork vs Clone & Remotes (Origin & Upstream)",
        "summary": "Master the GitHub remote model: Forking repositories, cloning your fork, and synchronizing with upstream.",
        "content": (
            "### Fork vs Clone: The Core Distinction\n"
            "- **Fork**: A remote server-side copy of another user's repository created under your own GitHub account. You have full write access to your fork.\n"
            "- **Clone**: Downloading a Git repository from GitHub onto your local computer disk (`git clone <url>`).\n\n"
            "### Managing Remotes\n"
            "When contributing to someone else's repository, you configure two remotes:\n"
            "1. `origin`: Your fork on GitHub (`https://github.com/YOUR_USERNAME/repo.git`)\n"
            "2. `upstream`: The original project repository (`https://github.com/ORIGINAL_MAINTAINER/repo.git`)\n\n"
            "```bash\n"
            "# 1. Clone your fork locally\n"
            "git clone https://github.com/YOUR_USERNAME/TaskTracker.git\n\n"
            "# 2. Add upstream remote\n"
            "git remote add upstream https://github.com/Atelier-Org/TaskTracker.git\n\n"
            "# 3. Verify remotes\n"
            "git remote -v\n"
            "```"
        ),
        "learning_objectives": [
            "Explain the difference between a GitHub Fork and a local Git Clone",
            "Configure `origin` and `upstream` remotes correctly",
            "Explain why contributors cannot push directly to upstream repositories without collaborator permissions",
        ],
        "tips": [
            "`origin` is where you push your branches; `upstream` is where you pull updates from.",
            "Always keep your fork's `main` branch synchronized with `upstream/main`.",
        ],
        "order": 60,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Add Upstream Remote",
                "prompt": "Add the upstream remote with URL https://github.com/Atelier-Org/TaskTracker.git",
                "expected_command": "git remote add upstream https://github.com/Atelier-Org/TaskTracker.git",
                "explanation": "This links your local repository to the canonical upstream source.",
                "points": 20,
            }
        ],
    },
    {
        "slug": "level-3-issues-labels-and-templates",
        "category": "Level 3 — GitHub Mechanics",
        "difficulty": "beginner",
        "title": "Project Governance: CONTRIBUTING.md & Issue Templates",
        "summary": "Understand repository guidelines: README, CONTRIBUTING.md, CODE_OF_CONDUCT.md, and structured issue templates.",
        "content": (
            "### Crucial Project Documents\n"
            "- **README.md**: The project's front door. Explains what the project does, quickstart steps, and features.\n"
            "- **CONTRIBUTING.md**: The contributor handbook. Details dev environment setup, branch naming, testing requirements, and PR review checklists.\n"
            "- **CODE_OF_CONDUCT.md**: Behavioral standards ensuring an inclusive, harassment-free community.\n\n"
            "### Understanding GitHub Labels\n"
            "- `good first issue`: Ideal for newcomers; well-defined with limited scope.\n"
            "- `help wanted`: Maintainers actively inviting external assistance.\n"
            "- `bug` / `enhancement` / `documentation`: Issue categories.\n"
            "- `needs reproduction` / `blocked`: Status indicators."
        ),
        "learning_objectives": [
            "Locate and interpret instructions in `CONTRIBUTING.md`",
            "Understand the purpose of `CODE_OF_CONDUCT.md`",
            "Interpret GitHub issue labels accurately to choose suitable tasks",
        ],
        "tips": [
            "Never open a PR that violates the testing or formatting rules in `CONTRIBUTING.md`.",
            "Respect issue templates and fill in every requested section.",
        ],
        "order": 70,
        "estimated_minutes": 12,
        "exercises": [
            {
                "title": "Locate Contributor Guidelines",
                "prompt": "What standard markdown file in a repository contains setup, testing, and PR submission guidelines? (CONTRIBUTING.md / README.md / LICENSE)",
                "expected_command": "CONTRIBUTING.md",
                "explanation": "CONTRIBUTING.md is the designated guide for all repository contributors.",
                "points": 15,
            }
        ],
    },

    # =========================================================================
    # LEVEL 4: FINDING YOUR FIRST CONTRIBUTION
    # =========================================================================
    {
        "slug": "level-4-exploring-repositories-and-scoping",
        "category": "Level 4 — Finding Your First Contribution",
        "difficulty": "intermediate",
        "title": "Finding Beginner-Friendly Issues & Scoping",
        "summary": "Learn how to filter issues, evaluate whether a task is within your current skillset, and claim it politely.",
        "content": (
            "### How to Find Good First Issues\n"
            "1. Search GitHub using filters: `is:issue is:open label:\"good first issue\" no:assignee`\n"
            "2. Read the issue description thoroughly:\n"
            "   - Is the problem clearly explained?\n"
            "   - Are steps to reproduce provided?\n"
            "   - Did a maintainer outline suggested files or approaches?\n\n"
            "### Communication Etiquette: Asking to Work on an Issue\n"
            "**Good Comment Example**:\n"
            "> 'Hi @maintainer! I would love to work on this issue. I plan to add input validation in `src/components/TaskForm.tsx` and add a corresponding test case in `TaskForm.test.tsx`. Could you please assign this to me?'\n\n"
            "**Avoid**:\n"
            "> 'assign me' or claiming 5 issues simultaneously without following up."
        ),
        "learning_objectives": [
            "Filter GitHub issues for unassigned `good first issue` tasks",
            "Assess task feasibility and identify relevant codebase locations",
            "Write polite, actionable issue comments demonstrating readiness to contribute",
        ],
        "tips": [
            "Always check existing issue comments to ensure another contributor isn't already actively working on it.",
            "Outline your proposed technical approach when requesting an assignment.",
        ],
        "order": 80,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Filter Issues by Label",
                "prompt": "What standard GitHub label filter helps beginners find well-scoped first tasks? (label:\"good first issue\" / label:urgent / label:wontfix)",
                "expected_command": 'label:"good first issue"',
                "explanation": "Searching for label:\"good first issue\" returns tasks curated specifically for newcomers.",
                "points": 20,
            }
        ],
    },

    # =========================================================================
    # LEVEL 5: THE COMPLETE CONTRIBUTION WORKFLOW
    # =========================================================================
    {
        "slug": "level-5-the-end-to-end-workflow",
        "category": "Level 5 — The Contribution Workflow",
        "difficulty": "intermediate",
        "title": "The End-to-End 10-Step Contribution Lifecycle",
        "summary": "Walk through the full contribution lifecycle: Fork → Clone → Branch → Fix → Test → Commit → Push → PR → Review → Merge.",
        "content": (
            "### The 10-Step Open Source Lifecycle\n\n"
            "1. **Discover**: Find an open issue and get assigned.\n"
            "2. **Fork**: Create your personal GitHub copy.\n"
            "3. **Clone**: Clone your fork locally.\n"
            "4. **Upstream Remote**: Configure canonical remote for syncing.\n"
            "5. **Branch**: Create a descriptive feature branch off `main`.\n"
            "6. **Develop & Test**: Implement the fix and run tests locally.\n"
            "7. **Stage & Commit**: Make atomic, conventional commits.\n"
            "8. **Push**: Push your feature branch to your fork (`origin`).\n"
            "9. **Open PR**: Submit Pull Request with description and issue reference.\n"
            "10. **Review & Merge**: Respond to feedback, push adjustments, and celebrate the merge!"
        ),
        "learning_objectives": [
            "Recite and execute all 10 stages of the contribution lifecycle",
            "Push a local feature branch to the remote origin with upstream tracking",
            "Recognize how local commits synchronize with GitHub Pull Requests",
        ],
        "tips": [
            "Run your test suite locally before pushing: `npm test` or `pytest`.",
            "Use `git push -u origin <branch-name>` on the first push to link tracking.",
        ],
        "order": 90,
        "estimated_minutes": 20,
        "exercises": [
            {
                "title": "Push Branch to Remote Fork",
                "prompt": "Push your local branch fix/empty-title-validation to origin and set upstream tracking.",
                "expected_command": "git push -u origin fix/empty-title-validation",
                "explanation": "The `-u` flag configures your local branch to track the remote branch on origin.",
                "points": 25,
            }
        ],
    },

    # =========================================================================
    # LEVEL 6: PULL REQUESTS & CODE REVIEW
    # =========================================================================
    {
        "slug": "level-6-crafting-exceptional-prs",
        "category": "Level 6 — Pull Requests & Code Review",
        "difficulty": "intermediate",
        "title": "Crafting PRs, Linking Issues & Review Etiquette",
        "summary": "Write stellar PR descriptions, link issues automatically (Fixes #104), and handle code reviews constructively.",
        "content": (
            "### Writing a Great Pull Request\n"
            "A Pull Request is a proposal to the maintainers. Make it as easy as possible for them to review and say YES.\n\n"
            "**Key Elements**:\n"
            "- **Title**: Clear and concise (`fix(validation): prevent empty task title submissions`)\n"
            "- **Closing Keyword**: `Fixes #104` or `Closes #104` (automatically closes the issue upon merge)\n"
            "- **What Changed**: Bullet points explaining the technical adjustments\n"
            "- **Testing Done**: Evidence of tests passed and screenshots if UI changed\n\n"
            "### Code Review Etiquette\n"
            "- Maintainers review code, not people. Critique is never personal.\n"
            "- If changes are requested: make the edits on your local branch, commit them, and push. The PR updates automatically!"
        ),
        "learning_objectives": [
            "Write descriptive, review-ready Pull Request titles and descriptions",
            "Use GitHub auto-closing keywords (`Fixes #<number>`) correctly",
            "Respond constructively to code review comments and update PRs with new commits",
        ],
        "tips": [
            "You do NOT need to close and reopen a PR to update it; simply push new commits to your branch.",
            "Thank maintainers for their review time — maintainers are often volunteers.",
        ],
        "order": 100,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Link Issue in PR Description",
                "prompt": "What GitHub keyword and syntax in a PR body automatically closes Issue 104 when merged? (Fixes #104 / Ref 104 / Issue 104)",
                "expected_command": "Fixes #104",
                "explanation": "GitHub keywords like 'Fixes #104' or 'Closes #104' link the PR and auto-close the issue on merge.",
                "points": 20,
            }
        ],
    },
    {
        "slug": "level-6-resolving-merge-conflicts",
        "category": "Level 6 — Pull Requests & Code Review",
        "difficulty": "advanced",
        "title": "Resolving Merge Conflicts Confidently",
        "summary": "Understand why merge conflicts occur and learn the step-by-step procedure to resolve conflict markers cleanly.",
        "content": (
            "### Why Conflicts Happen\n"
            "When two branches modify the same line in a file (or one branch deletes a file that another modified), Git stops and asks the developer to decide which version is correct.\n\n"
            "### Anatomy of Conflict Markers\n"
            "```\n"
            "<<<<<<< HEAD (Current Change: your branch)\n"
            "const title = input.trim();\n"
            "=======\n"
            "const title = sanitizeInput(input.trim());\n"
            ">>>>>>> upstream/main (Incoming Change)\n"
            "```\n\n"
            "### Step-by-Step Resolution\n"
            "1. Fetch latest upstream: `git fetch upstream`\n"
            "2. Merge or rebase: `git merge upstream/main`\n"
            "3. Open conflicting files and choose the desired code\n"
            "4. Delete all `<<<<<<<`, `=======`, and `>>>>>>>` marker lines\n"
            "5. Stage resolved file: `git add <file>`\n"
            "6. Complete merge commit: `git commit`\n"
            "7. Push to your fork: `git push origin <branch>`"
        ),
        "learning_objectives": [
            "Identify the causes of merge conflicts in collaborative workflows",
            "Read and parse Git conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)",
            "Execute full resolution: edit file, remove markers, stage, commit, and push",
        ],
        "tips": [
            "Always run your automated test suite after resolving conflicts to verify functionality.",
            "Pull from upstream frequently to keep conflicts small and manageable.",
        ],
        "order": 110,
        "estimated_minutes": 20,
        "exercises": [
            {
                "title": "Sync Upstream Branch",
                "prompt": "Run the command to fetch updates from the upstream remote repository.",
                "expected_command": "git fetch upstream",
                "explanation": "`git fetch upstream` downloads the latest commits and branches from the canonical repository.",
                "points": 25,
            }
        ],
    },

    # =========================================================================
    # LEVEL 7: REAL-WORLD OPEN SOURCE SKILLS
    # =========================================================================
    {
        "slug": "level-7-reading-unfamiliar-codebases",
        "category": "Level 7 — Real-World OSS Skills",
        "difficulty": "advanced",
        "title": "Navigating Large Codebases & Issue Triage",
        "summary": "Strategies for reading unfamiliar repositories, reproducing complex bugs, and triaging community issues.",
        "content": (
            "### Strategies for Exploring Large Codebases\n"
            "1. **Start at Entry Points**: Look at `package.json` scripts, `urls.py`, `App.tsx`, or `main.go` to trace data flow.\n"
            "2. **Search for Keywords**: Use global grep/search for UI text, route paths, or function names.\n"
            "3. **Inspect Existing Tests**: Unit and integration tests show exactly how functions are intended to be called.\n\n"
            "### Effective Issue Triage\n"
            "When triaging incoming community bug reports:\n"
            "- Verify reproduction steps\n"
            "- Check if it is a duplicate of an existing issue\n"
            "- Categorize with appropriate labels (`bug`, `needs-repro`, `good-first-issue`)\n"
            "- Prompt the author politely if crucial system information is missing"
        ),
        "learning_objectives": [
            "Apply top-down and bottom-up strategies to navigate large repositories",
            "Use tests and entry points to understand architecture quickly",
            "Perform structured issue triage to help maintainers manage issue backlogs",
        ],
        "tips": [
            "Small documentation fixes while exploring a codebase are great warmup contributions.",
            "Always reproduce a reported bug locally before writing a fix.",
        ],
        "order": 120,
        "estimated_minutes": 20,
        "exercises": [
            {
                "title": "Codebase Navigation Strategy",
                "prompt": "What files in a repository provide concrete executable examples of how functions and components are intended to work? (tests / license / gitignore)",
                "expected_command": "tests",
                "explanation": "Test suites provide living documentation of expected inputs, outputs, and edge cases.",
                "points": 20,
            }
        ],
    },
    {
        "slug": "level-7-maintainer-communication-and-resilience",
        "category": "Level 7 — Real-World OSS Skills",
        "difficulty": "advanced",
        "title": "Contribution Etiquette, Handling Feedback & Resilience",
        "summary": "Master communication etiquette, handling PR rejection gracefully, and evolving into a trusted open-source maintainer.",
        "content": (
            "### Handling Feedback & Closed PRs Gracefully\n"
            "Sometimes a Pull Request is closed without merging because:\n"
            "- The feature doesn't align with the project's long-term roadmap\n"
            "- Another contributor submitted an alternative approach\n"
            "- Architectural priorities shifted\n\n"
            "**How to Respond**:\n"
            "> 'Thank you for reviewing and explaining the project direction @maintainer! I learned a lot about the codebase during this task and look forward to contributing to future issues.'\n\n"
            "### The Path to Long-Term Impact\n"
            "Consistent, polite, and dependable contributors who help review others' PRs and triage issues are often invited to become official **Maintainers**."
        ),
        "learning_objectives": [
            "Develop resilience when contributions require extensive changes or are closed",
            "Communicate professionally with volunteer maintainers across timezones",
            "Understand the trajectory from first-time contributor to core maintainer",
        ],
        "tips": [
            "Every PR you write makes you a stronger software engineer, whether it gets merged immediately or not.",
            "Consistent helpfulness in discussions and reviews builds community reputation.",
        ],
        "order": 130,
        "estimated_minutes": 15,
        "exercises": [
            {
                "title": "Open Source Mindset",
                "prompt": "What is the primary factor that turns contributors into trusted project maintainers? (consistency and constructive collaboration / number of stars / writing code without tests)",
                "expected_command": "consistency and constructive collaboration",
                "explanation": "Maintainers value reliable, constructive contributors who write tests, communicate politely, and help others.",
                "points": 25,
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the focused 7-Level AI Tutor curriculum for Open-Source Contribution Atelier"

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding 7-Level Open Source AI Tutor curriculum..."))

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for lesson_data in CURRICULUM_LESSONS:
                exercises_data = lesson_data.pop("exercises", [])
                slug = lesson_data["slug"]

                lesson, created = Lesson.objects.update_or_create(
                    slug=slug,
                    defaults=lesson_data,
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                # Recreate exercises cleanly
                Exercise.objects.filter(lesson=lesson).delete()
                for ex in exercises_data:
                    Exercise.objects.create(
                        lesson=lesson,
                        title=ex["title"],
                        prompt=ex["prompt"],
                        expected_command=ex["expected_command"],
                        explanation=ex.get("explanation", ""),
                        points=ex.get("points", 15),
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded curriculum: {created_count} created, {updated_count} updated. "
                f"Total {Lesson.objects.count()} lessons across 7 Levels."
            )
        )
