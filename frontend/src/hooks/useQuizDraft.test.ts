import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { useQuizDraft } from "./useQuizDraft";

describe("useQuizDraft", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("saves and retrieves a draft", () => {
    const { result } = renderHook(() => useQuizDraft("test-quiz-1"));

    act(() => {
      result.current.saveDraft(2, 1, null, 30);
    });

    const draft = result.current.getDraft();
    expect(draft).not.toBeNull();
    expect(draft?.quizId).toBe("test-quiz-1");
    expect(draft?.currentQuizIndex).toBe(2);
    expect(draft?.selectedOption).toBe(1);
    expect(draft?.timeLeft).toBe(30);
  });

  it("clears the draft", () => {
    const { result } = renderHook(() => useQuizDraft("test-quiz-2"));

    act(() => {
      result.current.saveDraft(1, 0, null, null);
    });
    expect(result.current.getDraft()).not.toBeNull();

    act(() => {
      result.current.clearDraft();
    });
    expect(result.current.getDraft()).toBeNull();
  });

  it("restores draft from sessionStorage on mount", () => {
    const draft = {
      quizId: "test-quiz-3",
      currentQuizIndex: 3,
      selectedOption: 2,
      quizFeedback: null,
      timeLeft: 15,
      savedAt: Date.now(),
    };
    sessionStorage.setItem("quiz_draft_test-quiz-3", JSON.stringify(draft));

    const { result } = renderHook(() => useQuizDraft("test-quiz-3"));
    const restored = result.current.getDraft();
    expect(restored?.currentQuizIndex).toBe(3);
    expect(restored?.selectedOption).toBe(2);
  });

  it("does nothing when quizId is undefined", () => {
    const { result } = renderHook(() => useQuizDraft(undefined));

    act(() => {
      result.current.saveDraft(0, 0, null, null);
    });

    expect(result.current.getDraft()).toBeNull();
  });

  it("persists data to sessionStorage", () => {
    const { result } = renderHook(() => useQuizDraft("test-quiz-4"));

    act(() => {
      result.current.saveDraft(1, 3, "correct", 0);
    });

    const raw = sessionStorage.getItem("quiz_draft_test-quiz-4");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.quizFeedback).toBe("correct");
  });
});

describe("useQuizDraft malformed data", () => {
  beforeEach(() => sessionStorage.clear());

  it.each([
    ["not json", "{oops"],
    ["wrong shape", JSON.stringify({ quizId: "q", selectedOption: "x" })],
    [
      "other quiz id",
      JSON.stringify({
        quizId: "other",
        currentQuizIndex: 0,
        selectedOption: 1,
        quizFeedback: null,
        timeLeft: null,
        savedAt: 1,
      }),
    ],
  ])("ignores %s", (_n, raw) => {
    sessionStorage.setItem("quiz_draft_q", raw);
    const { result } = renderHook(() => useQuizDraft("q"));
    expect(result.current.getDraft()).toBeNull();
  });

  it("keeps the saved answer after a failed submit and remount", () => {
    const first = renderHook(() => useQuizDraft("q2"));
    act(() => first.result.current.saveDraft(1, 2, null, null));
    first.unmount();
    const second = renderHook(() => useQuizDraft("q2"));
    expect(second.result.current.getDraft()?.selectedOption).toBe(2);
  });
});
