import { useState, useRef, useCallback, useEffect } from "react";

export type TypingUser = {
  username: string;
  user_id: number;
  lastTypedAt?: number;
};

type UseTypingIndicatorOptions = {
  send: (data: unknown) => void;
  debounceMs?: number;
  stopTimeoutMs?: number;
};

export function useTypingIndicator({
  send,
  debounceMs = 800,
  stopTimeoutMs = 4000,
}: UseTypingIndicatorOptions) {
  const [typingUsers, setTypingUsers] = useState<TypingUser[]>([]);
  const typingTimersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(
    new Map(),
  );
  const isTypingRef = useRef(false);
  const typingDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const removeTypingUser = useCallback((identifier: string | number) => {
    if (!identifier) return;
    setTypingUsers((prev) =>
      prev.filter(
        (u) =>
          u.username !== identifier &&
          u.user_id !== identifier &&
          String(u.user_id) !== String(identifier),
      ),
    );

    const key = String(identifier);
    const timer = typingTimersRef.current.get(key);
    if (timer) {
      clearTimeout(timer);
      typingTimersRef.current.delete(key);
    }
  }, []);

  const clearAllTypingUsers = useCallback(() => {
    typingTimersRef.current.forEach((timer) => clearTimeout(timer));
    typingTimersRef.current.clear();
    setTypingUsers([]);
  }, []);

  const addTypingUser = useCallback(
    (username: string, userId: number) => {
      if (!username && !userId) return;
      const now = Date.now();

      setTypingUsers((prev) => {
        const exists = prev.some(
          (u) =>
            (username && u.username === username) ||
            (userId && u.user_id === userId),
        );
        if (exists) {
          return prev.map((u) =>
            (username && u.username === username) ||
            (userId && u.user_id === userId)
              ? {
                  username: username || u.username,
                  user_id: userId || u.user_id,
                  lastTypedAt: now,
                }
              : u,
          );
        }
        return [
          ...prev,
          { username: username || `user_${userId}`, user_id: userId, lastTypedAt: now },
        ];
      });

      const key = username || String(userId);
      const existingTimer = typingTimersRef.current.get(key);
      if (existingTimer) clearTimeout(existingTimer);

      const timer = setTimeout(() => {
        removeTypingUser(key);
      }, stopTimeoutMs);
      typingTimersRef.current.set(key, timer);
    },
    [removeTypingUser, stopTimeoutMs],
  );

  // Periodic safety sweep to clear stale typing users if WebSocket events drop
  useEffect(() => {
    const sweepInterval = setInterval(() => {
      const now = Date.now();
      setTypingUsers((prev) => {
        const active = prev.filter(
          (u) => !u.lastTypedAt || now - u.lastTypedAt < stopTimeoutMs,
        );
        return active.length === prev.length ? prev : active;
      });
    }, 2000);

    return () => clearInterval(sweepInterval);
  }, [stopTimeoutMs]);

  const handleTypingMessage = useCallback(
    (data: { action: string; username: string; user_id: number }) => {
      if (data.action === "typing_start") {
        addTypingUser(data.username, data.user_id);
      } else if (data.action === "typing_stop") {
        removeTypingUser(data.username || data.user_id);
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
    removeTypingUser,
    clearAllTypingUsers,
    onInputChange,
    onInputBlur,
    onInputSubmit,
  };
}

