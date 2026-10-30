# Guide to Writing Accessible Lessons

Accessible lessons help more learners understand and use the Open Source Contribution Atelier curriculum, including learners who use screen readers, keyboard navigation, or other assistive technologies.

This guide gives lesson authors practical ways to make educational content clear, readable, and easier to navigate.

For general lesson structure and Markdown authoring instructions, see the [Content Contribution Guide](CONTENT_GUIDE.md). For the repository's contribution process, see the [Contributing Guide](CONTRIBUTING.md).

---

## 1. Use Clear and Logical Headings

Headings divide a lesson into sections and help readers understand its structure. They also allow assistive technology users to navigate directly between sections.

### Good practices

- Use one main heading (`#`) for the lesson title.
- Use `##` for major sections and `###` for subsections.
- Keep heading levels in a logical order.
- Write headings that describe the content of the section.
- Do not choose a heading level just because its visual size looks better.

### Good example

```md
# Understanding Git Branches

## What Is a Branch?

A branch lets you work on changes independently.

## Creating a Branch

### Using the Terminal

Run the following command to create a branch.
```

### Bad example

```md
# Understanding Git Branches

#### What Is a Branch?

A branch lets you work independently.

## Creating a Branch
```

The second example jumps from a level-one heading to a level-four heading without a clear reason.

**Remember:** A logical heading hierarchy makes a lesson easier to scan and navigate. Do not use bold text as a replacement for a heading when the content is actually a new section.

---

## 2. Write Descriptive Link Text

Links should tell readers what they will open or where they will go. Avoid link text that makes sense only from its surrounding visual position.

### Good practices

- Use meaningful text that describes the destination.
- Make link text understandable when read on its own.
- Give different destinations different descriptions.
- Avoid vague phrases such as "click here", "read more", or "this link".
- Do not rely only on a raw URL to explain why a resource is useful.

### Good example

```md
Read the [GitHub documentation about creating a pull request](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests).
```

### Bad example

```md
Click [here](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests) to learn more.
```

The good example explains the destination before the reader opens it. The bad example does not explain what the link contains.

**Remember:** A reader should be able to understand the purpose of a link without guessing.

---

## 3. Make Code Examples Understandable

Code examples are an important part of technical lessons. They should be easy to identify, read, and follow.

### Good practices

- Use fenced code blocks with the correct language identifier.
- Introduce an example with a short explanation of what it demonstrates.
- Keep examples focused on one concept at a time.
- Use clear names and consistent formatting.
- Explain important commands, flags, placeholders, and expected results.
- Do not communicate an important instruction through syntax highlighting or color alone.
- Use inline code formatting for short commands, filenames, and code references.

### Good example

`````md
Create a branch named `feature-login`:

```bash
git switch -c feature-login
```

Expected result: Git switches to the newly created `feature-login` branch.

### Bad example

````md
```text
git sw -c
```
````
`````

The bad example is incomplete, has no language identifier, and does not explain what the command does.

**Remember:** Code should be accompanied by enough context for a learner to understand when and why to use it. Use realistic examples, and clearly mark placeholders such as `<branch-name>`.

---

## 4. Do Not Rely on Color Alone

Color can help organize information, but it should never be the only way a learner identifies a warning, result, status, or instruction.

Some learners may have difficulty distinguishing certain colors, and some devices or display settings may show colors differently.

### Good practices

- Pair colors with descriptive text, labels, icons, or patterns.
- Explain success, failure, and warning states in words.
- Make text readable against its background.
- Maintain sufficient contrast between text and its background.
- Do not use color as the only way to identify the correct answer in a quiz.
- Keep meaning understandable when viewed in grayscale.

### Good example

```md
- **Success:** Your changes have been committed.
- **Warning:** The branch contains uncommitted changes.
- **Error:** The requested file could not be found.
```

### Bad example

```md
- Green = success
- Yellow = warning
- Red = error
```

The bad example relies entirely on color and does not explain the meaning to someone who cannot distinguish the colors.

**Remember:** Use clear words in addition to visual styling. Color should reinforce meaning, not carry it by itself.

---

## 5. Make Interactive Content Keyboard-Friendly

Some learners navigate using a keyboard instead of a mouse. Interactive examples, quizzes, navigation controls, and practice activities should support predictable keyboard use.

### Good practices

- Make interactive controls reachable using the `Tab` key.
- Allow users to move backwards through controls using `Shift + Tab`.
- Use visible focus indicators so learners can identify the currently focused control.
- Use `Enter` or `Space` for appropriate actions, according to the control type.
- Keep the focus order logical and consistent with the content.
- Do not use a positive `tabindex` value to force an artificial focus order.
- Do not require dragging, hovering, or clicking as the only way to complete an activity.
- For dialogs or menus, provide a predictable way to close or leave the interaction, such as the `Escape` key where appropriate.
- Make the purpose of each interactive control clear.

### Good example

A multiple-choice activity can provide:

- Keyboard-accessible answer options.
- A clear indication of the focused option.
- A keyboard-accessible submit or check-answer control.
- Feedback that explains whether the answer is correct or incorrect.

### Bad example

A practice activity that requires learners to drag an answer into a box, with no keyboard alternative.

**Remember:** Test the activity without using a mouse. Every essential action should have a usable keyboard interaction.

---

## 6. Keep Instructions and Content Easy to Understand

Accessible content is also clear content. Learners should not need to guess what an instruction means or remember information from an unrelated section to complete an activity.

### Good practices

- Prefer short, direct sentences.
- Explain unfamiliar technical terms when they first appear.
- Introduce acronyms before using them repeatedly.
- Give instructions in the order learners should follow them.
- Use numbered lists for steps that must be completed in sequence.
- Use bullet lists for related items that do not have a required order.
- Explain error messages and expected outcomes.
- Avoid instructions that depend only on location, such as "click the green button on the right".

### Good example

```md
1. Open your terminal.
2. Run `git status`.
3. Review the files listed under uncommitted changes.
```

### Bad example

```md
Run the command from above and click the button on the right.
```

The bad example depends on visual position and unclear references.

---

## 7. Check Your Lesson Before Submitting

Use this checklist when creating or updating a lesson.

### Content structure

- [ ] The lesson has a clear title and logical heading hierarchy.
- [ ] Sections and instructions follow a meaningful order.
- [ ] Technical terms and abbreviations are explained when needed.

### Links and code

- [ ] Link text describes its destination.
- [ ] Code blocks use the correct language identifier.
- [ ] Code examples include enough explanation to be understood.
- [ ] Commands and expected results are clearly distinguished.

### Visual presentation

- [ ] Important information is not communicated through color alone.
- [ ] Text is readable against its background.
- [ ] Warnings, errors, and success states have descriptive labels.

### Keyboard accessibility

- [ ] Interactive controls can be reached using the keyboard.
- [ ] The focus indicator is visible.
- [ ] The focus order is logical.
- [ ] Essential actions do not require a mouse or hover.

---

## 8. Use the Project's Existing Accessibility Checks

The repository includes accessibility checks using Playwright and axe-core.

The end-to-end accessibility test is located at:

`frontend/e2e/accessibility/a11y-ci.spec.ts`

It scans configured application routes for accessibility violations using WCAG 2.2 A and AA-related tags.

To run the configured accessibility tests:

```bash
cd frontend
npm run test:a11y
```

The frontend package dependencies and Playwright configuration must already be set up. The test configuration starts or reuses the Vite development server at `http://localhost:5173`.

Automated checks are useful for identifying common accessibility issues, but they do not replace manual checks. In particular, review keyboard navigation, focus visibility, and whether instructions make sense to learners.

For broader accessibility guidance, use the [W3C Web Accessibility Initiative (WAI)](https://www.w3.org/WAI/).

---

## Final Reminder

Accessible lesson writing is not about adding extra complexity. It is about presenting information in a way that more learners can understand and use.

Use clear headings, meaningful links, readable code examples, text alongside color, and keyboard-friendly interactions. Review your work with the checklist above before submitting a content contribution.
