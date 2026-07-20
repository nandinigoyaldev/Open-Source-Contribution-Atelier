import { useEffect, useRef, useState, useCallback } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  enqueueMessage,
  clearQueue,
  setOnlineStatus,
  ChatMessage,
} from "../components/chat/chatSlice";
// Adjust RootState import based on your store setup
// import { RootState } from '../store';

export const useResilientWebSocket = (url: string) => {
  const dispatch = useDispatch();
  // Replace 'any' with RootState if you have it configured
  const offlineQueue = useSelector((state: any) => state.chat.offlineQueue);

  const [ws, setWs] = useState<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectDelay = 30000; // Cap at 30 seconds
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    const socket = new WebSocket(url);
    wsRef.current = socket;

    socket.onopen = () => {
      dispatch(setOnlineStatus(true));
      reconnectAttempts.current = 0; // Reset attempts on success

      // Flush the offline queue to the backend
      if (offlineQueue.length > 0) {
        offlineQueue.forEach((msg: ChatMessage) => {
          socket.send(JSON.stringify(msg));
        });
        dispatch(clearQueue());
      }
    };

    socket.onclose = () => {
      dispatch(setOnlineStatus(false));

      // Exponential backoff formula: min(1000ms * 2^attempts, 30000ms)
      const delay = Math.min(
        1000 * 2 ** reconnectAttempts.current,
        maxReconnectDelay,
      );
      reconnectAttempts.current += 1;

      setTimeout(() => {
        connect();
      }, delay);
    };

    socket.onerror = (error) => {
      console.error("WebSocket Error:", error);
      socket.close(); // Force close to trigger onclose and backoff
    };

    setWs(socket);
  }, [url, dispatch, offlineQueue]);

  useEffect(() => {
    connect();

    const handleOnline = () => dispatch(setOnlineStatus(true));
    const handleOffline = () => dispatch(setOnlineStatus(false));

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  const sendMessage = (msg: ChatMessage) => {
    if (
      wsRef.current &&
      wsRef.current.readyState === WebSocket.OPEN &&
      navigator.onLine
    ) {
      wsRef.current.send(JSON.stringify(msg));
    } else {
      // If offline or connecting, push to Redux queue
      dispatch(enqueueMessage(msg));
    }
  };

  return { sendMessage, isConnected: ws?.readyState === WebSocket.OPEN };
};
