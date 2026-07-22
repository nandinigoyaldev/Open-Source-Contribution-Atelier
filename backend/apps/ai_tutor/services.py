import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)

FALLBACK_RESPONSES = {
    r"\bgit\b": (
        "Git is a distributed version control system. Think of it as a time machine for your code — "
        "it tracks every change so you can go back to any previous state. The basic workflow is: "
        "`git init` to start a repo, `git add` to stage changes, `git commit` to save them. "
        "You can use `git log` to see history and `git diff` to see what changed."
    ),
    r"\bcommit\b": (
        "A commit is a snapshot of your project at a specific point in time. "
        "Each commit has a unique hash (like `a1b2c3d`), a message describing the change, "
        "and metadata (author, timestamp). Write clear commit messages in the imperative mood: "
        "'Add login feature' not 'Added login feature'."
    ),
    r"\b(branch|merge)\b": (
        "Branches let you work on different features in isolation. "
        "`git branch feature-x` creates a new branch, `git checkout feature-x` switches to it. "
        "When you're done, `git merge feature-x` brings those changes into your main branch. "
        "Merge conflicts happen when two branches modify the same file — you resolve them manually."
    ),
    r"\b(pull request|pr)\b": (
        "A Pull Request (PR) is how you propose changes to an open-source project. "
        "You fork the repo, make your changes in a branch, push to your fork, and open a PR "
        "against the original repo. Maintainers review your code, leave comments, and either "
        "request changes or merge it. Always follow the project's CONTRIBUTING.md guidelines."
    ),
    r"\b(open source|oss)\b": (
        "Open Source means the source code is publicly available for anyone to view, use, "
        "modify, and distribute. Popular licenses include MIT (permissive), GPL (copyleft), "
        "and Apache 2.0. Contributing to open source is a great way to learn, build your "
        "portfolio, and give back to the community."
    ),
    r"\b(fork|clone)\b": (
        "`git clone <url>` downloads a repository to your local machine. "
        "A fork is a personal copy of someone else's repository on GitHub. "
        "You fork → clone your fork → make changes → push → open a PR. "
        "Keep your fork updated with the original repo using `git remote add upstream` "
        "and `git pull upstream main`."
    ),
    r"\b(conflict|resolve)\b": (
        "A merge conflict occurs when two branches modify the same line of a file. "
        "Git marks the conflicting area with `<<<<<<<`, `=======`, and `>>>>>>>`. "
        "You edit the file to keep the correct changes, remove the markers, "
        "then `git add` and `git commit` to complete the merge."
    ),
    r"\b(issue|bug)\b": (
        "Issues are GitHub's way of tracking bugs, feature requests, and tasks. "
        "When reporting a bug, include: steps to reproduce, expected behavior, "
        "actual behavior, and your environment (OS, browser, version). "
        "Good first issues are labeled `good first issue` and are perfect for beginners."
    ),
    r"\bhello\b|\bhi\b|\bhey\b": (
        "Hello! I'm your AI lesson tutor. I can help you understand Git, open source, "
        "and the lesson content. Ask me anything about what you're studying!"
    ),
}

MARKDOWN_TEMPLATES = {
    r"\b(lesson|module|curriculum)\b.*\b(1|one)\b": (
        "Module 1 introduces **Open Source fundamentals**: what it is, why it matters, "
        "its history, common misconceptions, and licensing. The key takeaway is that "
        "open source is about collaboration and transparency — anyone can inspect, "
        "modify, and share the code."
    ),
    r"\b(module|lesson)\b.*\b(2|two)\b": (
        "Module 2 covers **Git fundamentals**: repositories, commits, branching, "
        "merging, remotes, and the standard Git workflow. Focus on understanding "
        "the three-tree architecture (working directory → staging → repository)."
    ),
    r"\bl(icense|icensing)\b": (
        "Licenses tell others what they can and can't do with your code. "
        "The main categories are:\n\n"
        "- **Permissive** (MIT, Apache 2.0, BSD): Few restrictions\n"
        "- **Copyleft** (GPL, AGPL): Derivatives must use same license\n"
        "- **Weak copyleft** (LGPL, MPL): Copyleft for specific files\n\n"
        "Always check the LICENSE file before using or contributing to a project."
    ),
}


class AiTutorService:
    @staticmethod
    def get_response(
        question: str, lesson_context: str = "", history: list | None = None
    ) -> str:
        if not question.strip():
            return "Please ask a question!"

        if getattr(settings, "OPENAI_API_KEY", None):
            return AiTutorService._llm_response(question, lesson_context, history or [])
        return AiTutorService._fallback_response(question)

    @staticmethod
    def _fallback_response(question: str) -> str:
        q_lower = question.lower()

        for pattern, response in {**MARKDOWN_TEMPLATES, **FALLBACK_RESPONSES}.items():
            if re.search(pattern, q_lower):
                return response

        return (
            f"That's a great question about **{question[:60]}...** "
            "I'm currently in offline mode (no AI API key configured). "
            "To get AI-powered answers, set `OPENAI_API_KEY` in your environment. "
            "In the meantime, try asking about **Git**, **commits**, **branches**, "
            "**pull requests**, or **open source licenses**!"
        )

    @staticmethod
    def _llm_response(question: str, lesson_context: str, history: list) -> str:
        try:
            import openai

            openai.api_key = settings.OPENAI_API_KEY
            model = getattr(settings, "LLM_MODEL", "gpt-3.5-turbo")

            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a friendly tutor helping a student learn open source contribution. "
                        "The student is currently studying a lesson. Answer concisely (2-4 sentences), "
                        "use code examples when helpful, and encourage the student. "
                        + (
                            f"\n\nLesson context:\n{lesson_context}"
                            if lesson_context
                            else ""
                        )
                    ),
                },
            ]

            for entry in history[-6:]:
                messages.append({"role": "user", "content": entry.get("question", "")})
                messages.append(
                    {"role": "assistant", "content": entry.get("answer", "")}
                )

            messages.append({"role": "user", "content": question})

            response = openai.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=300,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning("AI tutor LLM call failed: %s", e)
            return AiTutorService._fallback_response(question)
