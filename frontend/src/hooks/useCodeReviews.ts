import { useState, useEffect, useCallback } from "react";
import { fetchCodeReviewThreads, CodeReviewThread } from "../lib/api";

export function useCodeReviews(roomId: string) {
  const [threads, setThreads] = useState<CodeReviewThread[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [ws, setWs] = useState<WebSocket | null>(null);

  // Initial fetch
  useEffect(() => {
    async function loadThreads() {
      try {
        const data = await fetchCodeReviewThreads(roomId);
        setThreads(data);
      } catch (err) {
        console.error("Failed to fetch review threads:", err);
      } finally {
        setIsLoading(false);
      }
    }
    loadThreads();
  }, [roomId]);

  // WebSocket listener
  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const backendHost = import.meta.env.VITE_API_URL
      ? new URL(import.meta.env.VITE_API_URL).host
      : "localhost:8000";
    const wsUrl = `${protocol}//${backendHost}/ws/collab/${roomId}/`;
    
    const socket = new WebSocket(wsUrl);
    setWs(socket);

    const handleMessage = (event: MessageEvent) => {
      if (typeof event.data === "string") {
        try {
          const payload = JSON.parse(event.data);
          if (payload.action === "thread_updated" && payload.thread) {
            setThreads((prev) => {
              const existingIndex = prev.findIndex((t) => t.id === payload.thread.id);
              if (existingIndex >= 0) {
                const next = [...prev];
                next[existingIndex] = payload.thread;
                return next;
              } else {
                return [...prev, payload.thread];
              }
            });
          }
        } catch (e) {
          // Ignore parse errors or non-review messages
        }
      }
    };

    socket.addEventListener("message", handleMessage);
    return () => {
      socket.removeEventListener("message", handleMessage);
      socket.close();
    };
  }, [roomId]);

  const addComment = useCallback(
    (lineNumber: number, content: string, threadId?: string) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            action: "add_comment",
            line_number: lineNumber,
            content,
            thread_id: threadId,
          })
        );
      }
    },
    [ws]
  );

  const resolveThread = useCallback(
    (threadId: string) => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            action: "resolve_thread",
            thread_id: threadId,
          })
        );
      }
    },
    [ws]
  );

  return {
    threads,
    isLoading,
    addComment,
    resolveThread,
  };
}
