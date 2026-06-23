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

  const localKeyPairRef = useRef<KeyPair | null>(null);
  const sharedKeysRef = useRef<Record<number, CryptoKey>>({});
  const knownUsersRef = useRef<Set<number>>(new Set());

  const onMessage = useCallback(async (data: unknown) => {
    const msg = data as Record<string, unknown>;
    if (msg.type === "new_message") {
      let plaintext = msg.message as string;
      const senderId = msg.user_id as number;
      const myId = localUserIdRef.current;
      let matchedLocalId: string | null = null;

      if (plaintext.startsWith("{")) {
        try {
          const payload = JSON.parse(plaintext);
          if (payload.ciphertexts) {
            matchedLocalId = payload.local_id;
            if (senderId === myId) {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last && last.id === matchedLocalId) {
                  return prev.map((m) =>
                    m.id === matchedLocalId
                      ? {
                          ...m,
                          id: `msg_${messageIdRef.current + 1}`,
                          username: msg.username as string,
                        }
                      : m,
                  );
                }
                return prev;
              });
              return;
            } else if (
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

      setMessages((prev) => {
        messageIdRef.current += 1;
        return [
          ...prev,
          {
            id: `msg_${messageIdRef.current}`,
            username: msg.username as string,
            user_id: senderId,
            message: plaintext,
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
      
      const handleMsg = async () => {
        if (msg.type === "connection_established") {
          localUserIdRef.current = msg.user_id as number;
          
          if (!localKeyPairRef.current) {
            localKeyPairRef.current = await generateKeyPair();
          }
          const pubKeyBase64 = await exportPublicKey(localKeyPairRef.current.publicKey);
          ws.send({ action: "public_key", public_key: pubKeyBase64 });
          
        } else if (msg.type === "public_key") {
          const senderId = msg.user_id as number;
          const myId = localUserIdRef.current;
          
          if (myId && senderId !== myId) {
            try {
              const peerPubKey = await importPublicKey(msg.public_key as string);
              if (localKeyPairRef.current) {
                const sharedKey = await deriveSharedKey(localKeyPairRef.current.privateKey, peerPubKey);
                sharedKeysRef.current[senderId] = sharedKey;
                
                if (!knownUsersRef.current.has(senderId)) {
                  knownUsersRef.current.add(senderId);
                  const pubKeyBase64 = await exportPublicKey(localKeyPairRef.current.publicKey);
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
        }
      };
      
      handleMsg();
    }
  }, [ws.lastMessage, typing, ws]);

  const sendMessage = useCallback(
    async (text: string) => {
      messageIdRef.current += 1;
      const localId = `msg_${messageIdRef.current}_optimistic`;
      const optimistic: ChatMessage = {
        id: localId,
        username: "",
        user_id: localUserIdRef.current ?? 0,
        message: text,
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, optimistic]);
      
      const ciphertexts: Record<number, { ciphertext: string, iv: string }> = {};
      for (const [userIdStr, key] of Object.entries(sharedKeysRef.current)) {
        const userId = Number(userIdStr);
        ciphertexts[userId] = await encryptMessage(text, key);
      }
      
      const payload = {
        local_id: localId,
        ciphertexts,
      };
      
      ws.send({ action: "send_message", message: JSON.stringify(payload) });
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
