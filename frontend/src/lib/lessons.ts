import { fetchApi } from "./api";

export interface Exercise {
  id?: number;
  title: string;
  prompt: string;
  expected_command?: string;
  explanation?: string;
  points?: number;
}

export interface ConflictScenario {
  baseBranchName: string;
  featureBranchName: string;
  fileContent: string; // The file content containing Git conflict markers (<<<<<<< HEAD)
}

export interface PythonExercise {
  prompt: string;
  starterCode: string;
  testCode: string; // Hidden code appended after user code to run assertions
  hint?: string;
}

export interface JSExercise {
  prompt: string;
  starterCode: string;
  testCode: string;
  hint?: string;
}

export interface DebugExercise {
  prompt: string;
  starterCode: string;
  hint?: string;
}

export interface RustExercise {
  prompt?: string;
  starterCode: string;
  expected?: string;
  hint?: string;
}

export interface Lesson {
  slug: string; // used for URL
  title: string;
  description: string; // summary
  explanation: string; // content or long text
  expected: string | RegExp; // validation pattern or exact string
  hint: string;
  difficulty?: string;
  points?: number;
  estimatedMinutes?: number;
  learningObjectives?: string[];
  tips?: string[]; // optional tips/mistakes guidance
  exercises?: Exercise[];
  order?: number;
  filePath?: string;
  quizzes?: Array<{
    question: string;
    options: string[];
    answer: number;
    explanation: string;
  }>;
  conflictScenario?: ConflictScenario;
  pythonExercise?: PythonExercise;
  jsExercise?: JSExercise;
  debugExercise?: DebugExercise;
  category?: string;
}

// Small built-in fallback lessons (used if API unreachable)
export const lessons: Lesson[] = [
  {
    slug: "intro",
    title: "Open Source Mindset",
    description: "Understand how open source collaboration actually works.",
    explanation:
      "Open source is not only about code. It includes communication, issue triage, reviews, and consistency.",
    expected: "open-source means collaboration",
    hint: "Type exactly: open-source means collaboration",
    difficulty: "beginner",
    estimatedMinutes: 8,
    learningObjectives: [
      "Understand contributor and maintainer roles",
      "Know where to start in a new repository",
    ],
    tips: [
      "Small pull requests are reviewed faster.",
      "Always read README and CONTRIBUTING first.",
    ],
    order: 0,
  },
];

// Fetch lessons from live API
export async function fetchLessonsApi(): Promise<Lesson[]> {
  try {
    const data = await fetchApi("/content/lessons/", { requireAuth: false });
    if (!Array.isArray(data)) return lessons;

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (data as any[]).map((les, index: number) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const firstExercise = (les.exercises as any[] | undefined)?.[0];
      return {
        slug: String(les.slug ?? ""),
        title: String(les.title ?? ""),
        description: String(les.summary ?? ""),
        explanation: String(les.content ?? ""),
        expected: String(firstExercise?.expectedCommand ?? ""),
        hint: String(
          firstExercise?.explanation ??
          "Read the lesson contents and solve the check."
        ),
        difficulty: String(les.difficulty ?? "beginner"),
        points: Number(firstExercise?.points ?? 15),
        estimatedMinutes: Number(les.estimatedMinutes ?? 10),
        learningObjectives: Array.isArray(les.learningObjectives) ? les.learningObjectives : [],
        tips: Array.isArray(les.tips) ? les.tips : [],
        exercises: Array.isArray(les.exercises) ? les.exercises : [],
        quizzes: Array.isArray(les.quizzes) ? les.quizzes : [],
        conflictScenario: les.conflictScenario ?? undefined,
        pythonExercise: les.pythonExercise ?? undefined,
        jsExercise: les.jsExercise ?? undefined,
        debugExercise: les.debugExercise ?? undefined,
        order: Number(les.order ?? index),
        category: String(les.category ?? "general"),
        filePath: les.filePath ? String(les.filePath) : undefined,
      } satisfies Lesson;
    });
  } catch (err) {
    console.error("Error loading live curriculum:", err);
    return lessons;
  }
}

export function buildModulesFromLessons(lessonsList: Lesson[]) {
  type ModuleEntry = {
    id: string;
    title: string;
    lessons: { slug: string; title: string; difficulty?: string }[];
  };
  const modulesMap = new Map<string, ModuleEntry>();
  lessonsList.forEach((les) => {
    const cat = les.category || "general";
    if (!modulesMap.has(cat)) {
      modulesMap.set(cat, {
        id: cat,
        title: cat.charAt(0).toUpperCase() + cat.slice(1).replace(/-/g, " "),
        lessons: [],
      });
    }
    // eslint-disable-next-line @typescript-eslint/no-non-null-assertion
    modulesMap.get(cat)!.lessons.push({
      slug: les.slug,
      title: les.title,
      difficulty: les.difficulty,
    });
  });
  return Array.from(modulesMap.values());
}

// Fetch markdown text content for a lesson
export async function fetchLessonContent(filePath: string): Promise<string> {
  try {
    const response = await fetch(`/content/${filePath}`);
    if (!response.ok) throw new Error(`Markdown file not found: ${filePath}`);
    return await response.text();
  } catch (err) {
    console.error("Error loading lesson markdown content:", err);
    return "# Content not found\nCould not retrieve the detailed documentation for this lesson.";
  }
}
