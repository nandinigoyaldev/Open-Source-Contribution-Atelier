# Rebasing & Squashing

In large open source projects, commit histories can quickly become messy. Maintainers prefer clean, linear histories using **rebase** and **squash**.

---

### What is Rebasing?

**Rebasing** is the process of moving or combining a sequence of commits to a new base commit. Instead of a merge commit, rebasing rewrites history by applying your branch's changes one-by-one on top of the target branch (e.g. `main`).

```
Before Rebase:
      A---B---C (feature)
     /
D---E---F---G (main)

After Rebase:
              A'--B'--C' (feature)
             /
D---E---F---G (main)
```

### What is Squashing?

**Squashing** combines multiple local commits (e.g. `fix typo`, `add test`, `fix lint`) into a single, clean commit (e.g. `feat: add email verification`) before merging. This keeps the project's main branch log neat.

---

### Syncing with Rebase

To update your feature branch with the latest changes on `main`:

```bash
git fetch origin
git rebase origin/main
```

> [!TIP]
> Run `git rebase main` in the terminal below to practice applying your changes directly on top of the master branch!
