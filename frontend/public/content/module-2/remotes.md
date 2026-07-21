## Remotes: Connecting Your Computer to the World

Right now, your repository only exists on YOUR computer. No one else can see it. To share your work with others, you need to connect it to a **remote** — a repository hosted somewhere on the internet (like GitHub, GitLab, or Bitbucket).

---

## 🌐 What's a Remote?

A **remote** is a link between your local repository and a repository hosted online. Think of it as a bridge that lets you send and receive code.

You can have multiple remotes:

- **`origin`** — your personal copy on GitHub (where you push your changes)
- **`upstream`** — the original project you forked from (where you get updates)

---

## 🧠 An Analogy: Sending a Letter

- Your **local repo** is the letter you wrote on your desk
- **`origin`** is your mailbox — you put the letter there to send it
- **`upstream`** is your friend's mailbox — they might send you letters too
- **`git push`** is mailing the letter
- **`git pull`** is checking your mailbox for new letters

---

## 🛠️ Common Remote Commands

**See your remotes:**

```bash
git remote -v
```

This lists all remotes and their URLs.

**Add a new remote:**

```bash
git remote add origin https://github.com/your-username/your-repo.git
```

**Send your code to a remote:**

```bash
git push origin main
```

**Get updates from a remote:**

```bash
git pull origin main
```

---

## 🔄 Sync in Open Source

When contributing to someone else's project:

1. **Fork** their repo on GitHub → creates your copy
2. **Clone** your fork → downloads it to your computer
3. Add their repo as **`upstream`** → so you can get their latest changes
4. **Push** your changes to **`origin`** → your fork on GitHub
5. Open a **Pull Request** → ask them to pull your changes

```
Your Computer  →  origin (your GitHub)  →  upstream (their GitHub)
```

---

## 💡 Key Reminders

- `origin` = your remote copy
- `upstream` = the original project's remote
- `git push` sends your commits to a remote
- `git pull` gets commits from a remote
- You always push BEFORE you open a pull request

---

## 🧪 Try It Yourself

In the sandbox terminal:

```bash
git remote -v
```

This will show you which remotes are connected.

---

## 📝 Quick Check

[interactive-quiz id="quiz-10"]
