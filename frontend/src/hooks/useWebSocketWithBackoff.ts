/**
 * WebSocket hook with exponential backoff reconnection.
 * 
 * @file useWebSocketWithBackoff.ts
 * @location frontend/src/hooks/useWebSocketWithBackoff.ts
 */

import { useState, useEffect, useRef, useCallback } from 'react';

export interface WebSocketOptions {
  url: string;
  initialBackoff?: number;      // default: 1000ms
  maxBackoff?: number;          // default: 30000ms
  maxRetries?: number;          // default: 10
  backoffMultiplier?: number;   // default: 2
  reconnectOnClose?: boolean;   // default: true
  reconnectOnError?: boolean;   // default: true
  protocols?: string | string[];
}

export interface WebSocketState {
  status: 'connecting' | 'connected' | 'disconnected' | 'reconnecting' | 'failed';
  isConnected: boolean;
  isConnecting: boolean;
  isReconnecting: boolean;
  retryCount: number;
  lastError: string | null;
  lastMessage: any;
  readyState: number;
}

export interface WebSocketActions {
  send: (data: string | ArrayBuffer | Blob) => void;
  reconnect: () => void;
  disconnect: () => void;
  resetBackoff: () => void;
}

export function useWebSocketWithBackoff(
  options: WebSocketOptions
): WebSocketState & WebSocketActions {
  const {
    url,
    initialBackoff = 1000,
    maxBackoff = 30000,
    maxRetries = 10,
    backoffMultiplier = 2,
    reconnectOnClose = true,
    reconnectOnError = true,
    protocols,
  } = options;

  const [status, setStatus] = useState<WebSocketState['status']>('connecting');
  const [retryCount, setRetryCount] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const [readyState, setReadyState] = useState<number>(WebSocket.CONNECTING);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);
  const isManualDisconnectRef = useRef(false);

  const isConnected = status === 'connected';
  const isConnecting = status === 'connecting' || status === 'reconnecting';
  const isReconnecting = status === 'reconnecting';

  const getBackoffDelay = useCallback((attempt: number): number => {
    const delay = initialBackoff * Math.pow(backoffMultiplier, attempt);
    return Math.min(delay, maxBackoff);
  }, [initialBackoff, backoffMultiplier, maxBackoff]);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const resetBackoff = useCallback(() => {
    setRetryCount(0);
    clearReconnectTimer();
  }, [clearReconnectTimer]);

  const scheduleReconnect = useCallback(() => {
    if (!isMountedRef.current || isManualDisconnectRef.current) return;

    const nextRetry = retryCount + 1;
    setRetryCount(nextRetry);

    if (nextRetry > maxRetries) {
      setStatus('failed');
      setLastError(`Max retries (${maxRetries}) exceeded`);
      return;
    }

    const delay = getBackoffDelay(nextRetry - 1);
    setStatus('reconnecting');
    
    clearReconnectTimer();
    reconnectTimerRef.current = window.setTimeout(() => {
      if (isMountedRef.current && !isManualDisconnectRef.current) {
        connectWebSocket();
      }
    }, delay);
  }, [retryCount, maxRetries, getBackoffDelay, clearReconnectTimer]);

  const connectWebSocket = useCallback(() => {
    if (!isMountedRef.current || isManualDisconnectRef.current) return;
    if (!url) {
      setStatus('disconnected');
      return;
    }

    setStatus('connecting');
    setLastError(null);

    try {
      const ws = protocols ? new WebSocket(url, protocols) : new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        if (!isMountedRef.current) return;
        setStatus('connected');
        setReadyState(WebSocket.OPEN);
        setLastError(null);
        resetBackoff();
      };

      ws.onmessage = (event) => {
        if (!isMountedRef.current) return;
        try {
          const data = JSON.parse(event.data);
          setLastMessage(data);
        } catch {
          setLastMessage(event.data);
        }
      };

      ws.onclose = (event) => {
        if (!isMountedRef.current) return;
        setReadyState(WebSocket.CLOSED);
        
        if (event.code === 1000) {
          setStatus('disconnected');
          return;
        }

        if (!isManualDisconnectRef.current && reconnectOnClose) {
          scheduleReconnect();
        } else {
          setStatus('disconnected');
        }
      };

      ws.onerror = (error) => {
        if (!isMountedRef.current) return;
        setReadyState(WebSocket.CLOSED);
        setLastError('WebSocket error occurred');
        
        if (!isManualDisconnectRef.current && reconnectOnError) {
          scheduleReconnect();
        }
      };

    } catch (error) {
      if (!isMountedRef.current) return;
      setReadyState(WebSocket.CLOSED);
      setLastError(error instanceof Error ? error.message : 'Failed to connect');
      
      if (!isManualDisconnectRef.current && reconnectOnError) {
        scheduleReconnect();
      }
    }
  }, [url, protocols, reconnectOnClose, reconnectOnError, resetBackoff, scheduleReconnect]);

  const send = useCallback((data: string | ArrayBuffer | Blob) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
      return true;
    }
    return false;
  }, []);

  const reconnect = useCallback(() => {
    isManualDisconnectRef.current = false;
    resetBackoff();
    clearReconnectTimer();
    if (wsRef.current) {
      wsRef.current.close();
    }
    connectWebSocket();
  }, [connectWebSocket, resetBackoff, clearReconnectTimer]);

  const disconnect = useCallback(() => {
    isManualDisconnectRef.current = true;
    clearReconnectTimer();
    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }
    setStatus('disconnected');
    setRetryCount(0);
  }, [clearReconnectTimer]);

  useEffect(() => {
    isMountedRef.current = true;
    isManualDisconnectRef.current = false;
    connectWebSocket();

    const handleOnline = () => {
      if (status === 'disconnected' || status === 'failed' || status === 'reconnecting') {
        reconnect();
      }
    };
    window.addEventListener('online', handleOnline);

    return () => {
      isMountedRef.current = false;
      clearReconnectTimer();
      window.removeEventListener('online', handleOnline);
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmount');
        wsRef.current = null;
      }
    };
  }, [connectWebSocket, reconnect, clearReconnectTimer]);

  return {
    status,
    isConnected,
    isConnecting,
    isReconnecting,
    retryCount,
    lastError,
    lastMessage,
    readyState,
    send,
    reconnect,
    disconnect,
    resetBackoff,
  };
}

export default useWebSocketWithBackoff;