# 🗂️ Repositories & Commits

### To collaborate in open source, you must understand the terminologies **'repositories'** and **'commits'**.

---

## 📁 What is a Repository?

A **repository** (or "repo") is a directory containing all your project files.

It also contains these essential files:

- The `.git` folder is a hidden folder that holds the entire database of all changes, versions, and branches.
- The `.gitignore` file specifies the files in the repository which must not be committed when making changes to the codebase.
- The `README.md` file is the file that appears on the main page of the repository, and contains information about the repository and its contents.
- Other files, such as `CONTRIBUTING.md` (which lays out guidelines and templates for contributors), `LICENSE.md` (which specificies the type of license and project copyright, if any).

---

## 📤 What is a Commit?

A **commit** is a snapshot of your files at a specific point in time. Think of it as a save game in a video game. If you make a mistake, you can revert back to any previous commit.
A commit pushes all the changes which are currently in the staging area.

To commit your changes:

```bash
git init
```

---

## 🌲 Working Tree States

In Git, files reside in one of 3 states:

1. **Working Directory**: Modifying files locally but not tracked yet.
2. **Staging Area**: Selecting files you want to include in your next snapshot.
3. **Git Directory (Repository)**: Files committed safely in the database.

---

## ,🚀 Getting Started

To turn any local folder into a Git repository, run:

```bash
git init
```

This will initialize a Git repository inside your project folder.

---

> [!TIP]
> Run `git init` in your terminal to start tracking your project!
