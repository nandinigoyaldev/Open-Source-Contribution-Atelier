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
  /** True after max reconnect attempts fail — callers should use REST fallback */
  reconnectExhausted: boolean;
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
    reconnectExhausted: false,
    lastMessage: null,
    error: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  /** Ignore close events from intentionally replaced sockets */
  const intentionalCloseRef = useRef(false);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const buildUrl = useCallback(() => {
    if (!token) return url;
    const separator = url.includes("?") ? "&" : "?";
    return `${url}${separator}token=${encodeURIComponent(token)}`;
  }, [url, token]);

  const ws = new WebSocket(
    `wss://${window.location.host}/ws/notifications/`,
    ["token", token], // Subprotocol: token
  );

  const cleanup = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    if (wsRef.current) {
      intentionalCloseRef.current = intentional;
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      if (
        wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING
      ) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }
  }, []);

  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    cleanup(true);

    if (!token) {
      setState((s) => ({
        ...s,
        isConnected: false,
        reconnectExhausted: false,
      }));
      return;
    }

    // Token refresh / new connect cycle resets exhaustion
    setState((s) => ({ ...s, reconnectExhausted: false }));

    const wsUrl = buildUrl();
    const ws = new WebSocket(wsUrl);
    intentionalCloseRef.current = false;

    ws.onopen = () => {
      reconnectCountRef.current = 0;
      setState((s) => ({
        ...s,
        isConnected: true,
        reconnectExhausted: false,
        error: null,
      }));
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, isConnected: false }));
      if (intentionalCloseRef.current) return;

      if (reconnectCountRef.current < maxReconnectAttempts) {
        reconnectCountRef.current += 1;
        reconnectTimerRef.current = setTimeout(
          () => connectRef.current(),
          reconnectInterval,
        );
      } else {
        setState((s) => ({ ...s, reconnectExhausted: true }));
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

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = useCallback(() => {
    cleanup(true);
    setState((s) => ({
      ...s,
      isConnected: false,
      reconnectExhausted: false,
    }));
  }, [cleanup]);

  const send = useCallback((data: unknown): boolean => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    // Reconnect whenever URL or JWT token changes (token refresh)
    reconnectCountRef.current = 0;
    connect();
    return () => cleanup(true);
  }, [connect, cleanup]);

  return {
    ...state,
    send,
    connect,
    disconnect,
  };
}
