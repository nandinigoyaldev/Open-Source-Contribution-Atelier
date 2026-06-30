# Merging Branches

Once you have finished development and tested your changes on a feature branch, you need to bring those changes back into the main branch. This is called **merging**.

---

### How Merging Works

Merging combines two independent branch histories together. Git automatically finds the common base commit, compares the changes, and creates a special "merge commit" incorporating both histories.

### The Merge Command

To merge changes:

1. First, switch to the branch you want to merge _into_ (e.g. `main`):
   ```bash
   git switch main
   ```
2. Run the merge command with the name of the feature branch:
   ```bash
   git merge <feature-branch-name>
   ```

---

> [!NOTE]
> If changes overlap on the exact same lines, Git might trigger a **Merge Conflict**. Don't worry! We will learn how to handle conflicts in a later module.
