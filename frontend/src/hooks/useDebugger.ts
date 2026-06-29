import { useState, useEffect, useRef, useCallback } from "react";

export interface DebugState {
  isDebugging: boolean;
  currentLine: number | null;
  variables: Record<string, string>;
  callStack: Array<{ function: string; line: number; file: string }>;
  logs: string[];
}

export function useDebugger() {
  const [state, setState] = useState<DebugState>({
    isDebugging: false,
    currentLine: null,
    variables: {},
    callStack: [],
    logs: [],
  });
  
  const wsRef = useRef<WebSocket | null>(null);

  const startDebug = useCallback((code: string, breakpoints: number[]) => {
    setState({
      isDebugging: true,
      currentLine: null,
      variables: {},
      callStack: [],
      logs: [],
    });
    
    // Connect WebSocket
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws/sandbox/`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        action: "debug_start",
        code,
        breakpoints
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === "debug_state") {
          setState((prev) => ({
            ...prev,
            currentLine: data.line,
            variables: data.locals || {},
            callStack: data.stack || [],
          }));
        } else if (data.type === "debug_end") {
          setState((prev) => ({ ...prev, isDebugging: false, currentLine: null }));
          ws.close();
        } else if (data.type === "debug_error") {
          setState((prev) => ({
            ...prev,
            logs: [...prev.logs, `Error: ${data.error}`],
            isDebugging: false,
            currentLine: null,
          }));
          ws.close();
        } else if (data.type === "execution_output") {
          setState((prev) => ({
            ...prev,
            logs: [...prev.logs, data.output],
          }));
        }
      } catch (err) {
        console.error("Failed to parse debug message", err);
      }
    };

    ws.onclose = () => {
      setState((prev) => ({ ...prev, isDebugging: false, currentLine: null }));
    };
  }, []);

  const sendAction = useCallback((action: string, payload: any = {}) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    }
  }, []);

  const stepInto = useCallback(() => sendAction("debug_step"), [sendAction]);
  const stepOver = useCallback(() => sendAction("debug_next"), [sendAction]);
  const continueExecution = useCallback(() => sendAction("debug_continue"), [sendAction]);
  const stopDebug = useCallback(() => {
    sendAction("debug_stop");
    if (wsRef.current) wsRef.current.close();
  }, [sendAction]);
  const addBreakpoint = useCallback((line: number) => sendAction("debug_breakpoint_add", { line }), [sendAction]);
  const removeBreakpoint = useCallback((line: number) => sendAction("debug_breakpoint_remove", { line }), [sendAction]);

  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return {
    ...state,
    startDebug,
    stepInto,
    stepOver,
    continueExecution,
    stopDebug,
    addBreakpoint,
    removeBreakpoint,
  };
}
