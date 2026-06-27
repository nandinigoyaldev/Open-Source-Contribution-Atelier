/* eslint-disable react-hooks/refs */
/* eslint-disable react-hooks/immutability */
/* eslint-disable @typescript-eslint/no-use-before-define */
import { useEffect, useRef, useCallback, useState } from "react";

type UseWebSocketOptions = {
  url: string;
  token?: string | null;
  onMessage?: (data: unknown) => void;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
};

type WebSocketState = {
  isConnected: boolean;
  lastMessage: unknown | null;
  error: Event | null;
};

export function useWebSocket({
  url,
  token,
  onMessage,
  reconnectInterval = 3000,
  maxReconnectAttempts = 10,
}: UseWebSocketOptions) {
  const [state, setState] = useState<WebSocketState>({
    isConnected: false,
    lastMessage: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const buildUrl = useCallback(() => {
    try {
      const parsedUrl = new URL(url, window.location.origin);
      if (parsedUrl.protocol !== "ws:" && parsedUrl.protocol !== "wss:") {
        console.error("useWebSocket: Invalid protocol");
        return null;
      }
      if (token) {
        if (!/^[A-Za-z0-9\-_.]+$/.test(token)) {
          console.error("useWebSocket: Invalid token format");
          return null;
        }
        parsedUrl.searchParams.set("token", token);
      }
      return parsedUrl.toString();
    } catch (e) {
      console.error("useWebSocket: Invalid URL", e);
      return null;
    }
  }, [url, token]);

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    cleanup();

    if (!token) {
      setState((s) => ({ ...s, isConnected: false }));
      return;
    }

    const wsUrl = buildUrl();
    if (!wsUrl) {
      setState((s) => ({ ...s, isConnected: false }));
      return;
    }
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      reconnectCountRef.current = 0;
      setState((s) => ({ ...s, isConnected: true, error: null }));
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, isConnected: false }));
      if (reconnectCountRef.current < maxReconnectAttempts) {
        reconnectCountRef.current += 1;

        reconnectTimerRef.current = setTimeout(connect, reconnectInterval);
      }
    };

    ws.onerror = () => {
      setState((s) => ({ ...s, isConnected: false }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setState((s) => ({ ...s, lastMessage: data }));
        onMessageRef.current?.(data);
      } catch {
        console.error("useWebSocket: failed to parse message", event.data);
      }
    };

    wsRef.current = ws;
  }, [buildUrl, cleanup, reconnectInterval, maxReconnectAttempts, token]);

  const disconnect = useCallback(() => {
    reconnectCountRef.current = maxReconnectAttempts;
    cleanup();
    setState((s) => ({ ...s, isConnected: false }));
  }, [cleanup, maxReconnectAttempts]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return cleanup;
  }, [connect, cleanup]);

  return {
    ...state,
    send,
    connect,
    disconnect,
  };
}
