/**
 * WebSocket connection status indicator with toast notifications.
 * 
 * @file WebSocketStatusIndicator.tsx
 * @location frontend/src/components/WebSocketStatus/WebSocketStatusIndicator.tsx
 */

import React, { useEffect, useState } from 'react';
import { toast } from 'react-hot-toast';
import { useWebSocketWithBackoff } from '../../hooks/useWebSocketWithBackoff';

interface WebSocketStatusIndicatorProps {
  url: string;
  onMessage?: (data: any) => void;
  className?: string;
}

export const WebSocketStatusIndicator: React.FC<WebSocketStatusIndicatorProps> = ({
  url,
  onMessage,
  className = '',
}) => {
  const [toastId, setToastId] = useState<string | null>(null);

  const {
    status,
    isConnected,
    isReconnecting,
    retryCount,
    lastError,
    send,
    reconnect,
    disconnect,
  } = useWebSocketWithBackoff({
    url,
    initialBackoff: 1000,
    maxBackoff: 30000,
    maxRetries: 10,
  });

  // Handle status changes with toasts
  useEffect(() => {
    if (!url) return;

    if (toastId) {
      toast.dismiss(toastId);
      setToastId(null);
    }

    let id: string | null = null;

    if (status === 'connected') {
      id = toast.success('✅ Connected to server', { duration: 3000 });
    } else if (status === 'reconnecting') {
      id = toast.loading(`🔄 Reconnecting... (${retryCount}/10)`, { duration: Infinity });
    } else if (status === 'failed') {
      id = toast.error(`❌ Connection failed after ${retryCount} attempts`, { duration: 5000 });
    } else if (status === 'disconnected') {
      id = toast.error('🔌 Connection lost', { duration: 3000 });
    }

    if (id) {
      setToastId(id);
    }
  }, [status, retryCount, url]);

  // Listen for messages
  useEffect(() => {
    const handleMessage = (event: CustomEvent) => {
      if (onMessage) onMessage(event.detail);
    };

    window.addEventListener('ws-message', handleMessage as EventListener);
    return () => window.removeEventListener('ws-message', handleMessage as EventListener);
  }, [onMessage]);

  const getStatusColor = () => {
    switch (status) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500 animate-pulse';
      case 'reconnecting': return 'bg-orange-500 animate-pulse';
      case 'disconnected': return 'bg-red-500';
      case 'failed': return 'bg-red-600';
      default: return 'bg-gray-500';
    }
  };

  const getStatusLabel = () => {
    switch (status) {
      case 'connected': return 'Connected';
      case 'connecting': return 'Connecting...';
      case 'reconnecting': return `Reconnecting (${retryCount}/10)...`;
      case 'disconnected': return 'Disconnected';
      case 'failed': return 'Failed';
      default: return 'Unknown';
    }
  };

  if (!url || status === 'connecting') return null;

  return (
    <div className={`fixed bottom-4 left-4 z-50 ${className}`}>
      <div className="flex items-center gap-3 bg-dark-800/90 backdrop-blur-sm px-4 py-2.5 rounded-xl border border-dark-700 shadow-lg">
        <div className="relative">
          <div className={`w-3 h-3 rounded-full ${getStatusColor()}`} />
          {status === 'reconnecting' && (
            <div className="absolute inset-0 w-3 h-3 rounded-full bg-orange-500 animate-ping opacity-75" />
          )}
        </div>
        <span className="text-sm text-gray-300">{getStatusLabel()}</span>
        {status === 'reconnecting' && (
          <div className="w-16 h-1.5 bg-dark-700 rounded-full overflow-hidden">
            <div className="h-full bg-orange-500 transition-all duration-300 rounded-full" style={{ width: `${(retryCount / 10) * 100}%` }} />
          </div>
        )}
        {status === 'failed' && (
          <button onClick={reconnect} className="text-xs px-2 py-1 bg-blue-600 hover:bg-blue-700 rounded-lg text-white">
            Retry
          </button>
        )}
      </div>
    </div>
  );
};