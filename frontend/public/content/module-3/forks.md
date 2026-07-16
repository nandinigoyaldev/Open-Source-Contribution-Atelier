## 𐂐 Forking a Repository — Your Personal Copy

In open source, you usually can't edit the main project directly. That would be like walking into a library and scribbling in a book on the shelf!

Instead, you make a **fork** — your own personal copy of the project.

---

<div align="center">
  <img width="600" height=auto alt="Untitled design (1)" src="https://github.com/user-attachments/assets/23a980f9-4d45-4d26-9e46-27a3a6e49630" />
</div>

---

## 🗐 What is a Fork?

Think of it like this: imagine you find a recipe book at the store. You can't write in the store's copy. But if you **photocopy** the pages you want (that's your fork), you can write all over your copy — add notes, change ingredients, experiment!

A **Fork** is a copy of a repository that lives under your own GitHub account. Because it's yours:

- You have full permission to create branches, make commits, and delete files
- The original project (called the **upstream** repository) stays completely unchanged

You can experiment freely without worrying about breaking anything for anyone else.

---

## 🛠️ How to Fork a Repo and Raise a Pull Request

Here's the step-by-step process:

1. **Find a repository** you want to contribute to on GitHub.
2. Click the **Fork** button (top-right corner) to copy it to your account.
3. **Clone your fork** to your computer:
   ```bash
   git clone <your-fork-url>
   ```
4. Create a branch, make your edits, and push the changes back to **your fork** (GitHub calls this `origin`).
5. Open a **Pull Request** from your fork's branch to the original project's main branch.

That's it! Your fork is your personal sandbox — play around, break things, learn. When you're ready, you send your changes to the original project through a Pull Request.

---

### 🧠 Key Takeaway

A fork is your personal copy of someone else's project. It gives you a safe space to experiment, and when you're ready, it's the starting point for contributing back to the original.
