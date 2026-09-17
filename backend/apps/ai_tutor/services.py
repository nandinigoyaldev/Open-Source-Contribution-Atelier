import json
import logging
import re
from typing import Any, Dict, Generator, List, Optional

from django.conf import settings

logger = logging.getLogger(__name__)

# Structured Socratic knowledge base covering all 7 Levels of Open Source mastery
SOCRATIC_KNOWLEDGE_BASE: Dict[str, Dict[str, Any]] = {
    # Level 1: What is Open Source?
    "open_source": {
        "keywords": [r"\bopen source\b", r"\boss\b", r"\bwhat is open source\b"],
        "concept": "Open Source & Collaborative Software",
        "socratic_prompt": "Before we dive in, imagine you wrote a useful tool and published the code so anyone can study and improve it. Why might other developers want to help you make it better?",
        "explanation": (
            "Open source software is code that is freely accessible for anyone to inspect, modify, enhance, and distribute. "
            "It powers the modern software ecosystem (Linux, Python, React, Kubernetes). "
            "Beyond code, open source thrives on transparent collaboration, issue triage, documentation, and peer review."
        ),
        "hints": [
            "Think about how transparent code lets people discover bugs, propose fixes, and add features together.",
            "Open source projects have a LICENSE file that specifies permissions and conditions for using and altering the code.",
            "Key roles include Maintainers (who guide the project and merge PRs) and Contributors (who propose improvements).",
        ],
    },
    "licenses": {
        "keywords": [r"\blicense\b", r"\blicensing\b", r"\bmit\b", r"\bgpl\b", r"\bapache\b"],
        "concept": "Open Source Licenses",
        "socratic_prompt": "If you put your code on GitHub without a license, does that mean anyone can legally use it in their commercial project? What protects your intentions?",
        "explanation": (
            "An open-source license explicitly states what others can and cannot do with your code.\n\n"
            "- **Permissive** (MIT, Apache 2.0, BSD): Gives users maximum freedom with minimal conditions.\n"
            "- **Copyleft** (GPL, AGPL): Requires that any distributed derivative works must also be open source under the same license.\n"
            "Without a license, default copyright laws apply, meaning you retain exclusive rights and nobody else may copy or modify it."
        ),
        "hints": [
            "Permissive licenses like MIT let developers do almost anything as long as they retain the copyright notice.",
            "Copyleft licenses like GPL ensure software remains open source forever in downstream derivatives.",
            "Always check the repository's `LICENSE` file before contributing or embedding it in your own work.",
        ],
    },
    # Level 2: Git Fundamentals
    "git": {
        "keywords": [r"\bgit\b", r"\bversion control\b", r"\bvcs\b"],
        "concept": "Git Version Control",
        "socratic_prompt": "Have you ever saved files as `project_final.zip`, `project_final_v2.zip`, `project_real_final.zip`? What problem does Git solve when collaborating with 10 people?",
        "explanation": (
            "Git is a distributed version control system that acts like a time machine for your codebase. "
            "It tracks the history of every change, lets multiple developers work concurrently on separate branches without overwriting each other, "
            "and allows you to rewind or compare any version safely."
        ),
        "hints": [
            "Git tracks snapshots of files, not just differences.",
            "The 3 main areas in Git are: Working Directory → Staging Area (`git add`) → Repository (`git commit`).",
            "Use `git status` frequently to inspect your working tree.",
        ],
    },
    "commit": {
        "keywords": [r"\bcommit\b", r"\bcommits\b", r"\bcommit message\b"],
        "concept": "Git Commits & Snapshots",
        "socratic_prompt": "When a maintainer looks at a commit hash 6 months later, what helps them understand *why* a change was made rather than just what lines changed?",
        "explanation": (
            "A commit is an immutable snapshot of staged changes saved to your Git history. "
            "Every commit contains a unique SHA hash, author info, timestamp, and a commit message. "
            "Best practice: Write commit messages in the imperative mood (`feat: add validation for empty input` instead of `added validation`)."
        ),
        "hints": [
            "First stage changes with `git add <file>`, then save the snapshot with `git commit -m 'message'`.",
            "Keep commits atomic: each commit should represent one focused, logical change.",
            "Follow conventional commit formats like `fix:`, `feat:`, `docs:`, and `refactor:`.",
        ],
    },
    "branch": {
        "keywords": [r"\bbranch\b", r"\bbranches\b", r"\bcheckout\b", r"\bswitch\b"],
        "concept": "Git Branches & Isolation",
        "socratic_prompt": "If you are fixing a bug and another teammate is building a new feature, why shouldn't both of you commit directly to the `main` branch simultaneously?",
        "explanation": (
            "A branch is an isolated pointer to a line of commits. It lets you develop features, fix bugs, or experiment without affecting the stable `main` branch. "
            "Create a new branch with `git switch -c feat/my-feature` (or `git checkout -b feat/my-feature`). Once your work is tested and reviewed, it is merged back into `main`."
        ),
        "hints": [
            "Never work directly on `main` in collaborative projects.",
            "Use descriptive branch names like `fix/issue-104-validation` or `docs/update-readme`.",
            "Use `git branch` to list existing branches and `git switch <branch-name>` to change between them.",
        ],
    },
    "merge_conflicts": {
        "keywords": [r"\bconflict\b", r"\bmerge conflict\b", r"\bconflicts\b", r"\brebase\b"],
        "concept": "Merge Conflicts & Resolution",
        "socratic_prompt": "What happens if both you and another developer edit line 25 of `app.py` in different ways and try to merge into `main`? How does Git know which version is right?",
        "explanation": (
            "A merge conflict occurs when Git cannot automatically reconcile differences between two branches modifying the same lines of code. "
            "Git inserts conflict markers (`<<<<<<< HEAD`, `=======`, `>>>>>>> branch-name`). "
            "To resolve it: open the file, decide which code to keep, delete the marker lines, stage the resolved file with `git add`, and finalize with `git commit`."
        ),
        "hints": [
            "Conflict markers show your local version above `=======` and the incoming version below `=======`.",
            "Keep your branch updated frequently by pulling or rebasing against upstream `main` to minimize conflict scope.",
            "After cleaning up the conflicting code, run your test suite to make sure nothing broke.",
        ],
    },
    # Level 3: GitHub Ecosystem & Fork vs Clone
    "fork_vs_clone": {
        "keywords": [r"\bfork\b", r"\bclone\b", r"\bfork vs clone\b", r"\bremote\b", r"\bupstream\b"],
        "concept": "Fork vs Clone Workflow",
        "socratic_prompt": "If you don't have direct write access to a popular open-source repository on GitHub, where do you push your branch before opening a Pull Request?",
        "explanation": (
            "**Fork**: A server-side copy of the repository under your own GitHub account on GitHub's servers.\n"
            "**Clone**: Downloading a copy of a repository from GitHub to your local computer's disk (`git clone <url>`).\n\n"
            "**Standard Workflow**:\n"
            "1. Fork the repo on GitHub.\n"
            "2. Clone *your fork* locally: `git clone https://github.com/YOUR_USER/repo.git`.\n"
            "3. Add the original repo as upstream: `git remote add upstream https://github.com/ORIGINAL_OWNER/repo.git`.\n"
            "4. Make changes on a branch, push to your fork (`origin`), and open a Pull Request to `upstream`."
        ),
        "hints": [
            "You cannot push directly to a repository you don't own unless you are added as a collaborator.",
            "Forking gives you your own sandbox repo where you have full write permissions.",
            "`origin` points to your personal fork; `upstream` points to the canonical project repository.",
        ],
    },
    "issues_and_templates": {
        "keywords": [r"\bissue\b", r"\bissues\b", r"\bcontributing\b", r"\btemplate\b", r"\bcode of conduct\b"],
        "concept": "Issues & Project Governance",
        "socratic_prompt": "Before opening a PR with a major code overhaul, why should you check existing issues or start a discussion with the maintainers first?",
        "explanation": (
            "GitHub Issues track bugs, enhancements, and tasks. High-quality repositories provide `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, and issue templates. "
            "Good issue etiquette:\n"
            "- Search existing issues before creating a duplicate.\n"
            "- Fill in all template fields (reproduction steps, expected vs actual behavior, environment).\n"
            "- Discuss large architectural changes before spending days writing code that maintainers might not want."
        ),
        "hints": [
            "Look for `CONTRIBUTING.md` in the root or `.github/` folder for setup and testing rules.",
            "Issue templates ask for specific info that saves maintainers hours of back-and-forth.",
            "Always be respectful and adhere to the project's `CODE_OF_CONDUCT.md`.",
        ],
    },
    # Level 4: Finding Your First Contribution
    "first_contribution": {
        "keywords": [r"\bgood first issue\b", r"\bhelp wanted\b", r"\bfirst contribution\b", r"\bfind issue\b"],
        "concept": "Finding Beginner-Friendly Issues",
        "socratic_prompt": "When browsing a 50,000-line repository for the first time, what issue labels should you search for to find scoped, maintainer-vetted tasks?",
        "explanation": (
            "Maintainers curate beginner tasks using standardized labels:\n"
            "- `good first issue`: Scoped tasks with clear boundaries, perfect for newcomers.\n"
            "- `help wanted`: Maintainers actively inviting external community help.\n"
            "- `documentation`: Improving docs, guides, or fixing typos — great for learning repo structure.\n\n"
            "Before jumping in: read the issue carefully, ask polite clarifying questions if needed, and confirm no one else is already actively assigned."
        ),
        "hints": [
            "Don't claim multiple issues at once. Start with one small, clear task.",
            "Comment politely: 'Hi maintainers, I'd like to work on this issue. Could you assign it to me?'",
            "Read existing comments on the issue to see if someone already submitted a solution.",
        ],
    },
    # Level 5 & 6: Pull Requests & Code Review
    "pull_request": {
        "keywords": [r"\bpull request\b", r"\bpr\b", r"\bcode review\b", r"\breview\b"],
        "concept": "Pull Requests & Code Review Etiquette",
        "socratic_prompt": "Why is it important to link the issue number (e.g., `Fixes #104`) in your Pull Request description, and why should PRs be small rather than changing 40 unrelated files?",
        "explanation": (
            "A Pull Request (PR) proposes your branch's changes to the upstream project. "
            "Best practices for successful PRs:\n"
            "1. **Clear Title**: Describe the outcome (`fix(auth): prevent session timeout on page refresh`).\n"
            "2. **Description**: Explain *why* the change was made and link the issue using keywords like `Closes #123`.\n"
            "3. **Small Scope**: Keep diffs focused. Reviewing a 50-line PR takes 5 minutes; a 1,000-line PR takes weeks.\n"
            "4. **Receptive to Feedback**: Code review comments are about the code, not you. Respond constructively, make requested tweaks, and push new commits to update the PR automatically."
        ),
        "hints": [
            "Use GitHub keywords like `Fixes #123` or `Closes #123` to automatically close the issue when merged.",
            "You don't need to open a new PR when making changes — just push commits to your existing feature branch.",
            "Run linters and test suites locally before submitting your PR to ensure CI passes on the first try.",
        ],
    },
}


class AiTutorService:
    """Core AI Tutor service offering Socratic teaching, progressive hints,

    attempt evaluation, and mistake diagnosis.
    """

    @classmethod
    def build_tutor_context(
        cls,
        learner_level: str = "beginner",
        current_level: str = "",
        current_lesson: str = "",
        completed_concepts: Optional[List[str]] = None,
        recent_mistakes: Optional[List[str]] = None,
        exercise_prompt: str = "",
    ) -> Dict[str, Any]:
        """Constructs a compact, structured context object for the AI Tutor."""
        return {
            "learner_level": learner_level,
            "current_level": current_level or "Level 1 — What is Open Source?",
            "current_lesson": current_lesson or "Introduction to Open Source",
            "completed_concepts": completed_concepts or [],
            "recent_mistakes": recent_mistakes or [],
            "exercise_prompt": exercise_prompt,
        }

    @classmethod
    def find_relevant_topic(cls, text: str) -> Optional[Dict[str, Any]]:
        """Matches a query string to the curated knowledge base."""
        text_lower = text.lower()
        for topic_key, topic_data in SOCRATIC_KNOWLEDGE_BASE.items():
            for pattern in topic_data["keywords"]:
                if re.search(pattern, text_lower):
                    return topic_data
        return None

    @classmethod
    def evaluate_attempt(
        cls,
        user_input: str,
        expected_concept_or_command: str,
        lesson_context: str = "",
        tutor_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluates a learner's exercise attempt or answer using Socratic principles.

        Returns:
            {
                "is_correct": bool,
                "feedback": str,
                "hint": str,
                "mistake_detected": Optional[str]
            }
        """
        user_clean = user_input.strip()
        expected_clean = expected_concept_or_command.strip()

        # Check exact or normalized command match
        if user_clean.lower() == expected_clean.lower():
            return {
                "is_correct": True,
                "feedback": "🎯 Excellent work! You nailed it. That is the exact command maintainers expect.",
                "hint": "",
                "mistake_detected": None,
            }

        # Check common beginner mistakes
        mistake = None
        hint = ""
        feedback = ""

        # Mistake 1: Confusing fork and clone
        if "clone" in user_clean.lower() and "fork" in expected_clean.lower():
            mistake = "Confused local clone with GitHub fork"
            feedback = "Close! Notice that `git clone` copies a repo to your local machine, but if you don't have write permissions, you first need a personal copy on GitHub."
            hint = "Think about which action creates your personal copy on GitHub's servers first."

        # Mistake 2: Missing branch flag in switch / checkout
        elif ("git checkout" in user_clean or "git switch" in user_clean) and "-b" not in user_clean and "-c" not in user_clean and ("-c" in expected_clean or "-b" in expected_clean):
            mistake = "Missing new branch creation flag"
            feedback = "Good start, but running `git switch <name>` without `-c` tries to switch to an *existing* branch. To create a new branch at the same time, you need the creation flag."
            hint = "Use `git switch -c <branch-name>` or `git checkout -b <branch-name>`."

        # Mistake 3: Committing on main
        elif "main" in user_clean.lower() and "feature" in expected_clean.lower():
            mistake = "Attempted direct commit to main"
            feedback = "Careful! In open-source collaboration, you should never commit directly on `main`. Always isolate your changes in a feature branch."
            hint = "Create a dedicated feature branch with a descriptive name like `feat/add-validation`."

        # Mistake 4: Missing commit message
        elif "git commit" in user_clean and "-m" not in user_clean:
            mistake = "Missing commit message flag (-m)"
            feedback = "You ran `git commit`, but you didn't provide a commit message. Maintainers require clear descriptions of every change."
            hint = "Add `-m \"your descriptive commit message\"` to your command."

        # Mistake 5: Missing git add
        elif "git commit" in user_clean and "git add" in expected_clean:
            mistake = "Committed before staging"
            feedback = "Before Git can commit changes, you need to stage them so Git knows which files to include in the snapshot."
            hint = "Use `git add <filename>` or `git add .` to stage your changes first."

        else:
            feedback = f"Not quite. You entered `{user_clean}`, but think about what the lesson requires."
            hint = f"Review the lesson goal: `{expected_clean}`. What command structure matches that action?"

        return {
            "is_correct": False,
            "feedback": feedback,
            "hint": hint,
            "mistake_detected": mistake,
        }

    @classmethod
    def get_hint(
        cls,
        hint_level: int = 1,
        topic_or_exercise: str = "",
        lesson_context: str = "",
    ) -> str:
        """Returns progressive hints (Level 1: Guiding question, Level 2: Clue, Level 3: Concrete example/solution)."""
        topic_data = cls.find_relevant_topic(topic_or_exercise)
        if topic_data and "hints" in topic_data:
            hints = topic_data["hints"]
            index = min(max(0, hint_level - 1), len(hints) - 1)
            level_labels = ["💡 Guiding Question (Hint 1)", "🔍 Practical Clue (Hint 2)", "🎯 Targeted Solution (Hint 3)"]
            return f"**{level_labels[index]}**:\n{hints[index]}"

        if hint_level == 1:
            return "💡 **Hint 1 (Socratic)**: Think about the core goal. What is the fundamental Git command or GitHub concept needed here?"
        elif hint_level == 2:
            return f"🔍 **Hint 2 (Clue)**: Check the syntax rules from this lesson. Focus on parameters and branch naming."
        else:
            return f"🎯 **Hint 3 (Solution)**: Review the reference command: `{topic_or_exercise}`."

    @classmethod
    def get_response(
        cls,
        question: str,
        lesson_context: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        tutor_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generates a synchronous Socratic response using LLM or structured knowledge base fallback."""
        if not question.strip():
            return "Please ask a question! I'm here to help you master open source contribution."

        if getattr(settings, "OPENAI_API_KEY", None):
            return cls._llm_response(question, lesson_context, history or [], tutor_context)

        return cls._fallback_socratic_response(question, lesson_context, tutor_context)

    @classmethod
    def get_streaming_response(
        cls,
        question: str,
        lesson_context: str = "",
        history: Optional[List[Dict[str, str]]] = None,
        tutor_context: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Streams Socratic tutor responses word-by-word (via LLM or deterministic fallback)."""
        if not question.strip():
            yield f"data: {json.dumps({'text': 'Please ask a question about open source!'})}\n\n"
            return

        if getattr(settings, "OPENAI_API_KEY", None):
            try:
                import openai

                openai.api_key = settings.OPENAI_API_KEY
                model = getattr(settings, "LLM_MODEL", "gpt-3.5-turbo")

                system_prompt = cls._build_system_prompt(lesson_context, tutor_context)
                messages = [{"role": "system", "content": system_prompt}]

                for entry in (history or [])[-6:]:
                    messages.append({"role": "user", "content": entry.get("question", "")})
                    messages.append({"role": "assistant", "content": entry.get("answer", "")})

                messages.append({"role": "user", "content": question})

                stream = openai.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=400,
                    temperature=0.6,
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        content = getattr(delta, "content", None)
                        if content:
                            yield f"data: {json.dumps({'text': content})}\n\n"
                return
            except Exception as e:
                logger.warning("AI tutor streaming LLM call failed: %s", e)

        # Fallback streaming
        fallback_text = cls._fallback_socratic_response(question, lesson_context, tutor_context)
        tokens = re.findall(r"\S+|\s+", fallback_text)
        for token in tokens:
            yield f"data: {json.dumps({'text': token})}\n\n"

    @classmethod
    def _build_system_prompt(
        cls, lesson_context: str = "", tutor_context: Optional[Dict[str, Any]] = None
    ) -> str:
        ctx = tutor_context or {}
        cur_level = ctx.get("current_level", "Open Source Learning Path")
        cur_lesson = ctx.get("current_lesson", "General")
        completed = ", ".join(ctx.get("completed_concepts", [])) or "None yet"
        mistakes = ", ".join(ctx.get("recent_mistakes", [])) or "None recorded"

        return (
            "You are an expert, supportive AI mentor for 'Open-Source Contribution Atelier'. "
            "Your mission is to teach beginners how to contribute to real open-source projects with confidence.\n\n"
            "TEACHING PHILOSOPHY (Socratic Method):\n"
            "- Teach → Ask → Let learner try → Evaluate → Explain mistake → Give progressive hints → Try again → Progress.\n"
            "- Do NOT simply dump answers immediately. Guide the student with questions and analogies.\n"
            "- Explain *why* things work (e.g. why branches protect main, why commits need clear messages, why forks prevent unauthorized pushes).\n"
            "- Keep answers concise (2 to 4 sentences or a clean bulleted list), encouraging, and technically precise.\n"
            "- If the student makes a mistake, pinpoint the exact misconception kindly and ask them to try again.\n\n"
            f"LEARNER CONTEXT:\n"
            f"- Track Level: {cur_level}\n"
            f"- Active Lesson: {cur_lesson}\n"
            f"- Mastered Concepts: {completed}\n"
            f"- Recent Mistakes to Reinforce: {mistakes}\n"
            + (f"\nLESSON SUMMARY:\n{lesson_context}\n" if lesson_context else "")
        )

    @classmethod
    def _fallback_socratic_response(
        cls,
        question: str,
        lesson_context: str = "",
        tutor_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Determines the best structured Socratic response from the knowledge base."""
        topic = cls.find_relevant_topic(question)
        if topic:
            return (
                f"**{topic['concept']}**\n\n"
                f"{topic['explanation']}\n\n"
                f"🤔 **Mentor Question**: {topic['socratic_prompt']}"
            )

        # Quick greetings
        if re.search(r"\b(hello|hi|hey|greetings|help)\b", question.lower()):
            lesson_info = f" on **{lesson_context}**" if lesson_context else ""
            return (
                f"👋 Hello! I'm your open-source mentor{lesson_info}. "
                "I'm here to help you understand Git mechanics, GitHub collaboration, pull requests, and contribution etiquette. "
                "What concept would you like to explore or practice today?"
            )

        return (
            f"That's a thoughtful question about **{question[:60]}**.\n\n"
            "In open-source development, every contribution follows a clean lifecycle: understand the project → claim an issue → branch → change & test → commit → open PR → respond to review.\n\n"
            "Try asking about **Git branches**, **commits**, **fork vs clone**, **finding good first issues**, or **resolving merge conflicts**!"
        )

    @classmethod
    def _llm_response(
        cls,
        question: str,
        lesson_context: str,
        history: List[Dict[str, str]],
        tutor_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            import openai

            openai.api_key = settings.OPENAI_API_KEY
            model = getattr(settings, "LLM_MODEL", "gpt-3.5-turbo")

            system_prompt = cls._build_system_prompt(lesson_context, tutor_context)
            messages = [{"role": "system", "content": system_prompt}]

            for entry in history[-6:]:
                messages.append({"role": "user", "content": entry.get("question", "")})
                messages.append({"role": "assistant", "content": entry.get("answer", "")})

            messages.append({"role": "user", "content": question})

            response = openai.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=400,
                temperature=0.6,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning("AI tutor LLM call failed: %s", e)
            return cls._fallback_socratic_response(question, lesson_context, tutor_context)
