# Pull Requests (PRs)

A **Pull Request** is the bridge between your isolated fork and the main project. It's a formal proposal to merge your code changes into the official codebase.

---

### Key Elements of a Good PR

- **Title**: Clear, descriptive summary of the change (e.g. `feat: implement dark mode switcher`).
- **Description**: Explains:
  - _Why_ the change is necessary.
  - _How_ it was implemented.
  - Links to related issues (e.g. `Closes #42`).
- **Files Changed**: A diff view showing exactly which lines were added, modified, or removed.
- **Reviewers**: Maintainers and other contributors who comment, request revisions, or approve the code.

---

### The Pull Request Cycle

1. You push your branch to GitHub and click **Compare & pull request**.
2. Automated tests (CI/CD) run to verify that your code doesn't break existing features.
3. Reviewers review your code, request changes, or leave comments.
4. You make updates on your local branch and push them; the PR updates automatically.
5. The maintainer clicks **Merge**, and your code is integrated!
