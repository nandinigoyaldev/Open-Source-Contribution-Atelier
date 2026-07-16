## 🧲 The Contribution Lifecycle — From Start to Merge

A successful contribution isn't random — it follows a clear path. Think of it like **baking a cake from a recipe**. You gather ingredients, follow steps, check your work, and finally present it. If you skip a step, the cake might not turn out right.

Let's walk through the nine steps of a professional contribution.

---

## The 9-Step Lifecycle

```mermaid
graph TD
    A[1. Pick/Raise Issue] --> B[2. Request Assignment]
    B --> C[3. Get Assigned]
    C --> D[4. Create Branch]
    D --> E[5. Develop/Make Your Changes]
    E --> F[6. Run Local Tests]
    F --> G[7. Create Pull Request]
    G --> H[8. Maintainer Review & Revisions]
    H --> I[9. Merge & Close]

    style A fill:#ff4a4a,stroke:#fff,stroke-width:2px,color:#fff
    style B fill:#ff9f43,stroke:#fff,stroke-width:2px,color:#fff
    style C fill:#f1c40f,stroke:#fff,stroke-width:2px,color:#000
    style D fill:#2ecc71,stroke:#fff,stroke-width:2px,color:#fff
    style E fill:#00f3ff,stroke:#fff,stroke-width:2px,color:#000
    style F fill:#3498db,stroke:#fff,stroke-width:2px,color:#fff
    style G fill:#9b59b6,stroke:#fff,stroke-width:2px,color:#fff
    style H fill:#ff0055,stroke:#fff,stroke-width:2px,color:#fff
    style I fill:#34495e,stroke:#fff,stroke-width:2px,color:#fff
```

---

### 1. Pick or Raise an Issue

Find an existing issue that interests you, or create a new one describing what you want to do.

Think of this like **choosing a recipe**. You wouldn't start cooking without knowing what you're making!

<img width="1140" height="635" alt="image" src="https://github.com/user-attachments/assets/a31a17f6-3c1c-4ebc-b82e-5439afb287d5" />

<img width="828" height="635" alt="image" src="https://github.com/user-attachments/assets/556823b2-4823-4287-864c-885f95b8a9ca" />

---

### 2. Request Assignment

Leave a comment on the issue saying you'd like to work on it. This prevents two people from doing the same work at the same time.

---

### 3. Get Assigned

Wait for a maintainer to officially assign the issue to you. Now it's yours!

<img width="1029" height="774" alt="image" src="https://github.com/user-attachments/assets/812a99f4-ca2b-4441-8412-f93f541d2d0f" />

---

### 4. Create a Branch

Create a new branch from the latest `main` — this keeps your work separate and organized.

```bash
git switch -c feat/my-feature
```

<img width="636" height="478" alt="image" src="https://github.com/user-attachments/assets/cb14a8d5-4244-4b50-a566-f6ae4872def6" />

---

### 5. Make Your Changes

Write clean code that follows the project's style guide. Keep your changes focused on just one thing.

<img width="636" height="478" alt="image" src="https://github.com/user-attachments/assets/b09dd65d-4919-4949-bf93-79407fac8d99" />

---

### 6. Run Tests

Run the project's test suite to make sure you haven't broken anything. If there are no tests for your change, consider adding some!

---

### 7. Open a Pull Request

Push your branch and open a PR. Explain *why* the change is needed and *how* you implemented it.

---

### 8. Review and Revise

Maintainers will review your code and might request changes. Don't worry — this is normal! Make the updates and push to the same branch. The PR updates automatically.

---

### 9. Merge and Close

Once everything looks good, a maintainer merges your code into the project. The issue is closed, and your contribution is live!

<img width="715" height=auto alt="image" src="https://github.com/user-attachments/assets/b2629a32-4eef-452e-a6fe-0c1f14a6bd0b" />

---

### 🧠 Key Takeaway

The contribution lifecycle has nine steps: pick an issue, get assigned, branch, code, test, PR, review, merge, celebrate. Follow this path every time, and you'll be a reliable contributor that maintainers trust.
