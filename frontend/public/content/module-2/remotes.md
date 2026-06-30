# Git Remotes

A local repository on your machine lives in isolation. To share code with others, you must connect it to a **remote repository** hosted on a server (like GitHub, GitLab, or Bitbucket).

---

### Origin vs. Upstream

- **Origin**: This is the default name Git gives to the server repository you cloned or pushed code to. Typically, it points to your personal fork of a project.
- **Upstream**: In open source, "upstream" refers to the original parent project repository that you forked from. Keeping sync with upstream is essential to avoid conflicts.

### Working with Remotes

- **List Remotes**:
  ```bash
  git remote -v
  ```
- **Add a Remote**:
  ```bash
  git remote add upstream <repository-url>
  ```
- **Fetch Remote Updates**:
  ```bash
  git fetch origin
  ```

---

> [!TIP]
> Run `git remote -v` in the sandbox terminal below to inspect the registered remote links!
