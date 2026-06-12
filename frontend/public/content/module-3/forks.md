# Forks on GitHub

In open source, you usually do not have direct write permissions to edit the main repository of a project. To make changes, you use a **Fork**.

---

### What is a Fork?

A **Fork** is a copy of a repository that is created under your own GitHub account.

Because the fork belongs to you:

- You have complete write permission to create branches, push commits, and delete files.
- The original (upstream) project remains unaffected by your local edits.

### The Fork-and-PR Workflow

1. Find a repository you want to contribute to.
2. Click the **Fork** button on GitHub to copy it to your account.
3. Clone _your fork_ to your computer:
   ```bash
   git clone <your-fork-url>
   ```
4. Create a branch, edit files, and push changes back to _your fork_ (origin).
5. Open a **Pull Request** from your fork's branch to the original project's main branch.
