# Submit a Mock PR

Let's practice the complete sequence of actions to submit a feature pull request!

---

### Step-by-Step Exercise

Imagine you've forked the repository and cloned it locally. Now, follow this routine:

1. **Create and Switch to a Feature Branch**:
   ```bash
   git switch -c feat/my-first-pr
   ```
2. **Make Edits**:
   Create or modify a file (e.g. `contrib.md`).
3. **Stage Changes**:
   ```bash
   git add contrib.md
   ```
4. **Commit with standard imperatve message**:
   ```bash
   git commit -m "Add my contributor profile"
   ```
5. **Push Branch and Set Upstream tracking**:
   ```bash
   git push -u origin feat/my-first-pr
   ```

---

> [!TIP]
> Run the final push command in the sandbox terminal below to simulate submitting your first pull request upstream!
