import { useState, useCallback, useRef, useEffect } from "react";
import { useWebSocket } from "./useWebSocket";
import { useTypingIndicator } from "./useTypingIndicator";

type ChatMessage = {
  id: string;
  username: string;
  user_id: number;
  message: string;
  timestamp: string;
};

type UseChatOptions = {
  roomId: string;
  token?: string | null;
  username?: string;
};

function getWsUrl(roomId: string): string {
  const apiBase =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const host = apiBase.replace(/^https?:\/\//, "").replace(/\/api$/, "");
  const scheme = apiBase.startsWith("https") ? "wss" : "ws";
  return `${scheme}://${host}/ws/chat/${roomId}/`;
}

export function useChat({ roomId, token }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const messageIdRef = useRef(0);
  const localUserIdRef = useRef<number | null>(null);

  const onMessage = useCallback((data: unknown) => {
    const msg = data as Record<string, unknown>;
    if (msg.type === "new_message") {
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (
          last &&
          last.id.endsWith("_optimistic") &&
          last.user_id === (msg.user_id as number) &&
          last.message === (msg.message as string)
        ) {
          return prev.map((m) =>
            m.id === last.id
              ? {
                  ...m,
                  id: `msg_${messageIdRef.current + 1}`,
                  username: msg.username as string,
                }
              : m,
          );
        }
        messageIdRef.current += 1;
        return [
          ...prev,
          {
            id: `msg_${messageIdRef.current}`,
            username: msg.username as string,
            user_id: msg.user_id as number,
            message: msg.message as string,
            timestamp: new Date().toLocaleTimeString(),
          },
        ];
      });
    }
  }, []);

  const ws = useWebSocket({
    url: getWsUrl(roomId),
    token,
    onMessage,
  });

  const typing = useTypingIndicator({
    send: ws.send,
  });

  useEffect(() => {
    if (ws.lastMessage) {
      const msg = ws.lastMessage as Record<string, unknown>;
      if (msg.type === "connection_established") {
        localUserIdRef.current = msg.user_id as number;
      } else if (msg.type === "typing") {
        typing.handleTypingMessage(
          msg as unknown as {
            action: string;
            username: string;
            user_id: number;
          },
        );
      }
    }
  }, [ws.lastMessage, typing]);

  const sendMessage = useCallback(
    (text: string) => {
      messageIdRef.current += 1;
      const optimistic: ChatMessage = {
        id: `msg_${messageIdRef.current}_optimistic`,
        username: "",
        user_id: localUserIdRef.current ?? 0,
        message: text,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, optimistic]);
      ws.send({ action: "send_message", message: text });
    },
    [ws],
  );

  return {
    messages,
    typingUsers: typing.typingUsers,
    isConnected: ws.isConnected,
    sendMessage,
    onInputChange: typing.onInputChange,
    onInputBlur: typing.onInputBlur,
    onInputSubmit: typing.onInputSubmit,
  };
}
