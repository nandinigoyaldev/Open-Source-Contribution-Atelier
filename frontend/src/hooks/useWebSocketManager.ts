import { useEffect, useState, useCallback, useRef } from "react";
import { WebSocketManager, ManagedWebSocket } from "../lib/ws";

type UseWebSocketManagerOptions = {
  url: string;
  token?: string | null;
  onMessage?: (data: unknown) => void;
};

export function useWebSocketManager({
  url,
  token,
  onMessage,
}: UseWebSocketManagerOptions) {
  const [isConnected, setIsConnected] = useState(false);
  const [state, setState] = useState<
    "CONNECTING" | "OPEN" | "CLOSING" | "CLOSED" | "RECONNECTING"
  >("CLOSED");
  const [lastMessage, setLastMessage] = useState<unknown | null>(null);
  const [error, setError] = useState<any | null>(null);

  const manager = WebSocketManager.getInstance();
  const connRef = useRef<ManagedWebSocket | null>(null);
  const onMessageRef = useRef(onMessage);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    const conn = manager.getOrCreateConnection(url, token);
    connRef.current = conn;

    setIsConnected(conn.state === "OPEN");
    setState(conn.state);

    const handleOpen = () => {
      setIsConnected(true);
      setError(null);
    };

    const handleMessage = (data: any) => {
      setLastMessage(data);
      if (onMessageRef.current) {
        onMessageRef.current(data);
      }
    };

    const handleClose = () => {
      setIsConnected(false);
    };

    const handleError = (err: any) => {
      setError(err);
    };

    const handleStateChange = (newState: typeof conn.state) => {
      setState(newState);
      setIsConnected(newState === "OPEN");
    };

    conn.on("open", handleOpen);
    conn.on("message", handleMessage);
    conn.on("close", handleClose);
    conn.on("error", handleError);
    conn.on("stateChange", handleStateChange);

    conn.connect();

    return () => {
      conn.off("open", handleOpen);
      conn.off("message", handleMessage);
      conn.off("close", handleClose);
      conn.off("error", handleError);
      conn.off("stateChange", handleStateChange);
    };
  }, [url, token]);

  const send = useCallback((data: any) => {
    if (connRef.current) {
      connRef.current.send(data);
    }
  }, []);

  const connect = useCallback(() => {
    if (connRef.current) {
      connRef.current.connect();
    }
  }, []);

  const disconnect = useCallback(() => {
    if (connRef.current) {
      connRef.current.disconnect();
    }
  }, []);

  const getMetrics = useCallback(() => {
    if (connRef.current) {
      return connRef.current.getMetrics();
    }
    return null;
  }, []);

  return {
    isConnected,
    state,
    lastMessage,
    error,
    send,
    connect,
    disconnect,
    getMetrics,
  };
}
