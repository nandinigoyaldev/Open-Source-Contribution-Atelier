import { useCallback, useRef } from "react";

const STORAGE_PREFIX = "quiz_draft_";

export interface QuizDraft {
  quizId: string;
  currentQuizIndex: number;
  selectedOption: number | null;
  quizFeedback: "correct" | "incorrect" | "timeout" | null;
  timeLeft: number | null;
  savedAt: number;
}

function getStorageKey(quizId: string): string {
  return `${STORAGE_PREFIX}${quizId}`;
}

function isValidDraft(value: unknown, quizId: string): value is QuizDraft {
  if (!value || typeof value !== "object") return false;
  const d = value as Record<string, unknown>;
  return (
    d.quizId === quizId &&
    Number.isInteger(d.currentQuizIndex) &&
    (d.currentQuizIndex as number) >= 0 &&
    (d.selectedOption === null ||
      (Number.isInteger(d.selectedOption) &&
        (d.selectedOption as number) >= 0)) &&
    (d.quizFeedback === null ||
      d.quizFeedback === "correct" ||
      d.quizFeedback === "incorrect" ||
      d.quizFeedback === "timeout") &&
    (d.timeLeft === null || typeof d.timeLeft === "number")
  );
}

function readDraft(quizId: string | undefined): QuizDraft | null {
  if (!quizId) return null;
  try {
    const raw = sessionStorage.getItem(getStorageKey(quizId));
    if (raw) {
      const parsed = JSON.parse(raw);
      if (isValidDraft(parsed, quizId)) return parsed;
    }
  } catch {
    // Ignore corrupt data
  }
  return null;
}

export function useQuizDraft(quizId: string | undefined) {
  const draftRef = useRef<QuizDraft | null>(null);
  if (draftRef.current === null || draftRef.current.quizId !== quizId) {
    draftRef.current = readDraft(quizId);
  }

  const saveDraft = useCallback(
    (
      currentQuizIndex: number,
      selectedOption: number | null,
      quizFeedback: "correct" | "incorrect" | "timeout" | null,
      timeLeft: number | null,
    ) => {
      if (!quizId) return;
      const draft: QuizDraft = {
        quizId,
        currentQuizIndex,
        selectedOption,
        quizFeedback,
        timeLeft,
        savedAt: Date.now(),
      };
      draftRef.current = draft;
      try {
        sessionStorage.setItem(getStorageKey(quizId), JSON.stringify(draft));
      } catch {
        // Storage quota exceeded or unavailable
      }
    },
    [quizId],
  );

  const getDraft = useCallback((): QuizDraft | null => {
    return draftRef.current;
  }, []);

  const clearDraft = useCallback(() => {
    if (!quizId) return;
    draftRef.current = null;
    try {
      sessionStorage.removeItem(getStorageKey(quizId));
    } catch {
      // Ignore storage errors
    }
  }, [quizId]);

  return { saveDraft, getDraft, clearDraft };
}
