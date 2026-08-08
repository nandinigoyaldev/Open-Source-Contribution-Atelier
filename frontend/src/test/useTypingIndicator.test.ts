import { renderHook, act } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { useTypingIndicator } from "../hooks/useTypingIndicator";

describe("useTypingIndicator", () => {
  const sendMock = vi.fn();

  beforeEach(() => {
    vi.useFakeTimers();
    sendMock.mockReset();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("adds a user to typingUsers on typing_start", () => {
    const { result } = renderHook(() =>
      useTypingIndicator({ send: sendMock, stopTimeoutMs: 3000 }),
    );

    act(() => {
      result.current.handleTypingMessage({
        action: "typing_start",
        username: "alice",
        user_id: 1,
      });
    });

    expect(result.current.typingUsers).toHaveLength(1);
    expect(result.current.typingUsers[0]).toEqual(
      expect.objectContaining({ username: "alice", user_id: 1 }),
    );
  });

  it("removes a user on typing_stop", () => {
    const { result } = renderHook(() =>
      useTypingIndicator({ send: sendMock, stopTimeoutMs: 3000 }),
    );

    act(() => {
      result.current.handleTypingMessage({
        action: "typing_start",
        username: "alice",
        user_id: 1,
      });
    });

    expect(result.current.typingUsers).toHaveLength(1);

    act(() => {
      result.current.handleTypingMessage({
        action: "typing_stop",
        username: "alice",
        user_id: 1,
      });
    });

    expect(result.current.typingUsers).toHaveLength(0);
  });

  it("auto-expires typing users after stopTimeoutMs", () => {
    const { result } = renderHook(() =>
      useTypingIndicator({ send: sendMock, stopTimeoutMs: 3000 }),
    );

    act(() => {
      result.current.handleTypingMessage({
        action: "typing_start",
        username: "bob",
        user_id: 2,
      });
    });

    expect(result.current.typingUsers).toHaveLength(1);

    // Advance timer past stopTimeoutMs
    act(() => {
      vi.advanceTimersByTime(3500);
    });

    expect(result.current.typingUsers).toHaveLength(0);
  });

  it("removes typing user via removeTypingUser by username or user_id", () => {
    const { result } = renderHook(() =>
      useTypingIndicator({ send: sendMock, stopTimeoutMs: 3000 }),
    );

    act(() => {
      result.current.handleTypingMessage({
        action: "typing_start",
        username: "charlie",
        user_id: 3,
      });
    });

    expect(result.current.typingUsers).toHaveLength(1);

    act(() => {
      result.current.removeTypingUser(3);
    });

    expect(result.current.typingUsers).toHaveLength(0);
  });

  it("clears all typing users via clearAllTypingUsers", () => {
    const { result } = renderHook(() =>
      useTypingIndicator({ send: sendMock, stopTimeoutMs: 3000 }),
    );

    act(() => {
      result.current.handleTypingMessage({
        action: "typing_start",
        username: "user1",
        user_id: 1,
      });
      result.current.handleTypingMessage({
        action: "typing_start",
        username: "user2",
        user_id: 2,
      });
    });

    expect(result.current.typingUsers).toHaveLength(2);

    act(() => {
      result.current.clearAllTypingUsers();
    });

    expect(result.current.typingUsers).toHaveLength(0);
  });
});
