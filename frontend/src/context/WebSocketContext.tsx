/**
 * WebSocket Context Provider with backoff reconnection.
 *
 * @file WebSocketContext.tsx
 * @location frontend/src/context/WebSocketContext.tsx
 */

import React, { createContext, useContext, ReactNode } from "react";
import {
  useWebSocketWithBackoff,
  WebSocketState,
  WebSocketActions,
} from "../hooks/useWebSocketWithBackoff";

interface WebSocketContextValue extends WebSocketState, WebSocketActions {
  sendMessage: (type: string, payload?: any) => void;
}

const WebSocketContext = createContext<WebSocketContextValue | null>(null);

interface WebSocketProviderProps {
  children: ReactNode;
  url: string;
  onMessage?: (data: any) => void;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({
  children,
  url,
  onMessage,
}) => {
  const ws = useWebSocketWithBackoff({
    url,
    initialBackoff: 1000,
    maxBackoff: 30000,
    maxRetries: 10,
  });

  const sendMessage = (type: string, payload?: any) => {
    ws.send(JSON.stringify({ type, payload }));
  };

  React.useEffect(() => {
    const handleMessage = (event: CustomEvent) => {
      const data = event.detail;
      if (data?.type && onMessage) onMessage(data);
    };

    window.addEventListener("ws-message", handleMessage as EventListener);
    return () =>
      window.removeEventListener("ws-message", handleMessage as EventListener);
  }, [onMessage]);

  const value: WebSocketContextValue = { ...ws, sendMessage };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = (): WebSocketContextValue => {
  const context = useContext(WebSocketContext);
  if (!context)
    throw new Error("useWebSocket must be used within a WebSocketProvider");
  return context;
};
