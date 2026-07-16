## ⚠️ Merge Conflicts — When Two People Edit the Same Thing

Imagine you and a friend are both editing the same sentence in a shared document. You change "The cat sat on the mat" to "The dog sat on the mat." Your friend changes it to "The cat sat on the couch."

Who's right?

Git doesn't know either. When two branches modify the exact same line of a file, Git throws up its hands and says: **"Merge conflict! You decide."**

Don't panic — conflicts are normal, and resolving them is a skill you'll pick up quickly.

---

<div align="center">
   <img width="760" height=auto alt="image" src="https://github.com/user-attachments/assets/b9e04891-8876-4496-93c7-439408b4a70e" />
</div>

---

## 🚨 Understanding Conflict Markers

When a conflict happens, Git pauses and writes special markers into the file:

```md
<<<<<<< HEAD
Our changes here (on the target branch)
=======
Their changes here (on the feature branch)
>>>>>>> feature-branch-name
```

Think of these markers like **Post-it notes** that Git leaves for you, saying: "Here's my version, here's their version — you pick which one to keep (or write something new)."

---

## ✅ How to Resolve Conflicts

### 🖥️ Approach 1 — Using Your Terminal

1. **Open the file** in your code editor.
2. **Edit the file** to choose the correct code. Delete the Git markers (`<<<<<<<`, `=======`, `>>>>>>>`) and keep the lines you want.

   <img width="590" height=auto alt="image" src="https://github.com/user-attachments/assets/c5c2a10a-1a99-4aa0-bf9f-a1025309fda9" />

3. **Save the file.**

4. **Stage and continue:**

   ```bash
   git add <filename>
   git rebase --continue
   ```

---

### 🌐 Approach 2 — Using GitHub's Editor

GitHub also has a built-in conflict resolver:

1. On your PR on GitHub, click **Resolve conflicts**.

   <img width="690" height="286" alt="image" src="https://github.com/user-attachments/assets/8d1db43e-654e-458b-8c17-8fd689f46221" />

2. **Find the conflict markers**:
   - `<<<<<<<` — Your branch's changes
   - `=======` — The divider
   - `>>>>>>>` — The other branch's changes

3. **Edit the file** directly on GitHub. Delete the markers and the code you don't want.

4. **Mark as resolved** — click the **Mark as resolved** button.

   <img width="800" height=auto alt="image" src="https://github.com/user-attachments/assets/9d02d516-f4e6-40ab-86dc-e2d5bf029450" />

5. **Commit the merge** — once all conflicts are resolved, click **Commit merge**.

   <img width="830" height=auto alt="image" src="https://github.com/user-attachments/assets/dcb7ae5f-b265-4f76-be4b-6aaf1b84e870" />

---

## ⚡ Continuing After Resolution

Once you've resolved conflicts in a file:

1. **Stage the resolved file:**

   ```bash
   git add <filename>
   ```

2. **Continue the rebase or merge:**

   ```bash
   git rebase --continue
   ```

---

> [!TIP]
>
> - You can resolve conflicts on GitHub or in your terminal — whichever you're more comfortable with.
> - If you're in the middle of a rebase and hit a conflict, resolve it, then run `git rebase --continue` to pick up where you left off.
> - Conflicts aren't a failure — they're just Git asking you to make a decision.

---

### 🧠 Key Takeaway

Merge conflicts happen when two branches edit the same part of a file. Git marks the conflict, and you choose what to keep. Resolve them in your terminal or on GitHub, then continue. You've got this!
