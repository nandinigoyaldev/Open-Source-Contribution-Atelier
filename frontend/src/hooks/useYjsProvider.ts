import { useEffect, useRef, useState } from "react";
import * as Y from "yjs";
import { WebsocketProvider } from "y-websocket";
import { getAccessToken } from "../lib/authToken";

export interface CollabUser {
  clientId: number;
  name: string;
  color: string;
  activeFileId: string | null;
}

function getWsUrl(sessionId: string): string {
  const apiBase =
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";
  const host = apiBase.replace(/^https?:\/\//, "").replace(/\/api$/, "");
  const scheme = apiBase.startsWith("https") ? "wss" : "ws";
  return `${scheme}://${host}/ws/collab/${sessionId}/`;
}

function randomColor(): string {
  const colors = [
    "#f87171",
    "#fb923c",
    "#fbbf24",
    "#34d399",
    "#60a5fa",
    "#a78bfa",
    "#f472b6",
  ];
  return colors[Math.floor(Math.random() * colors.length)];
}

interface UseYjsProviderOptions {
  sessionId: string;
  username: string;
  onTextMessage?: (data: any) => void;
}

export function useYjsProvider({
  sessionId,
  username,
  onTextMessage,
}: UseYjsProviderOptions) {
  const ydocRef = useRef<Y.Doc | null>(null);
  const providerRef = useRef<WebsocketProvider | null>(null);
  const [connected, setConnected] = useState(false);
  const [collaborators, setCollaborators] = useState<CollabUser[]>([]);
  const colorRef = useRef(randomColor());
  const onTextMessageRef = useRef(onTextMessage);

  useEffect(() => {
    onTextMessageRef.current = onTextMessage;
  }, [onTextMessage]);

  useEffect(() => {
    const token = getAccessToken();
    const url = getWsUrl(sessionId) + (token ? `?token=${token}` : "");

    const ydoc = new Y.Doc();
    ydocRef.current = ydoc;

    const provider = new WebsocketProvider(url, sessionId, ydoc, {
      connect: true,
    });
    providerRef.current = provider;

    provider.awareness.setLocalStateField("user", {
      name: username,
      color: colorRef.current,
      activeFileId: null,
    });

    const syncCollaborators = () => {
      const states = Array.from(provider.awareness.getStates().entries());
      const users: CollabUser[] = states
        .filter(([id]) => id !== provider.awareness.clientID)
        .map(([clientId, state]) => ({
          clientId,
          name: (state?.user as { name?: string })?.name ?? "Anonymous",
          color: (state?.user as { color?: string })?.color ?? "#888",
          activeFileId:
            (state?.user as { activeFileId?: string | null })?.activeFileId ??
            null,
        }));
      setCollaborators(users);
    };

    provider.awareness.on("change", syncCollaborators);

    const handleStatus = ({ status }: { status: string }) => {
      const isConnected = status === "connected";
      setConnected(isConnected);
      if (isConnected && provider.ws) {
        provider.ws.addEventListener("message", (event) => {
          if (typeof event.data === "string") {
            try {
              const data = JSON.parse(event.data);
              onTextMessageRef.current?.(data);
            } catch (err) {
              // Ignore non-JSON or other messages
            }
          }
        });
      }
    };

    provider.on("status", handleStatus);

    return () => {
      provider.awareness.off("change", syncCollaborators);
      provider.off("status", handleStatus);
      provider.destroy();
      ydoc.destroy();
      ydocRef.current = null;
      providerRef.current = null;
    };
  }, [sessionId, username]);

  const setActiveFile = (fileId: string | null) => {
    providerRef.current?.awareness.setLocalStateField("user", {
      name: username,
      color: colorRef.current,
      activeFileId: fileId,
    });
  };

  const sendTextMessage = (msg: any) => {
    if (
      providerRef.current?.ws &&
      providerRef.current.ws.readyState === WebSocket.OPEN
    ) {
      providerRef.current.ws.send(JSON.stringify(msg));
    }
  };

  return {
    ydoc: ydocRef,
    provider: providerRef,
    connected,
    collaborators,
    setActiveFile,
    sendTextMessage,
  };
}
