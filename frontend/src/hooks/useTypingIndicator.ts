import { useState, useRef, useCallback } from "react";

type TypingUser = {
  username: string;
  user_id: number;
};

type UseTypingIndicatorOptions = {
  send: (data: unknown) => void;
  debounceMs?: number;
  stopTimeoutMs?: number;
};

export function useTypingIndicator({
  send,
  debounceMs = 1500,
  stopTimeoutMs = 3000,
}: UseTypingIndicatorOptions) {
  const [typingUsers, setTypingUsers] = useState<TypingUser[]>([]);
  const typingTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map(),
  );
  const isTypingRef = useRef(false);
  const typingDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const removeTypingUser = useCallback((username: string) => {
    setTypingUsers((prev) => prev.filter((u) => u.username !== username));
    const timer = typingTimersRef.current.get(username);
    if (timer) {
      clearTimeout(timer);
      typingTimersRef.current.delete(username);
    }
  }, []);

  const addTypingUser = useCallback(
    (username: string, userId: number) => {
      setTypingUsers((prev) => {
        if (prev.some((u) => u.username === username)) return prev;
        return [...prev, { username, user_id: userId }];
      });

      const existingTimer = typingTimersRef.current.get(username);
      if (existingTimer) clearTimeout(existingTimer);

      const timer = setTimeout(() => {
        removeTypingUser(username);
      }, stopTimeoutMs);
      typingTimersRef.current.set(username, timer);
    },
    [removeTypingUser, stopTimeoutMs],
  );

  const handleTypingMessage = useCallback(
    (data: { action: string; username: string; user_id: number }) => {
      if (data.action === "typing_start") {
        addTypingUser(data.username, data.user_id);
      } else if (data.action === "typing_stop") {
        removeTypingUser(data.username);
      }
    },
    [addTypingUser, removeTypingUser],
  );

  const notifyTyping = useCallback(() => {
    if (!isTypingRef.current) {
      isTypingRef.current = true;
      send({ action: "typing_start" });
    }
    if (typingDebounceRef.current) clearTimeout(typingDebounceRef.current);
    typingDebounceRef.current = setTimeout(() => {
      isTypingRef.current = false;
      send({ action: "typing_stop" });
    }, debounceMs);
  }, [send, debounceMs]);

  const stopTyping = useCallback(() => {
    if (isTypingRef.current) {
      isTypingRef.current = false;
      send({ action: "typing_stop" });
    }
    if (typingDebounceRef.current) {
      clearTimeout(typingDebounceRef.current);
      typingDebounceRef.current = null;
    }
  }, [send]);

  const onInputChange = useCallback(() => {
    notifyTyping();
  }, [notifyTyping]);

  const onInputBlur = useCallback(() => {
    stopTyping();
  }, [stopTyping]);

  const onInputSubmit = useCallback(() => {
    stopTyping();
  }, [stopTyping]);

  return {
    typingUsers,
    handleTypingMessage,
    onInputChange,
    onInputBlur,
    onInputSubmit,
  };
}
