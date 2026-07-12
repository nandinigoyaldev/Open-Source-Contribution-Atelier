import { useState, useCallback, useRef, useEffect } from "react";
import { useWebSocket } from "./useWebSocket";
import { useTypingIndicator } from "./useTypingIndicator";
import {
  generateKeyPair,
  exportPublicKey,
  importPublicKey,
  deriveSharedKey,
  encryptMessage,
  decryptMessage,
  KeyPair,
} from "../lib/crypto";

type ChatMessage = {
  id: string;
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

  const onMessage = useCallback(async (data: unknown) => {
    try {
      const msg = data as Record<string, unknown>;
      if (msg.type === "new_message") {
        let plaintext = msg.message as string;
        const senderId = msg.user_id as number;
        const myId = localUserIdRef.current;
        let matchedLocalId: string | null = null;

        if (senderId === myId) {
          setMessages((prev) => {
            const optimisticIdx = prev.findIndex((m) => m.id.endsWith("_optimistic"));
            if (optimisticIdx !== -1) {
              return prev.map((m, idx) =>
                idx === optimisticIdx
                  ? {
                      ...m,
                      id: `msg_${messageIdRef.current + 1}`,
                      username: msg.username as string,
                      timestamp: msg.created_at
                        ? new Date(msg.created_at as string).toLocaleTimeString()
                        : new Date().toLocaleTimeString(),
                      created_at: msg.created_at as string | undefined,
                    }
                  : m
              );
            }
            return prev;
          });
          return;
        }

        if (plaintext.startsWith("{")) {
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
                // If it is JSON ciphertext but we don't have keys, show fallback
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
          return [
            ...prev,
            {
              id: `msg_${messageIdRef.current}`,
              username: msg.username as string,
              user_id: msg.user_id as number,
              message: plaintext,
              timestamp: msg.created_at
                ? new Date(msg.created_at as string).toLocaleTimeString()
                : new Date().toLocaleTimeString(),
              created_at: msg.created_at as string | undefined,
            },
          ];
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
        }
      };

      handleMsg().catch((err) =>
        console.error("Error handling websocket message:", err),
      );
    }
  }, [ws.lastMessage, typing, ws]);

  const sendMessage = useCallback(
    async (text: string) => {
      messageIdRef.current += 1;
      const localId = `msg_${messageIdRef.current}_optimistic`;
      const optimistic: ChatMessage = {
        id: localId,
        username: username || "",
        user_id: localUserIdRef.current ?? 0,
        message: text,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, optimistic]);

      ws.send({ action: "send_message", message: text });
    },
    [ws, username],
  );

  return {
    messages,
    typingUsers: typing.typingUsers,
    onlineUsers,
    isConnected: ws.isConnected,
    sendMessage,
    onInputChange: typing.onInputChange,
    onInputBlur: typing.onInputBlur,
    onInputSubmit: typing.onInputSubmit,
  };
}
