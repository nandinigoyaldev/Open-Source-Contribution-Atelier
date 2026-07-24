type WSEventMap = {
  open: () => void;
  message: (data: any) => void;
  close: (code: number, reason: string) => void;
  error: (err: any) => void;
  stateChange: (state: ManagedWebSocket["state"]) => void;
};

export class ManagedWebSocket {
  private url: string;
  public token: string | null;
  private ws: WebSocket | null = null;

  // Connection State
  public state: "CONNECTING" | "OPEN" | "CLOSING" | "CLOSED" | "RECONNECTING" =
    "CLOSED";

  // Configuration
  private heartbeatInterval = 30000;
  private heartbeatTimeout = 15000;
  private baseReconnectDelay = 1000;
  private maxReconnectDelay = 30000;

  // Timers
  private heartbeatTimer: any = null;
  private timeoutTimer: any = null;
  private reconnectTimer: any = null;

  // Reconnection info
  private reconnectAttempts = 0;

  // Event listeners
  private listeners: { [K in keyof WSEventMap]?: Array<WSEventMap[K]> } = {};

  // Metrics
  private metrics = {
    connectTime: 0,
    uptime: 0,
    reconnectionCount: 0,
    lastError: null as string | null,
    messagesSent: 0,
    messagesReceived: 0,
  };

  constructor(url: string, token: string | null = null) {
    this.url = url;
    this.token = token;
  }

  public updateToken(newToken: string | null) {
    if (this.token !== newToken) {
      this.token = newToken;
      if (this.state === "OPEN" || this.state === "CONNECTING") {
        this.disconnect();
        this.connect();
      }
    }
  }

  private buildUrl(): string {
    if (!this.token) return this.url;
    const separator = this.url.includes("?") ? "&" : "?";
    return `${this.url}${separator}token=${encodeURIComponent(this.token)}`;
  }

  public connect() {
    if (this.state === "OPEN" || this.state === "CONNECTING") return;

    this.cleanupTimers();
    if (this.state !== "RECONNECTING") {
      this.setState("CONNECTING");
    }

    try {
      const wsUrl = this.buildUrl();
      this.ws = new WebSocket(wsUrl);

      this.ws.onopen = () => {
        this.setState("OPEN");
        this.reconnectAttempts = 0;
        this.metrics.connectTime = Date.now();
        this.emit("open");
        this.startHeartbeat();
      };

      this.ws.onmessage = (event) => {
        this.metrics.messagesReceived++;
        try {
          const data = JSON.parse(event.data);

          // Handle heartbeat pong
          if (data && data.type === "pong") {
            if (this.timeoutTimer) {
              clearTimeout(this.timeoutTimer);
              this.timeoutTimer = null;
            }
            return;
          }

          this.emit("message", data);
        } catch {
          // Send raw message if it's not JSON (for backwards compatibility/raw streams)
          this.emit("message", event.data);
        }
      };

      this.ws.onclose = (event) => {
        this.setState("CLOSED");
        this.emit("close", event.code, event.reason);
        this.handleDisconnect();
      };

      this.ws.onerror = (err) => {
        this.metrics.lastError = "WebSocket error occurred";
        this.emit("error", err);
      };
    } catch (err: any) {
      this.setState("CLOSED");
      this.metrics.lastError = err?.message || "Failed to initialize WebSocket";
      this.handleDisconnect();
    }
  }

  public disconnect() {
    this.cleanupTimers();
    this.reconnectAttempts = 0;
    this.setState("CLOSED");
    if (this.ws) {
      this.ws.onopen = null;
      this.ws.onmessage = null;
      this.ws.onclose = null;
      this.ws.onerror = null;
      this.ws.close();
      this.ws = null;
    }
  }

  public send(data: any) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === "string" ? data : JSON.stringify(data));
      this.metrics.messagesSent++;
    } else {
      console.warn("ManagedWebSocket: Cannot send message, socket is not open");
    }
  }

  public on<K extends keyof WSEventMap>(event: K, callback: WSEventMap[K]) {
    if (!this.listeners[event]) {
      this.listeners[event] = [] as any;
    }
    this.listeners[event]!.push(callback as any);
  }

  public off<K extends keyof WSEventMap>(event: K, callback: WSEventMap[K]) {
    const list = this.listeners[event];
    if (!list) return;
    this.listeners[event] = (list as any[]).filter(
      (cb) => cb !== callback,
    ) as any;
  }

  private emit<K extends keyof WSEventMap>(
    event: K,
    ...args: Parameters<WSEventMap[K]>
  ) {
    const list = this.listeners[event];
    if (list) {
      list.forEach((cb: any) => {
        try {
          cb(...args);
        } catch (e) {
          console.error(`Error in WebSocket event listener for ${event}:`, e);
        }
      });
    }
  }

  private setState(newState: typeof this.state) {
    this.state = newState;
    this.emit("stateChange", newState);
  }

  private handleDisconnect() {
    this.cleanupTimers();

    // Schedule reconnect
    this.setState("RECONNECTING");
    this.metrics.reconnectionCount++;

    const delay = this.getNextDelay();
    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++;
      this.connect();
    }, delay);
  }

  private getNextDelay(): number {
    const tempDelay =
      this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
    const delay = Math.min(this.maxReconnectDelay, tempDelay);
    // Exponential backoff with Full Jitter
    return Math.random() * delay;
  }

  private startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.state === "OPEN") {
        this.send({ action: "ping" });

        // Timeout detection
        this.timeoutTimer = setTimeout(() => {
          console.warn(
            "ManagedWebSocket: Heartbeat timeout, closing connection",
          );
          this.metrics.lastError = "Heartbeat timeout";
          if (this.ws) {
            this.ws.close();
          }
        }, this.heartbeatTimeout);
      }
    }, this.heartbeatInterval);
  }

  private cleanupTimers() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
      this.timeoutTimer = null;
    }
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  public getMetrics() {
    const uptime =
      this.state === "OPEN" && this.metrics.connectTime > 0
        ? Math.floor((Date.now() - this.metrics.connectTime) / 1000)
        : 0;

    return {
      ...this.metrics,
      uptime,
      state: this.state,
    };
  }
}

export class WebSocketManager {
  private static instance: WebSocketManager | null = null;
  private connections = new Map<string, ManagedWebSocket>();

  private constructor() {}

  public static getInstance(): WebSocketManager {
    if (!WebSocketManager.instance) {
      WebSocketManager.instance = new WebSocketManager();
    }
    return WebSocketManager.instance;
  }

  public getOrCreateConnection(
    url: string,
    token?: string | null,
  ): ManagedWebSocket {
    let conn = this.connections.get(url);
    if (!conn) {
      conn = new ManagedWebSocket(url, token);
      this.connections.set(url, conn);
    } else if (token !== undefined) {
      conn.updateToken(token);
    }
    return conn;
  }
}
