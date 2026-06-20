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

// Fetch lessons from local curriculum JSON asset
export async function fetchLessonsApi(): Promise<Lesson[]> {
  try {
    const response = await fetch("/content/curriculum.json");
    if (!response.ok) {
      throw new Error("Failed to load curriculum.json");
    }
    const data = await response.json();
    if (!data || !Array.isArray(data.modules)) return lessons;

    const allLessons: Lesson[] = [];
    let orderIndex = 0;

    for (const mod of data.modules) {
      if (!Array.isArray(mod.lessons)) continue;
      for (const les of mod.lessons) {
        allLessons.push({
          slug: les.slug,
          title: les.title,
          description: les.description || "",
          explanation: "", // Will load dynamically from markdown content
          expected: les.expected || "",
          hint: les.hint || "Read the lesson contents and solve the check.",
          difficulty: les.difficulty || "beginner",
          points: les.points || 15,
          estimatedMinutes: les.estimatedMinutes || 10,
          learningObjectives: les.learningObjectives || [],
          tips: les.tips || [],
          exercises: les.exercises || [],
          quizzes: les.quizzes || [],
          conflictScenario: les.conflictScenario || undefined,
          order: orderIndex++,
          filePath: les.filePath,
        });
      }
    }
    return allLessons;
  } catch (err) {
    console.error("Error loading curriculum JSON:", err);
    return lessons;
  }
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
