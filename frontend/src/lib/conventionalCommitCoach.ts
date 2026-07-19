/**
 * Conventional Commit Message Coach — validator & rewrite helpers.
 * Spec-inspired rules for first-time open-source contributors.
 */

export const ALLOWED_TYPES = [
  "feat",
  "fix",
  "docs",
  "style",
  "refactor",
  "perf",
  "test",
  "build",
  "ci",
  "chore",
  "revert",
] as const;

export type CommitType = (typeof ALLOWED_TYPES)[number];

export type ValidationIssue = {
  code:
    | "empty"
    | "format"
    | "type"
    | "scope"
    | "subject_empty"
    | "subject_case"
    | "subject_period"
    | "subject_length"
    | "whitespace";
  message: string;
};

export type ValidationResult = {
  valid: boolean;
  issues: ValidationIssue[];
  parsed: {
    type: string | null;
    scope: string | null;
    subject: string | null;
  };
};

const HEADER_RE =
  /^(?<type>[a-zA-Z]+)(?:\((?<scope>[^)]*)\))?(?<breaking>!)?:\s*(?<subject>.*)$/;

const MAX_SUBJECT_LENGTH = 72;

export function validateCommitMessage(raw: string): ValidationResult {
  const message = raw.replace(/\r\n/g, "\n").trim();
  const issues: ValidationIssue[] = [];
  const parsed = {
    type: null as string | null,
    scope: null as string | null,
    subject: null as string | null,
  };

  if (!message) {
    return {
      valid: false,
      issues: [
        {
          code: "empty",
          message:
            "Commit message is empty. Start with a type like feat or fix.",
        },
      ],
      parsed,
    };
  }

  if (/\s{2,}/.test(message) || message !== raw.trim()) {
    // only flag internal double spaces in the trimmed message
    if (/\s{2,}/.test(message)) {
      issues.push({
        code: "whitespace",
        message: "Avoid extra spaces. Use a single space after the colon.",
      });
    }
  }

  const match = message.match(HEADER_RE);
  if (!match?.groups) {
    issues.push({
      code: "format",
      message:
        'Use the format type(scope): subject — for example "feat(auth): add login form". Scope is optional.',
    });
    return { valid: false, issues, parsed };
  }

  const type = match.groups.type ?? "";
  const scope = match.groups.scope ?? null;
  const subject = (match.groups.subject ?? "").trim();

  parsed.type = type;
  parsed.scope = scope;
  parsed.subject = subject || null;

  const typeLower = type.toLowerCase();
  if (!(ALLOWED_TYPES as readonly string[]).includes(typeLower)) {
    issues.push({
      code: "type",
      message: `"${type}" is not a known type. Allowed: ${ALLOWED_TYPES.join(", ")}.`,
    });
  } else if (type !== typeLower) {
    issues.push({
      code: "type",
      message: `Type should be lowercase. Use "${typeLower}" instead of "${type}".`,
    });
  }

  if (scope !== null) {
    if (!scope.trim()) {
      issues.push({
        code: "scope",
        message:
          "Scope is empty. Either remove the parentheses or add a short scope like (auth).",
      });
    } else if (/\s/.test(scope)) {
      issues.push({
        code: "scope",
        message:
          "Scope should be a short kebab-case word without spaces (e.g. auth, api, ui).",
      });
    }
  }

  if (!subject) {
    issues.push({
      code: "subject_empty",
      message: "Add a short subject after the colon describing what changed.",
    });
  } else {
    if (/^[A-Z]/.test(subject)) {
      issues.push({
        code: "subject_case",
        message:
          'Subject should start with a lowercase letter (e.g. "add login form").',
      });
    }
    if (subject.endsWith(".")) {
      issues.push({
        code: "subject_period",
        message: "Do not end the subject with a period.",
      });
    }
    if (subject.length > MAX_SUBJECT_LENGTH) {
      issues.push({
        code: "subject_length",
        message: `Subject is too long (${subject.length} chars). Keep it under ${MAX_SUBJECT_LENGTH} characters.`,
      });
    }
  }

  return {
    valid: issues.length === 0,
    issues,
    parsed,
  };
}

/**
 * Attempt to rewrite an invalid (or rough) message into a valid Conventional Commit.
 */
export function suggestCommitRewrite(raw: string): string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return "feat: describe your change here";
  }

  const match = trimmed.match(HEADER_RE);
  let type = "feat";
  let scope: string | null = null;
  let subject = trimmed;

  if (match?.groups) {
    const rawType = (match.groups.type ?? "").toLowerCase();
    type = (ALLOWED_TYPES as readonly string[]).includes(rawType)
      ? rawType
      : "chore";
    const rawScope = match.groups.scope;
    if (rawScope && rawScope.trim() && !/\s/.test(rawScope.trim())) {
      scope = rawScope.trim().toLowerCase();
    }
    subject =
      (match.groups.subject ?? "").trim() || "describe your change here";
  } else {
    // Heuristic: first word might be a type
    const parts = trimmed.split(/\s+/);
    const maybeType = parts[0]?.toLowerCase().replace(/:$/, "");
    if ((ALLOWED_TYPES as readonly string[]).includes(maybeType)) {
      type = maybeType;
      subject =
        parts.slice(1).join(" ").replace(/^:\s*/, "").trim() ||
        "describe your change here";
    } else {
      subject = trimmed;
    }
  }

  subject = subject.replace(/\.$/, "");
  if (subject) {
    subject = subject.charAt(0).toLowerCase() + subject.slice(1);
  }
  if (subject.length > MAX_SUBJECT_LENGTH) {
    subject = subject.slice(0, MAX_SUBJECT_LENGTH).trim();
  }

  return scope ? `${type}(${scope}): ${subject}` : `${type}: ${subject}`;
}

export function buildPrChecklistTemplate(commitMessage: string): string {
  const msg = commitMessage.trim() || "feat: your change";
  return `## Summary
- ${msg}

## Test plan
- [ ] Ran relevant frontend/backend tests
- [ ] Checked UI in light and dark theme (if UI change)
- [ ] Updated docs if needed

## Checklist
- [ ] Conventional Commit message used
- [ ] Scope matches the issue / PR title
- [ ] No unrelated files included
`;
}

export const COMMIT_TYPE_HINTS: { type: CommitType; hint: string }[] = [
  { type: "feat", hint: "A new feature for users" },
  { type: "fix", hint: "A bug fix" },
  { type: "docs", hint: "Documentation only" },
  { type: "style", hint: "Formatting, no logic change" },
  {
    type: "refactor",
    hint: "Code change that neither fixes a bug nor adds a feature",
  },
  { type: "perf", hint: "Performance improvement" },
  { type: "test", hint: "Adding or fixing tests" },
  { type: "build", hint: "Build system or dependencies" },
  { type: "ci", hint: "CI configuration" },
  { type: "chore", hint: "Maintenance tasks" },
  { type: "revert", hint: "Reverts a previous commit" },
];
