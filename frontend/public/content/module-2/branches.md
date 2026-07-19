## Branches: Your Own Private Workspace

Imagine you and a friend are both writing the same document. If you both edit the same page at the same time, you'll overwrite each other's work. Chaos!

Now imagine you each get your own copy of the document. You write your changes on your copy, your friend writes theirs on their copy. When you're both done, you merge the best parts together.

That's what **branches** do in Git.

---

## 🌿 What's a Branch?

A branch is your own private workspace. You can make changes here without affecting anyone else's work.

- The **main branch** (usually called `main`) is the official, stable version of the project
- **Feature branches** are where you experiment and build new things
- Branches are **lightweight** — creating one is instant and free

---

## 🧠 An Analogy: A Tree

Think of your project as a tree:

- The **trunk** (`main` branch) is the stable version
- Each **branch** is like a limb growing in a different direction
- Branches can grow back into the trunk (merging)
- You can cut off a branch if it doesn't work out — the tree is fine

---

## 🛠️ Creating and Switching Branches

To create a new branch and immediately switch to it:

```bash
git switch -c my-new-feature
```

Think of `-c` as "create". You're saying: "Create a new branch called `my-new-feature` and move me there."

The older way (you might see this in tutorials):

```bash
git checkout -b my-new-feature
```

Both do the same thing. `switch` is the newer, clearer command.

To switch between existing branches:

```bash
git switch main
```

---

## 📝 Good Branch Names

Good branch names are descriptive:

| Instead of... | Use...                  |
| ------------- | ----------------------- |
| `my-branch`   | `feat/add-login-button` |
| `fix`         | `fix/nav-not-working`   |
| `stuff`       | `docs/update-readme`    |

Prefixes like `feat/`, `fix/`, `docs/` help everyone understand what the branch is for.

---

## 💡 The Golden Rule

**Never commit directly to `main`.**

Always create a branch, do your work there, then merge it back. This keeps `main` clean and stable at all times.

---

## 🧪 Try It Yourself

In the sandbox terminal, try:

1. Run `git switch -c my-first-branch`
2. Switch back with `git switch main`
3. Create another branch and explore

---

## 📝 Quick Check

[interactive-quiz id="quiz-8"]
