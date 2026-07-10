# 🏗️ Rebasing & Squashing

### In large open source projects, commit histories can quickly become messy. Maintainers prefer clean, linear histories using **rebase** and **squash**.

---

## 🔨 What is Rebasing?

**Rebasing** is the process of combining or moving a sequence of commits to a new base commit. Instead of a merge commit, rebasing rewrites history by applying your branch's changes one-by-one on top of the target branch (e.g. `main`).

```plaintext
Before Rebase:

      A---B---C (feature)
     /
D---E---F---G (📍 main)


After Rebase:

              A'--B'--C' (feature)
             /
D---E---F---G (📍 main)
```

#### Terminal Example

<img width="690" height="191" alt="image" src="https://github.com/user-attachments/assets/9e7c8b12-d442-4ed5-b0fc-e9bc24226f4d" />

---

## 📥 What is Squashing?

**Squashing** combines multiple local commits (e.g. `fix typo`, `add test`, `fix lint`) into a single, clean commit (e.g. `feat: add email verification`) before merging. This keeps the project's main branch log neat.

<img width="670" height=auto alt="image" src="https://github.com/user-attachments/assets/10ffa6c3-be4a-490f-83e6-b99555b54ffc" />

---

## 🔄 Syncing with Rebase

To update your feature branch with the latest changes on `main`, run this in your terminal:

```bash
git fetch origin
git rebase origin/main
```

---

## 🆚 Merge vs. Rebase vs. Squash

| Feature            | 🔗 Git Merge                                                             | 🔨 Git Rebase                                                                 | 📥 Git Squash                                                                            |
| ------------------ | ------------------------------------------------------------------------ | ----------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| **Core Concept**   | Combines branches by creating a new merge commit                         | Applies commits from one branch onto another                                  | Combines many commits into a single commit                                               |
| **History Impact** | Keeps the full history of all branches                                   | Gives commits new IDs while applying them on top of another branch            | Compresses changes and drops extra commit messages                                       |
| **Best Practice**  | It lets you merge feature branches into the main branch on team projects | It lets you keep a clean and linear history, but never rebase shared branches | It lets you clean up the feature branch before merging, but never squash a shared branch |
| **Pros**           | Safe, easy to undo, simple to understand                                 | Linear history, easier to understand and debug                                | Clean history and allows one commit per feature                                          |
| **Cons**           | Extra merge commits can clutter history                                  | Risk of confusion and conflicts on shared branches from changed commit IDs    | Harder to revert small parts or trace changes as history gets lost                       |

---

> [!IMPORTANT]
>
> - Rebasing is combining your commits and moving them to a new base commit - it rewrites history by applying your branch's changes one-by-one on top of the other target branch.
> - Squashing is combining multiple local commits into a single, clean commit before merging. This keeps the repo's main branch log neat.
