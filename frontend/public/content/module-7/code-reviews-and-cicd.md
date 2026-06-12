# CI/CD and Check Lists

In open source, projects use **Continuous Integration (CI)** pipelines to run automated tests on every single pull request. This ensures that new contributions do not break the existing program.

---

### What happens when you open a PR?

GitHub automatically triggers runners that perform:

- **Build Checks**: Verifies that the code compiles successfully without syntax errors.
- **Unit & Integration Tests**: Runs the project's test suite (e.g. Jest, Pytest) to confirm all specs pass.
- **Linter checks**: Confirms your code format follows standard styling expectations (Prettier, ESLint).
- **Code Coverage**: Tracks what percentage of the new lines are tested.

---

> [!IMPORTANT]
> If a check fails (indicated by a red cross `❌` on GitHub), check the test logs! Fix the issues locally and push updates to your branch to trigger the tests again. Do not ask for reviews if tests are red!
