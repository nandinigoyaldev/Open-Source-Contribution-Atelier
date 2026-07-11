# 🎋 Git Branching

### In open source, multiple developers work on the same codebase simultaneously. To prevent people from overwriting each other's changes, we work in **branches**.

---

## 🪾 What is a Branch?

A **branch** is an independent line of development, a workspace for you to make changes to the codebase without affecting the original/main branch.

By default, every repository starts with a default branch (usually named `main` or `master`).

When you want to add a feature or fix a bug in the codebase:

1. You create a new branch off of `main`/`master`.
2. You write your code and commit your changes on this new branch.
3. Your work is isolated: the `main`/`master` branch remains clean and stable.

---

## 🛠️ Creating and Switching Branches

To create a new branch and switch to it immediately in one step, run:

```bash
git switch -c <branch-name>
```

_(Or the older syntax: `git checkout -b <branch-name>`)_

To create a branch first, and then switch to it, run:

```
git branch <branch-name>
git switch <branch-name>
```

---

## 📤 Pushing Changes from your Local Branch to a Remote Branch

To push changes from your local Git branch to a remote repository, you must first stage and commit your files locally, then use the **`git push`** command. If this is the very first time you are pushing a newly created local branch, you need to use the **`git push -u`** command to link it to the remote server.

### 1. Stage your changes

Prepare your modified or new files to be committed by adding them to the staging area.

```bash
git add .
```

> **Note:** The `.` stages all modified and new files in the current directory. Replace it with a specific filename (e.g., `git add index.html`) if you only want to stage one file.

---

### 2. Commit your changes

Save your staged changes locally by creating a commit with a descriptive message.

```bash
git commit -m "Your descriptive commit message here"
```

---

### 3. Push to the remote repository

Depending on your branch status, choose one of the options below to push your changes:

#### 📌 Option A: If this is a brand new local branch (e.g., `feature-branch`)

You need to set the upstream tracking branch on the remote server (usually called `origin`). This links your local branch to the remote branch so Git knows where to pull/push in the future. This only needs to be done once.

```bash
git push -u origin feature-branch
```

_(Note: `-u` is short for `--set-upstream`. Once you run this, you can just type `git push` or `git pull` for this branch in the future)._

#### 📌 Option B: Setting up and pushing to the `main` branch for the first time

If you just initialized a brand new repository and want to push your local `main` branch to GitHub/GitLab, you first tell Git where the remote repository lives, and then push with tracking:

```bash
# 1. Link your local repo to the remote server (only done once per project)
git remote add origin https://github.com/username/repo-name.git

# 2. Rename your default branch to main (if it isn't already)
git branch -M main

# 3. Push and set the tracking upstream
git push -u origin main
```

#### 📌 Option C: If the branch already exists on the remote

If tracking is already established from a previous push (or you are working on an already-tracked `main` branch), simply run:

```bash
git push
```

---

### 4. Troubleshoot common errors

#### ⚠️ `fatal: The current branch has no upstream branch.`

- **Why it happens:** You used a plain `git push` on a brand-new local branch instead of using Option A.
- **How to fix it:** Run `git push -u origin <branch-name>` to link it.

#### ⚠️ `Updates were rejected because the remote contains work...`

- **Why it happens:** Someone else pushed changes to this branch on the remote server while you were working locally, or you created files on GitHub (like a README) that your local machine doesn't have yet.
- **How to fix it:** Safely pull and integrate their changes first by running:

```bash
git pull origin <branch-name>
```

Once the changes are merged (and any conflicts are resolved), try running `git push` again.

---

> [!IMPORTANT]
> Always create descriptive branch names, e.g. `feat/add-login` or `fix/nav-accessibility`. Never make commits directly on the `main` branch!
