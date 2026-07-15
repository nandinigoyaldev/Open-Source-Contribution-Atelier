# ⚠️ Merge Conflict Resolution

### When two branches modify the exact same line of a file, Git doesn't know which version to keep. This triggers a **Merge Conflict**.

<div align="center">
   <img width="760" height=auto alt="image" src="https://github.com/user-attachments/assets/b9e04891-8876-4496-93c7-439408b4a70e" />
</div>

---

## 🚨 Understanding Conflict Markers

When a conflict happens, Git pauses and writes markers directly into the files:

```md
<<<<<<< HEAD
Our changes here (on the target branch)
=======
Their changes here (on the feature branch)

> > > > > > > feature-branch-name
```

---

## ✅ Resolving Conflict Markers

You need to resolve these conflict markers in the files.

---

### 1️⃣ Approach 1 : Git/CLI (Terminal)

To resolve:

**1.** Open the file in your code editor.

**2.** Edit the file to choose the correct code, and delete the Git markers (`<<<<<<<`, `=======`, `>>>>>>>`).

<img width="590" height=auto alt="image" src="https://github.com/user-attachments/assets/c5c2a10a-1a99-4aa0-bf9f-a1025309fda9" />
<br><br>

**3.** Save the file.

---

### 1️⃣ Approach 2 : GitHub

<img width="690" height="286" alt="image" src="https://github.com/user-attachments/assets/8d1db43e-654e-458b-8c17-8fd689f46221" />

---

**1. Click 'Resolve Conflicts' and Locate the conflict markers:**
Scroll through the file to find the highlighted conflict sections.

_GitHub will visually group the conflict markers, separated by:_

`<<<<<<<` (Your branch's changes)

`=======` (The divider line)

`>>>>>>>` (The changes from the branch you are merging into)

---

**2. Edit the file directly:**
Decide which code you want to keep. Delete the unwanted code lines and manually delete all the Git conflict markers (<<<<<<<, =======, >>>>>>>).

---

**3. Mark as Resolved:**
Once all markers in that specific file are gone and the code looks correct, click the "Mark as resolved" button in the top-right corner of that file's box.

<img width="800" height=auto alt="image" src="https://github.com/user-attachments/assets/9d02d516-f4e6-40ab-86dc-e2d5bf029450" />

---

**4. Commit the changes:**
Repeat the process for any other conflicting files. Once all conflicts are resolved, click the "Commit merge" button at the top to finalize the merge back into your branch.

<img width="830" height=auto alt="image" src="https://github.com/user-attachments/assets/dcb7ae5f-b265-4f76-be4b-6aaf1b84e870" />

---

## ⚡ Continuing after Resolution

Once you resolve conflicts in a file:

**1.** Stage the file:

```bash
git add <filename>
```

**2.** Continue the paused rebase process:

```bash
git rebase --continue
```

---

> [!TIP]
>
> - You may also resolve conflict markers on GitHub if you prefer that method, not just with Git from your terminal.
> - Run the resume command in your terminal to continue your rebase once conflict resolution is staged: `git rebase --continue`
