## 🏅 Your First Contribution — Let's Do This!

Welcome! You're about to make your very first open source contribution. This might feel like a big step, but we're going to walk through it together, one small step at a time.

Think of this like **making your first deposit at a bank**. You have something valuable (your code or your idea), and you're about to add it to a shared account (the project). Let's go!

---

## ⚠️ Step 1: Raise an Issue

Every great contribution starts with a conversation. First, you need to let the project know what you're planning to do.

---

### Step-by-Step

1. **Go to the Issues Tab**  
   Navigate to the original project on GitHub and click the **Issues** tab.

   <img width="415" height="90" alt="image" src="https://github.com/user-attachments/assets/519029d7-732c-430b-b9ff-fcf88562fe47" />

2. **Click New Issue**  
   Hit the green **New Issue** button.

   <img width="415" height="90" alt="image" src="https://github.com/user-attachments/assets/cd9a626b-f7f3-4d53-8a27-179ef7c6b811" />

3. **Choose a Template (if offered)**  
   Pick the template that fits best — like "Bug Report" or "Feature Request" — or click **Open a blank issue**.

   <img width="637" height="596" alt="image" src="https://github.com/user-attachments/assets/cfee857a-08ee-4c8a-bb01-a42eeda9d716" />

4. **Fill in the Details**  
   Give your issue a clear title and describe what you plan to do.

5. **Submit**  
   Click **Submit new issue** and note down the issue number (e.g. `#123`). You'll need it later for your Pull Request!

   <img width="180" height=auto alt="image" src="https://github.com/user-attachments/assets/6ae2077f-1b9d-4a51-b8d0-94a251ed4707" />

---

## 🍴 Step 2: Fork the Repository

Now you need your own copy of the project to work on.

---

### Step-by-Step

1. Go to the main page of the project on GitHub.
2. Click the **Fork** button in the top-right corner.

   <img width="1133" height="116" alt="image" src="https://github.com/user-attachments/assets/41ec9cf4-3eed-45aa-9aaf-7042a748bc94" />

3. Choose your personal GitHub account as the destination.

   <img width="644" height="473" alt="image" src="https://github.com/user-attachments/assets/aa18df5c-a718-4f8c-bfa2-9a379401a9f6" />

4. **Clone your fork** to your computer:

   ```bash
   git clone https://github.com/YOUR-USERNAME/target-repository.git
   ```

---

## 🧲 Step 3: Submit a Pull Request

Now for the exciting part — sending your changes back to the original project!

---

### 🖥️ Approach 1 — Using the Terminal

1. **Create and switch to a new branch**:

   ```bash
   git switch -c feat/my-first-pr
   ```

2. **Make your changes** — edit a file or create a new one.

3. **Stage your changes**:

   ```bash
   git add CONTRIBUTING.md
   ```

   To stage all changes at once:

   ```bash
   git add .
   ```

4. **Commit with a clear message**:

   ```bash
   git commit -m "Update the CONTRIBUTING.md file"
   ```

5. **Push your branch to your fork**:

   ```bash
   git push -u origin feat/my-first-pr
   ```

---

### 🌐 Approach 2 — Using GitHub

1. **Create and switch to a new branch**:

   ```bash
   git switch -c feat/my-first-pr
   ```

2. **Make your changes** and save the file.

3. **Stage and commit**:

   ```bash
   git add contrib.md
   git commit -m "Add my contributor profile"
   ```

4. **Push your branch**:

   ```bash
   git push -u origin feat/my-first-pr
   ```

5. **Open the Pull Request on GitHub**:
   - Go to your forked repository on GitHub.
   - Click the green **Compare & pull request** button.

     <img width="300" height=auto alt="image" src="https://github.com/user-attachments/assets/329a36bd-af80-4ff1-8975-8860ca460013" />

   - Write a clear title and reference your issue in the description (e.g. `Closes #123`).

     <img width="1029" height="673" alt="image" src="https://github.com/user-attachments/assets/a11f89bf-7068-4f99-a481-fedf9a694a2c" />

   - Click **Create pull request**.

     <img width="260" height=auto alt="image" src="https://github.com/user-attachments/assets/d3868140-cb64-4c2a-9c40-02209faa1b44" />

---

> [!TIP]
>
> - **Keep PRs Small**: A good pull request does exactly one thing. If you spot other small issues while working, resist the urge to fix them in the same PR. Open a new issue and a new branch instead.
>
> - **Use Draft PRs**: If your work isn't finished but you'd like early feedback, click the dropdown next to "Create pull request" and select **Create draft pull request**. This tells maintainers "not ready yet, but feel free to peek."
>
> - **Clean Up Your Commits**: Try to squash tiny "oops" commits (like "fix typo" or "test 2") before requesting a review. A clean history makes it easier for maintainers to understand your changes.
>
> - **NEVER Commit Secrets**: Passwords, API keys, access tokens — never, ever commit these to GitHub. Double-check your files before staging.

---

### 🧠 Key Takeaway

You raised an issue, forked a repo, made changes, and submitted a pull request. That's the complete open source contribution cycle! You did it. 🎉 Every expert was once where you are right now.
