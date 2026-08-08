import { useState, useCallback, useRef, useEffect } from "react";
import { useWebSocketManager as useWebSocket } from "./useWebSocketManager";
import { useTypingIndicator } from "./useTypingIndicator";
import { fetchApi } from "../lib/api";
import {
  generateKeyPair,
  exportPublicKey,
  importPublicKey,
  deriveSharedKey,
  decryptMessage,
  KeyPair,
} from "../lib/crypto";

export type ChatMessage = {
  id: string | number;
  parent_id?: number | null;
  username: string;
  user_id: number;
  message: string;
  timestamp: string;
  created_at?: string;
};

export type OnlineUser = {
  user_id: number;
  username: string;
};

type UseChatOptions = {
  roomId: string;
  token?: string | null;
  username?: string;
};

export function parseMessageTime(msg: ChatMessage): number {
  if (msg.created_at) {
    const t = new Date(msg.created_at).getTime();
    if (!isNaN(t)) return t;
  }
  if (msg.timestamp) {
    const t = new Date(msg.timestamp).getTime();
    if (!isNaN(t)) return t;
  }
  if (typeof msg.id === "string" && msg.id.includes("optimistic")) {
    return Infinity;
  }
  return 0;
}

export function sortAndDeduplicateMessages(
  messages: ChatMessage[],
): ChatMessage[] {
  const map = new Map<string | number, ChatMessage>();

  for (const msg of messages) {
    const key = msg.id;
    const existing = map.get(key);
    if (!existing) {
      map.set(key, msg);
    } else {
      map.set(key, {
        ...existing,
        ...msg,
        message: msg.message || existing.message,
        username: msg.username || existing.username,
        user_id: msg.user_id || existing.user_id,
        created_at: msg.created_at || existing.created_at,
        timestamp: msg.created_at
          ? new Date(msg.created_at).toLocaleTimeString()
          : msg.timestamp || existing.timestamp,
      });
    }
  }

  const result = Array.from(map.values());

  result.sort((a, b) => {
    const timeA = parseMessageTime(a);
    const timeB = parseMessageTime(b);

    if (timeA !== timeB) {
      return timeA - timeB;
    }

    const idA = a.id;
    const idB = b.id;

    if (typeof idA === "number" && typeof idB === "number") {
      return idA - idB;
    }

    return String(idA).localeCompare(String(idB), undefined, { numeric: true });
  });

  return result;
}

function getWsUrl(roomId: string): string {
  const apiBase =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const host = apiBase.replace(/^https?:\/\//, "").replace(/\/api$/, "");
  const scheme = apiBase.startsWith("https") ? "wss" : "ws";
  return `${scheme}://${host}/ws/chat/${roomId}/`;
}

export function useChat({ roomId, token, username }: UseChatOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const messageIdRef = useRef(0);
  const localUserIdRef = useRef<number | null>(null);

  const localKeyPairRef = useRef<KeyPair | null>(null);
  const sharedKeysRef = useRef<Record<number, CryptoKey>>({});
  const knownUsersRef = useRef<Set<number>>(new Set());

  // Fetch REST history and merge with live WebSocket messages
  useEffect(() => {
    if (!roomId) return;
    let isMounted = true;
    setMessages([]);

    const fetchHistory = async () => {
      try {
        const data = await fetchApi(
          `/chat/rooms/${encodeURIComponent(roomId)}/messages/`,
        );
        if (!isMounted) return;
        const rawList = Array.isArray(data) ? data : data?.results || [];
        const formatted: ChatMessage[] = rawList.map((m: any) => ({
          id: m.id,
          parent_id: m.parent_id ?? m.parent ?? null,
          username: m.username || "",
          user_id: m.user_id ?? 0,
          message: m.content || m.message || "",
          timestamp: m.created_at
            ? new Date(m.created_at).toLocaleTimeString()
            : new Date().toLocaleTimeString(),
          created_at: m.created_at,
        }));
        setMessages((prev) =>
          sortAndDeduplicateMessages([...prev, ...formatted]),
        );
      } catch {
        // Silently ignore if room does not exist yet via REST
      }
    };

    void fetchHistory();

    return () => {
      isMounted = false;
    };
  }, [roomId, token]);

  const onMessage = useCallback(async (data: unknown) => {
    try {
      const msg = data as Record<string, unknown>;
      if (msg.type === "new_message") {
        let plaintext = msg.message as string;
        const senderId = msg.user_id as number;
        const myId = localUserIdRef.current;

        if (senderId === myId) {
          setMessages((prev) => {
            const optimisticIdx = prev.findIndex((m) =>
              String(m.id).endsWith("_optimistic"),
            );
            let updated: ChatMessage[];
            if (optimisticIdx !== -1) {
              updated = prev.map((m, idx) =>
                idx === optimisticIdx
                  ? {
                      ...m,
                      id: (msg.id as number | string) ?? m.id,
                      parent_id:
                        (msg.parent_id as number | null) ?? m.parent_id,
                      username: (msg.username as string) || m.username,
                      timestamp: msg.created_at
                        ? new Date(
                            msg.created_at as string,
                          ).toLocaleTimeString()
                        : m.timestamp,
                      created_at: (msg.created_at as string) || m.created_at,
                    }
                  : m,
              );
            } else {
              updated = [
                ...prev,
                {
                  id:
                    (msg.id as number | string) ??
                    `msg_${messageIdRef.current}`,
                  parent_id: msg.parent_id as number | null,
                  username: (msg.username as string) || "",
                  user_id: senderId,
                  message: plaintext,
                  timestamp: msg.created_at
                    ? new Date(msg.created_at as string).toLocaleTimeString()
                    : new Date().toLocaleTimeString(),
                  created_at: msg.created_at as string | undefined,
                },
              ];
            }
            return sortAndDeduplicateMessages(updated);
          });
          return;
        }

        if (plaintext && plaintext.startsWith("{")) {
          try {
            const payload = JSON.parse(plaintext);
            if (payload.ciphertexts) {
              if (
                myId &&
                payload.ciphertexts[myId] &&
                sharedKeysRef.current[senderId]
              ) {
                const { ciphertext, iv } = payload.ciphertexts[myId];
                plaintext = await decryptMessage(
                  ciphertext,
                  iv,
                  sharedKeysRef.current[senderId],
                );
              } else {
                plaintext = "[Encrypted message - key not found]";
              }
            }
          } catch {
            // Fallback to plaintext if JSON parse fails
          }
        }

        if (plaintext === "[Encrypted message - key not found]") {
          return;
        }

        setMessages((prev) => {
          messageIdRef.current += 1;
          const incoming: ChatMessage = {
            id: (msg.id as number | string) ?? `msg_${messageIdRef.current}`,
            parent_id: msg.parent_id as number | null,
            username: (msg.username as string) || "",
            user_id: (msg.user_id as number) || 0,
            message: plaintext,
            timestamp: msg.created_at
              ? new Date(msg.created_at as string).toLocaleTimeString()
              : new Date().toLocaleTimeString(),
            created_at: msg.created_at as string | undefined,
          };
          return sortAndDeduplicateMessages([...prev, incoming]);
        });
      }
    } catch (err) {
      console.error("Error processing incoming message", err);
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

      const handleMsg = async () => {
        if (msg.type === "connection_established") {
          localUserIdRef.current = msg.user_id as number;

          if (!localKeyPairRef.current) {
            localKeyPairRef.current = await generateKeyPair();
          }
          const pubKeyBase64 = await exportPublicKey(
            localKeyPairRef.current.publicKey,
          );
          ws.send({ action: "public_key", public_key: pubKeyBase64 });
        } else if (msg.type === "public_key") {
          const senderId = msg.user_id as number;
          const myId = localUserIdRef.current;

          if (myId && senderId !== myId) {
            try {
              const peerPubKey = await importPublicKey(
                msg.public_key as string,
              );
              if (localKeyPairRef.current) {
                const sharedKey = await deriveSharedKey(
                  localKeyPairRef.current.privateKey,
                  peerPubKey,
                );
                sharedKeysRef.current[senderId] = sharedKey;

                if (!knownUsersRef.current.has(senderId)) {
                  knownUsersRef.current.add(senderId);
                  const pubKeyBase64 = await exportPublicKey(
                    localKeyPairRef.current.publicKey,
                  );
                  ws.send({ action: "public_key", public_key: pubKeyBase64 });
                }
              }
            } catch (error) {
              console.error("Failed to process public key", error);
            }
          }
        } else if (msg.type === "typing") {
          typing.handleTypingMessage(
            msg as unknown as {
              action: string;
              username: string;
              user_id: number;
            },
          );
        } else if (msg.type === "presence_sync") {
          setOnlineUsers((msg.users as OnlineUser[]) || []);
        } else if (msg.type === "presence_joined") {
          const user = {
            user_id: msg.user_id as number,
            username: msg.username as string,
          };
          setOnlineUsers((prev) => {
            if (prev.some((u) => u.user_id === user.user_id)) return prev;
            return [...prev, user];
          });
        } else if (msg.type === "presence_left") {
          setOnlineUsers((prev) =>
            prev.filter((u) => u.user_id !== msg.user_id),
          );
          if (msg.username) typing.removeTypingUser(msg.username as string);
          if (msg.user_id) typing.removeTypingUser(msg.user_id as number);
        }
      };

      handleMsg().catch((err) =>
        console.error("Error handling websocket message:", err),
      );
    }
  }, [ws.lastMessage, typing, ws]);

  // Clear typing indicators when disconnected or when switching room
  useEffect(() => {
    if (!ws.isConnected) {
      typing.clearAllTypingUsers();
    }
  }, [ws.isConnected, typing]);


  const sendMessage = useCallback(
    async (text: string, parentId?: number) => {
      messageIdRef.current += 1;
      const localId = `msg_${messageIdRef.current}_optimistic`;
      const optimistic: ChatMessage = {
        id: localId,
        parent_id: parentId,
        username: username || "",
        user_id: localUserIdRef.current ?? 0,
        message: text,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => sortAndDeduplicateMessages([...prev, optimistic]));

      ws.send({ action: "send_message", message: text, parent_id: parentId });
    },
    [ws, username],
  );

  return {
    messages,
    typingUsers: typing.typingUsers,
    onlineUsers,
    isConnected: ws.isConnected,
    state: ws.state,
    getMetrics: ws.getMetrics,
    sendMessage,
    onInputChange: typing.onInputChange,
    onInputBlur: typing.onInputBlur,
    onInputSubmit: typing.onInputSubmit,
  };
}
