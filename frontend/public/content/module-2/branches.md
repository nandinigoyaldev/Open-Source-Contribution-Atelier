# Git Branching

In open source, multiple developers work on the same codebase simultaneously. To prevent people from overwriting each other's work, we use **branches**.

---

### What is a Branch?

A **branch** is an independent line of development. By default, every repository starts with a default branch (usually named `main` or `master`).

When you want to add a feature or fix a bug:

1. You spin up a new branch branching off of `main`.
2. You write your code and commit changes on this new branch.
3. Your work is isolated: the `main` branch remains clean and stable.

### Creating and Switching Branches

To create a new branch and switch to it immediately, run:

```bash
git switch -c <branch-name>
```

_(Or the older syntax: `git checkout -b <branch-name>`)_

---

> [!IMPORTANT]
> Always create descriptive branch names, e.g. `feat/add-login` or `fix/nav-accessibility`. Never make commits directly on the `main` branch!
