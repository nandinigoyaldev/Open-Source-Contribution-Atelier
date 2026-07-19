## 🏗️ Rebasing and Squashing — Keeping History Clean

In large open source projects, commit history can get messy fast. Imagine a shared journal where everyone writes their grocery list, then crosses things out, then rewrites them. It would be impossible to follow!

That's why maintainers love **rebasing** and **squashing** — two tools that keep your commit history clean and readable.

---

## 🔨 What is Rebasing?

**Rebasing** is like moving your train of thought to the front of the line.

Imagine you're working on a feature while someone else updates the `main` branch. Your branch is now based on old code. Rebasing replays your changes on top of the latest `main`, as if you started your work from the newest version.

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

The letters A, B, C are your commits. After rebasing, they sit neatly on top of the latest main (G). No messy merge commits!

---

#### Terminal Example

```bash
git fetch origin
git rebase origin/main
```

<img width="690" height="191" alt="image" src="https://github.com/user-attachments/assets/9e7c8b12-d442-4ed5-b0fc-e9bc24226f4d" />

---

## 📥 What is Squashing?

**Squashing** is like **combining several scratch notes into one clean page**.

When you're working on a feature, you might make many small commits: "fix typo", "add test", "oops, fix again", "actually this works now". That's fine for your local work, but when you share it, you want one clean commit like `feat: add email verification`.

Squashing combines all those tiny commits into one.

<img width="670" height=auto alt="image" src="https://github.com/user-attachments/assets/10ffa6c3-be4a-490f-83e6-b99555b54ffc" />

---

## 🔄 Syncing Your Branch with Rebase

To update your feature branch with the latest changes from `main`:

```bash
git fetch origin
git rebase origin/main
```

This grabs the latest `main`, then applies your commits on top.

---

## 🆚 Merge vs. Rebase vs. Squash

| Feature            | 🔗 Git Merge                              | 🔨 Git Rebase                                       | 📥 Git Squash                    |
| ------------------ | ----------------------------------------- | --------------------------------------------------- | -------------------------------- |
| **What it does**   | Combines branches with a new merge commit | Moves your commits to a new starting point          | Combines many commits into one   |
| **History impact** | Keeps all branch history                  | Rewrites commit IDs for a clean line                | Drops individual commit messages |
| **Best for**       | Team branches you want to preserve        | Keeping a clean, linear story                       | Cleaning up before merging       |
| **Pro**            | Safe and easy to undo                     | Easy to read and debug                              | One clean commit per feature     |
| **Con**            | Extra merge commits clutter history       | Can cause conflicts (don't rebase shared branches!) | Harder to trace small changes    |

---

> [!IMPORTANT]
>
> - **Rebasing** moves your commits to a new base, keeping history linear.
> - **Squashing** combines multiple small commits into one clean commit.
> - **Golden rule**: Never rebase or squash branches that others are also working on. Only do it to your own feature branches.

---

### 🧠 Key Takeaway

Rebase to keep your history linear. Squash to keep your commits clean. Together, they make maintainers' lives easier and your contributions look professional.
