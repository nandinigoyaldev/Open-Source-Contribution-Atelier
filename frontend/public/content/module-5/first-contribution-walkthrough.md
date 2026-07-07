# 🏅 First Contribution Walkthrough

### In this module, you will complete the entire process of making your first contribution - raising an issue in your target repisitory, cloning the repository, and submitting a pull request.

---

## ⚠️ Raise an Issue

### First, you need to raise an issue in your target repository!

---

### Step-by-Step Exercise

1. **Navigate to the Issues Tab**:
   Go to the original (upstream) repository on GitHub and click the Issues tab.
   
   <img width="415" height="90" alt="image" src="https://github.com/user-attachments/assets/519029d7-732c-430b-b9ff-fcf88562fe47" />

3. **Create a New Issue**:
   Click the green New Issue button.
   
   <img width="415" height="90" alt="image" src="https://github.com/user-attachments/assets/cd9a626b-f7f3-4d53-8a27-179ef7c6b811" />

5. **Choose a Template**:
   If prompted, select the most relevant template (e.g., Bug Report or Feature Request), or click "Open a blank issue."
   
   <img width="637" height="596" alt="image" src="https://github.com/user-attachments/assets/cfee857a-08ee-4c8a-bb01-a42eeda9d716" />

7. **Fill in the Details**:
   Give your issue a clear, descriptive title and explain what you plan to change or fix in the body.

8. **Submit the Issue**:
   Click Submit new issue and note down the issue number (e.g., #123) for your pull request.
   
   <img width="180" height=auto alt="image" src="https://github.com/user-attachments/assets/6ae2077f-1b9d-4a51-b8d0-94a251ed4707" />

---

## 🍴 Fork the Repository

### Now you need to fork the repository - make a copy of it on your own profile.

---

### Step-by-Step Exercise

1. **Navigate to the Repository**: 
   Open GitHub and go to the main page of the target project you want to contribute to.
   
3. **Click the Fork Button**: 
   In the top-right corner of the page, click the **Fork** button.
   
   <img width="1133" height="116" alt="image" src="https://github.com/user-attachments/assets/41ec9cf4-3eed-45aa-9aaf-7042a748bc94" />

5. **Select Your Account**: 
   Choose your personal GitHub account as the destination for the fork.
   
   <img width="644" height="473" alt="image" src="https://github.com/user-attachments/assets/aa18df5c-a718-4f8c-bfa2-9a379401a9f6" />

7. **Clone the Fork Locally**: 
   Copy the URL of your new fork and run the clone command in your terminal:
   
   ```bash
   git clone https://github.com/YOUR-USERNAME/target-repository.git
   ```

---

## 🧲 Submit a Mock Pull Request

### Finally, you need to create a PR linking back to your issue and submit it for approval by the repository's maintainer.

---

### 1️⃣ Approach 1 - Git/CLI (Terminal) : Step-by-Step Exercise

1. **Create and Switch to your Feature Branch**:
   ```bash
   git switch -c feat/my-first-pr
   ```
   
2. **Make Edits**:
   Create or modify a file (e.g. `CONTRIBUTING.md`).
   
3. **Stage Changes / Make files ready for committing**:
   ```bash
   git add CONTRIBUTING.md
   ```

   OR, to stage all modified files at once:
   ```bash
   git add .
   ```
   
4. **Commit with standard imperatve message**:
   ```bash
   git commit -m "Update the CONTRIBUTING.md file"
   ```
   
5. **Push Branch and Set Upstream tracking**:
   ```bash
   git push -u origin feat/my-first-pr
   ```

---

### 2️⃣ Approach 2 - GitHub : Step-by-Step Exercise

1. **Create and Switch to a Feature Branch**:
   ```bash
   git switch -c feat/my-first-pr
   ```
   
2. **Make Edits**:
   Create or modify a file (e.g. `contrib.md`).
   
4. **Stage Changes**:
   ```bash
   git add contrib.md
   ```
   
5. **Commit with standard imperatve message**:
   ```bash
   git commit -m "Add my contributor profile"
   ```
   
6. **Push Branch and Set Upstream tracking**:
   ```bash
   git push -u origin feat/my-first-pr
   ```

7. **Open the Pull Request on GitHub**:
   - Navigate to your forked repository page on GitHub.
     
   - Click the green Compare & pull request button next to the yellow banner.
     
     <img width="300" height=auto alt="image" src="https://github.com/user-attachments/assets/329a36bd-af80-4ff1-8975-8860ca460013" />

   - Add a descriptive title and reference your issue in the description (e.g., Closes #123). Add a description of your changes.
     
     <img width="1029" height="673" alt="image" src="https://github.com/user-attachments/assets/a11f89bf-7068-4f99-a481-fedf9a694a2c" />

   - Click Create pull request.
  
     <img width="260" height=auto alt="image" src="https://github.com/user-attachments/assets/d3868140-cb64-4c2a-9c40-02209faa1b44" />

---

> [!TIP]
> - **Keep PRs Single-Purpose**: A good pull request does exactly one thing. If you notice unrelated typos or minor bugs while working, resist the urge to fix them in the same PR. Open a separate issue and branch for them instead.
> - **Draft PRs for Work in Progress:** If your contribution isn't quite finished but you want early feedback or to test it in the project's CI pipeline, click the dropdown next to "Create pull request" and select **Create draft pull request**. This tells maintainers it isn't ready for a final review yet.
> - **Clean Commit History:** Try to squash unnecessary intermediate commits (like "fix typo", "test 2") before requesting a final review. A clean commit history makes it much easier for maintainers to understand your changes.
> - **NEVER Commit Secrets** (e.g. Passwords, Access tokens, API Keys, etc.) to GitHub.
