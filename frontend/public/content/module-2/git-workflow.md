# Staging & Reviewing Status

The daily cycle of a developer consists of checking file modifications, selecting what changes are ready for a commit, and logging them.

---

### The Status Check

Before doing anything, always inspect the state of your working directory:

```bash
git status
```

This lists:

- Which files have been modified.
- Which files are staged and ready to commit.
- Untracked files that Git isn't tracking yet.

### The Standard Workflow

1. Make code changes in your text editor.
2. Check changes: `git status`
3. Stage files: `git add <filename>` (or `git add .` to stage all changes)
4. Commit: `git commit -m "Describe the change in present tense"`

---

> [!CAUTION]
> Avoid running `git add .` blindly on unfamiliar open source projects. You might accidentally stage log files, API keys, or build outputs. Use `git status` to verify!
