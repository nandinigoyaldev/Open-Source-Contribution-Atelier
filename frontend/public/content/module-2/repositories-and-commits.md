# Repositories & Commits

To collaborate in open source, you must understand **Git**, the distributed version control system that tracks the history of files.

---

### What is a Repository?

A **repository** (or "repo") is a directory containing all your project files and a hidden folder named `.git`. This `.git` folder holds the entire database of all changes, versions, and branches.

### What is a Commit?

A **commit** is a snapshot of your files at a specific point in time. Think of it as a save game in a video game. If you make a mistake, you can revert back to any previous commit.

---

### Working Tree States

In Git, files reside in one of three states:

1. **Working Directory**: Modifying files locally but not tracked yet.
2. **Staging Area**: Selecting files you want to include in your next snapshot.
3. **Git Directory (Repository)**: Files committed safely in the database.

---

### Getting Started

To turn any local folder into a Git repository, run:

```bash
git init
```

> [!TIP]
> Run `git init` in the terminal below to start tracking your project!
