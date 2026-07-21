## Merging: Bringing It All Together

You've built a cool new feature on your branch. It works. You've tested it. Now it's time to bring it back to the main project.

That's called **merging**.

---

## 🔗 What Happens When You Merge?

Merging takes the changes from one branch and combines them into another. Git is smart about this — it looks at the history of both branches and figures out how to combine them automatically.

Think of it like two rivers flowing back together after going around an island.

---

## 🛠️ How to Merge

Let's say you have a feature branch called `feat/add-readme` and you want to merge it into `main`:

1. **Switch to the branch you want to merge INTO** (usually `main`):

```bash
git switch main
```

2. **Merge the feature branch**:

```bash
git merge feat/add-readme
```

Git will combine the changes and create a **merge commit** — a special commit that records that the branches came back together.

---

## 🧠 An Analogy: Team Editing

Imagine two people editing separate copies of the same book:

- Person A works on Chapter 5 (their branch)
- Person B works on Chapter 6 (main branch)

When Person A finishes, they "merge" their chapter back into the main book. Now the book has both chapters, and no work was lost.

---

## ⚠️ What Could Go Wrong?

Sometimes Git can't automatically merge — this is called a **merge conflict**.

This happens when:

- You and someone else edited the **same line** of the **same file**
- Git doesn't know whose version to keep

Don't panic! Conflicts are normal. We'll learn how to fix them in a later module.

---

## 💡 The Normal Workflow

1. Create a branch → `git switch -c my-feature`
2. Do your work → edit files, `git add`, `git commit`
3. Merge back → `git switch main` then `git merge my-feature`

---

## 🧪 Try It Yourself

In the sandbox:

1. Switch to main: `git switch main`
2. Merge a branch: `git merge feat/add-readme`

---

## 📝 Quick Check

[interactive-quiz id="quiz-9"]
