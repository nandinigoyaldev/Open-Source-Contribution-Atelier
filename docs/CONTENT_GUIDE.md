# Content Contribution Guide

Welcome to the **Open Source Contribution Atelier** content guide! 

This project is designed to be fully content-driven. You do **not** need to modify React code or database tables to create, modify, or extend the curriculum. All lessons, modules, and quizzes are parsed dynamically from static JSON and Markdown assets.

---

## Directory Structure
All educational content is located in the `frontend/public/content/` folder:

```text
frontend/public/content/
├── curriculum.json             # Main catalog mapping modules, lessons, quizzes, and tasks
├── module-1/                   # Markdown files for Module 1
│   ├── what-is-open-source.md
│   └── ...
├── module-2/                   # Markdown files for Module 2
│   ├── repositories-and-commits.md
│   └── ...
└── ...
```

---

## Part 1: How to Add or Modify Modules & Lessons
To add a new lesson or create a module:

1. **Register it in `curriculum.json`**:
   Open [curriculum.json](file:///Users/nandini/Downloads/open/Open-Source-Contribution-Atelier/frontend/public/content/curriculum.json) and add your module or lesson item to the `"modules"` array.
   
   Example lesson entry inside a module:
   ```json
   {
     "slug": "git-stash-basics",
     "title": "Stashing Changes",
     "description": "Learn to save your dirty working tree changes temporarily.",
     "difficulty": "intermediate",
     "estimatedMinutes": 8,
     "points": 20,
     "filePath": "module-2/git-stash-basics.md",
     "expected": "git stash",
     "hint": "Run: git stash"
   }
   ```
   
2. **Create the Markdown file**:
   Create the corresponding markdown file at the path listed in the `"filePath"` parameter. In this case: `frontend/public/content/module-2/git-stash-basics.md`.

---

## Part 2: How to Add Quizzes
If a lesson is conceptual/theoretical (e.g. licensing or etiquette), it is validated using multiple-choice quizzes rather than Git terminal commands.

To add a quiz, define the `"quizzes"` array in the lesson object inside `curriculum.json`:

```json
"quizzes": [
  {
    "question": "What does 'git clone' do?",
    "options": [
      "It deletes a local branch history.",
      "It copies a remote repository to your local computer.",
      "It forces changes to be merged upstream.",
      "It deletes untracked staging assets."
    ],
    "answer": 1,
    "explanation": "'git clone' is used to download an existing repository from a remote host onto your computer."
  }
]
```

- **`answer`**: The 0-indexed index of the correct option in the `"options"` array (e.g., `1` represents the 2nd option).
- **`explanation`**: A helpful note displayed to the learner after they answer correctly.

---

## Part 3: Markdown Formatting Tips
The platform uses a custom, lightweight markdown parser styled using the neobrutalist aesthetic. 

We support:
1. **GitHub Alert Panels**:
   ```md
   > [!NOTE]
   > For general notes and descriptions.
   
   > [!TIP]
   > For tips and optimizations.
   
   > [!IMPORTANT]
   > For rules and requirements.
   
   > [!WARNING]
   > For things developers should avoid.
   ```
2. **Code Blocks**:
   Use standard triple-backticks with language names.
3. **Tables**:
   Use standard markdown pipes (`|`) for side-by-side comparisons.
4. **Lists**:
   Use `-` for bullets, and `1.` for ordered lists.
5. **Inline Styling**:
   Use `**bold**`, `` `inline code` ``, and `[links](url)`.
