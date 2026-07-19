## The Daily Git Workflow: Stage, Commit, Repeat

Every developer — from beginners to pros — follows the same basic rhythm when working with Git. It's like a dance, and once you learn the steps, it becomes second nature.

---

## 👣 The Three-Step Dance

1. **Make changes** → Edit your files
2. **Stage changes** → Tell Git which changes to include
3. **Commit** → Save the snapshot

That's it. Everything else is just variations on these three steps.

---

## 🧠 An Analogy: Cooking

| Step | Git          | Cooking                    |
| ---- | ------------ | -------------------------- |
| 1    | Edit files   | Chop vegetables            |
| 2    | `git add`    | Put veggies in a bowl      |
| 3    | `git commit` | Put the bowl in the fridge |

You can keep adding more veggies to the bowl before you put it in the fridge. Once it's in the fridge (committed), it's safely saved.

---

## 🛠️ The Commands You'll Use Daily

### 1. Check what's happening

```bash
git status
```

This is the most important command. Run it constantly. It tells you:

- Which files you've changed
- Which files are staged (ready to commit)
- Which files Git isn't tracking yet

**Seriously. Run `git status` all the time. It's your best friend.**

### 2. Stage your changes

```bash
git add filename.py
```

Or to stage everything at once:

```bash
git add .
```

But be careful with `git add .` — you might accidentally include files you didn't mean to. Always check `git status` first!

### 3. Commit your snapshot

```bash
git commit -m "Add login button to homepage"
```

The `-m` flag lets you write a message explaining what you did. Good commit messages are:

- **Present tense**: "Add button" not "Added button"
- **Specific**: "Fix crash on login page" not "Fix stuff"
- **Concise**: Short and sweet

---

## 🔍 A Complete Workflow Example

```bash
# 1. Check what needs to be done
git status

# 2. You see: "modified: index.html, modified: style.css"

# 3. Stage the files
git add index.html style.css

# 4. Check again to make sure
git status

# 5. Commit!
git commit -m "Update homepage layout and colors"

# 6. Celebrate small wins 🎉
```

---

## ⚠️ Common Beginner Mistakes

| Mistake                          | The Fix                                                             |
| -------------------------------- | ------------------------------------------------------------------- |
| Committing without staging first | Git will tell you — just `git add` then commit again                |
| Writing vague commit messages    | "Fix stuff" → be specific: "Fix broken link on about page"          |
| `git add .` without checking     | Run `git status` before `git add` to see what'll be included        |
| Forgetting to commit             | Your changes are safe in your editor, but not in Git. Commit often! |

---

## 💡 The Golden Rule

**Commit early, commit often.**

Small, frequent commits are better than one huge commit. They're easier to understand, easier to undo, and make you look like a pro.

---

## 🧪 Try It Yourself

In the sandbox terminal:

1. Run `git status`
2. Create a file
3. Run `git status` again — see the difference?
4. Run `git add` on your file
5. Run `git status` — notice how it moved to "staged"
6. Run `git commit -m "My first commit!"`

---

## 📝 Quick Check

[interactive-quiz id="quiz-11"]
