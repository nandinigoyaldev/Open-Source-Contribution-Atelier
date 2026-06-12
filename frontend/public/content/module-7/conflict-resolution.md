# Conflict Resolution

When two branches modify the exact same line of a file, Git doesn't know which version to keep. This triggers a **Merge Conflict**.

---

### Understanding Conflict Markers

When a conflict happens, Git pauses and writes markers directly into the files:

```md
<<<<<<< HEAD
Our changes here (on the target branch)
=======
Their changes here (on the feature branch)

> > > > > > > feature-branch-name
```

To resolve:

1. Open the file in your code editor.
2. Edit the file to choose the correct code, and delete the Git markers (`<<<<<<<`, `=======`, `>>>>>>>`).
3. Save the file.

### Resuming after resolution

Once you resolve conflicts in a file:

1. Stage the file:
   ```bash
   git add <filename>
   ```
2. Continue the paused rebase process:
   ```bash
   git rebase --continue
   ```

---

> [!TIP]
> Run the resume command in the sandbox below to continue your rebase once conflict resolution is staged: `git rebase --continue`
