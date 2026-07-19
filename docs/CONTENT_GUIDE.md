# Content Contribution Guide

Welcome to the **Open Source Contribution Atelier** content guide! 

This project is designed to be fully content-driven. You do **not** need to modify React code or database tables to create, modify, or extend the curriculum. All lessons, modules, and quizzes are parsed dynamically from static JSON and Markdown assets.

---

## Directory Structure
All educational content is located in the `frontend/public/content/` folder:

```text
frontend/public/content/
├── curriculum.json             # Main catalog mapping modules, lessons, quizzes, and tasks
├── glossary.json               # “Explain like I’m new” OSS jargon for lesson markdown
├── git-cheatsheet-map.json     # Contextual Git terminal cheat-sheet by lesson/module
├── conflict-scenarios/         # Exported merge-conflict practice JSON (authoring)
│   └── api-version-conflict.json
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

3. **Keep API seeds in sync** (important):
   Static `curriculum.json` and Django `Lesson` rows (from `seed_lessons`) can drift. After adding or renaming a slug, run:

   ```bash
   cd backend
   python manage.py check_curriculum_slugs
   # optional CI-style gate:
   python manage.py check_curriculum_slugs --fail-on-drift
   ```

   The lesson UI soft-warns when a curriculum slug is missing from the API; reading still works.

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

---

## Part 4: Lesson Glossary (“Explain Like I’m New”)

Lessons automatically highlight known open-source jargon from [`glossary.json`](../frontend/public/content/glossary.json). Clicking a dotted-underline term opens a short plain-English drawer.

### Adding a term

Edit `frontend/public/content/glossary.json` and append an object to `"terms"`:

```json
{
  "id": "upstream",
  "term": "upstream",
  "aliases": [],
  "short": "The original project you forked from.",
  "definition": "Upstream usually means the main/original repository…"
}
```

- **`id`**: Stable unique key (kebab-case).
- **`term`**: Primary phrase shown in the drawer title.
- **`aliases`**: Optional alternate spellings/plurals matched in lesson text (e.g. `"PRs"`, `"pull requests"`).
- **`short`**: One-line summary (also used for `aria-describedby` / tooltip).
- **`definition`**: Beginner-friendly explanation.

### Matching rules

- Matching is **case-insensitive** and uses **word boundaries** (so `commit` won’t match `commitment`).
- Longer phrases win (e.g. `good first issue` before `issue`).
- Terms inside **fenced code blocks** and **inline `` `code` ``** are **not** linked (avoids false positives).

No React or database changes are required to add glossary terms.

---

## Part 5: Merge Conflict Scenarios (Content Authors)

Conflict practice sandboxes already exist (`ConflictSandbox`). Authors can create new scenarios **without writing React** by exporting JSON from the in-app builder.

### Authoring UI

1. Open **Practice → Conflict Builder** (`/conflict-scenario-builder`).
2. Fill in:
   - **Base** — shared lines before the conflict hunk
   - **Ours** — `HEAD` / current-branch side
   - **Theirs** — incoming / feature-branch side
   - **After** — shared lines after the hunk (optional but recommended)
   - Branch names + a kebab-case `id`
3. Preview the live sandbox, then **Download JSON** or copy the curriculum snippet.

### Where to save files

Place exported files here:

```text
frontend/public/content/conflict-scenarios/
└── api-version-conflict.json   # example included in the repo
```

Suggested path is shown in the builder UI, e.g.  
`frontend/public/content/conflict-scenarios/<id>.json`.

### JSON shape

```json
{
  "id": "api-version-conflict",
  "title": "API version path conflict",
  "description": "…",
  "filePath": "src/api.ts",
  "baseBranchName": "main",
  "featureBranchName": "feat/api-v3",
  "base": "function init() {",
  "ours": "  const fetchUsers = () => api.get('/v2/users');",
  "theirs": "  const fetchUsers = () => api.get('/v3/users', { timeout: 5000 });",
  "after": "}",
  "conflictScenario": {
    "baseBranchName": "main",
    "featureBranchName": "feat/api-v3",
    "fileContent": "function init() {\n<<<<<<< main\n…\n=======\n…\n>>>>>>> feat/api-v3\n}\n"
  }
}
```

- **`conflictScenario`** matches the lesson field already used in `curriculum.json` (`baseBranchName`, `featureBranchName`, `fileContent` with Git markers).
- Use **Copy curriculum snippet** in the builder, then paste `conflictScenario` onto a lesson object in `curriculum.json`.

### Validation tips

- Ours and theirs must differ.
- Provide base and/or after lines so learners see surrounding context.
- Ids must be lowercase kebab-case (`my-scenario-name`).

No backend changes are required to ship a new conflict scenario.
