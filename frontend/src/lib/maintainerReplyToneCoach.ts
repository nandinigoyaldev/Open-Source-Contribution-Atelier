/**
 * Maintainer Reply Tone Coach — rule-based etiquette checker.
 * Rubric inspired by Module 4 (Open Source Etiquette) lessons.
 * No paid AI required for v1.
 */

export type ToneFlagCode =
  | "empty"
  | "any_update_ping"
  | "demanding_tone"
  | "missing_context"
  | "excessive_punctuation"
  | "all_caps"
  | "hostile_language"
  | "entitled_tone"
  | "missing_courtesy";

export type ToneFlag = {
  code: ToneFlagCode;
  severity: "error" | "warning" | "info";
  title: string;
  message: string;
};

export type ToneAnalysis = {
  flags: ToneFlag[];
  score: number; // 0–100, higher = more polite / clearer
  ok: boolean;
};

export type EtiquetteExample = {
  id: string;
  label: string;
  bad: string;
  good: string;
  lessonSlug: string;
  tip: string;
};

/** Curriculum-aligned examples (Module 4). */
export const ETIQUETTE_EXAMPLES: EtiquetteExample[] = [
  {
    id: "any-update",
    label: "Respect maintainers' time",
    bad: "any update???",
    good: "Hi! Just checking in when you have a moment — happy to provide more details if needed. No rush.",
    lessonSlug: "respect-and-communication",
    tip: "Most maintainers are volunteers. Avoid “any updates?” pings; wait patiently.",
  },
  {
    id: "helpful-question",
    label: "Write helpful messages",
    bad: "it doesnt work",
    good: "Hi! I'm trying to run `npm test` on Node 20 / Windows 11. I get `Error: Cannot find module 'xyz'`. I already tried deleting node_modules and reinstalling. Any pointers?",
    lessonSlug: "respect-and-communication",
    tip: "Include what you tried, what went wrong, and environment details.",
  },
  {
    id: "feedback-focus",
    label: "Be kind and professional",
    bad: "This code is bad. Fix it ASAP.",
    good: "Thanks for the review context — I think this approach might cause performance issues under large inputs. Would you be open to an alternative that batches the work?",
    lessonSlug: "respect-and-communication",
    tip: "Critique the approach, not the person.",
  },
  {
    id: "assignment",
    label: "Ask before claiming work",
    bad: "I'm taking this. Don't assign anyone else.",
    good: "I'd like to work on this if it's still available. Happy to open a draft PR once assigned.",
    lessonSlug: "professional-prs-and-issues",
    tip: "Comment to request assignment instead of demanding ownership.",
  },
  {
    id: "pr-conversation",
    label: "Stay for the conversation",
    bad: "Merged my changes. Done.",
    good: "Thanks for the feedback! I've updated the branch to address the naming suggestions — let me know if anything else should change.",
    lessonSlug: "professional-prs-and-issues",
    tip: "A PR is a conversation, not a delivery drop-off.",
  },
];

const ANY_UPDATE_RE =
  /\b(any\s+updates?|update\?+|still\s+waiting|bump(?:ing)?|hello\?{2,}|following\s+up\s+again)\b/i;

const DEMANDING_RE =
  /\b(asap|immediately|right\s+now|do\s+this\s+now|fix\s+it\s+now|must\s+merge|you\s+must|need\s+this\s+today)\b/i;

const HOSTILE_RE =
  /\b(stupid|idiot|trash|garbage|useless|your\s+fault|this\s+is\s+bad\s+code|incompetent)\b/i;

const ENTITLED_RE =
  /\b(why\s+hasn'?t|why\s+haven'?t|you\s+should\s+have|i\s+deserve|merge\s+my\s+pr\s+now)\b/i;

const COURTESY_RE =
  /\b(please|thanks|thank\s+you|appreciate|grateful|kindly)\b/i;

const CONTEXT_HINT_RE =
  /\b(error|tried|attempt|steps?|repro|reproduce|version|os|windows|linux|macos|node|python|log|stack|because|when|after|before)\b/i;

export function analyzeMaintainerReply(raw: string): ToneAnalysis {
  const text = raw.replace(/\r\n/g, "\n").trim();
  const flags: ToneFlag[] = [];

  if (!text) {
    return {
      flags: [
        {
          code: "empty",
          severity: "info",
          title: "Start drafting",
          message:
            "Paste or write a reply you’d send on an issue or PR. We’ll check tone against Module 4 etiquette.",
        },
      ],
      score: 0,
      ok: false,
    };
  }

  if (ANY_UPDATE_RE.test(text)) {
    flags.push({
      code: "any_update_ping",
      severity: "error",
      title: "Update ping",
      message:
        "Phrases like “any update???” pressure volunteer maintainers. Prefer a patient check-in with extra context, or wait.",
    });
  }

  if (DEMANDING_RE.test(text)) {
    flags.push({
      code: "demanding_tone",
      severity: "error",
      title: "Demanding tone",
      message:
        "Words like ASAP / immediately / must can sound demanding. Soften with please, timing flexibility, and why it matters.",
    });
  }

  if (HOSTILE_RE.test(text)) {
    flags.push({
      code: "hostile_language",
      severity: "error",
      title: "Harsh wording",
      message:
        "Focus on the technical trade-off, not the person. Kind, specific feedback gets better reviews.",
    });
  }

  if (ENTITLED_RE.test(text)) {
    flags.push({
      code: "entitled_tone",
      severity: "warning",
      title: "Entitled framing",
      message:
        "Avoid “why haven’t you…” framing. Ask collaboratively and assume good intent.",
    });
  }

  const punctHeavy = (text.match(/[?!]{2,}/g) || []).length > 0;
  if (punctHeavy) {
    flags.push({
      code: "excessive_punctuation",
      severity: "warning",
      title: "Extra ??? / !!!",
      message:
        "Multiple question or exclamation marks can read as frustration. One is enough.",
    });
  }

  const letters = text.replace(/[^a-zA-Z]/g, "");
  if (letters.length >= 12 && letters === letters.toUpperCase()) {
    flags.push({
      code: "all_caps",
      severity: "warning",
      title: "ALL CAPS",
      message:
        "All-caps messages feel like shouting. Use normal sentence case.",
    });
  }

  const wordCount = text.split(/\s+/).filter(Boolean).length;
  const looksLikeRequest =
    /\b(can you|could you|please|fix|help|review|merge|assign)\b/i.test(text) ||
    text.includes("?");

  if (wordCount < 8 && !CONTEXT_HINT_RE.test(text)) {
    flags.push({
      code: "missing_context",
      severity: "warning",
      title: "Missing context",
      message:
        "Short replies often lack what you tried, what broke, and environment details. Add a mini map to the problem.",
    });
  }

  if (looksLikeRequest && wordCount >= 4 && !COURTESY_RE.test(text)) {
    flags.push({
      code: "missing_courtesy",
      severity: "info",
      title: "Add a courtesy cue",
      message:
        "A simple please / thanks goes a long way with volunteer maintainers.",
    });
  }

  // Score: start at 100, subtract by severity
  let score = 100;
  for (const flag of flags) {
    if (flag.severity === "error") score -= 28;
    else if (flag.severity === "warning") score -= 14;
    else score -= 6;
  }
  score = Math.max(0, Math.min(100, score));

  const hasBlocking = flags.some((f) => f.severity === "error");
  return {
    flags,
    score,
    ok: !hasBlocking && score >= 70,
  };
}

/** Suggest a rewritten reply based on detected flags (template-based, not AI). */
export function suggestReplyRewrite(raw: string): string {
  const text = raw.replace(/\r\n/g, "\n").trim();
  if (!text) {
    return "Hi! Thanks for your time. I’m happy to share more context or adjust based on your feedback.";
  }

  const analysis = analyzeMaintainerReply(text);
  if (analysis.ok && analysis.flags.every((f) => f.severity === "info")) {
    return text;
  }

  // Prefer curriculum “good” examples when the draft clearly matches a bad pattern
  const lower = text.toLowerCase();
  if (ANY_UPDATE_RE.test(text) || /any\s+update/.test(lower)) {
    return ETIQUETTE_EXAMPLES[0].good;
  }
  if (
    /doesn'?t work|not working|broken/.test(lower) &&
    text.split(/\s+/).length < 12
  ) {
    return ETIQUETTE_EXAMPLES[1].good;
  }
  if (HOSTILE_RE.test(text) || DEMANDING_RE.test(text)) {
    return ETIQUETTE_EXAMPLES[2].good;
  }
  if (/taking this|don'?t assign/.test(lower)) {
    return ETIQUETTE_EXAMPLES[3].good;
  }

  // Generic polite wrapper
  let core = text
    .replace(/[?!]{2,}/g, "?")
    .replace(/\bASAP\b/gi, "when you have capacity")
    .replace(/\bimmediately\b/gi, "when convenient")
    .replace(/\byou must\b/gi, "would you be open to")
    .replace(/\bfix it now\b/gi, "help me understand the preferred fix");

  if (!COURTESY_RE.test(core)) {
    core = `Thanks for your time — ${core}`;
  }
  if (!/\bplease\b/i.test(core) && /\?$/.test(core.trim())) {
    core = core.replace(/\?$/, ", please?");
  }

  return core.trim();
}

export function scoreLabel(score: number): string {
  if (score >= 85) return "Maintainer-friendly";
  if (score >= 70) return "Mostly clear";
  if (score >= 45) return "Needs polish";
  return "Rewrite recommended";
}

/** Lesson slug used for optional XP when a polite rewrite is practiced. */
export const TONE_COACH_LESSON_SLUG = "maintainer-reply-tone-coach";
export const TONE_COACH_XP = 10;
