export type EventCallback = (payload?: any) => void;

/**
 * A central EventBus for the frontend to decouple core modules.
 */
export class EventBus {
  private static instance: EventBus;
  private listeners: Record<string, EventCallback[]> = {};

  private constructor() {}

  /**
   * Retrieves the singleton instance of the EventBus.
   */
  public static getInstance(): EventBus {
    if (!EventBus.instance) {
      EventBus.instance = new EventBus();
    }
    return EventBus.instance;
  }

  /**
   * Subscribes to an event.
   * Supports specific events (e.g. 'sync:success') and wildcards (e.g. '*').
   *
   * @param event The event name to listen to.
   * @param callback The function to execute when the event is emitted.
   */
  public on(event: string, callback: EventCallback): void {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  }

  /**
   * Unsubscribes an existing callback from an event.
   *
   * @param event The event name.
   * @param callback The exact function reference that was used in `on()`.
   */
  public off(event: string, callback: EventCallback): void {
    if (!this.listeners[event]) return;
    this.listeners[event] = this.listeners[event].filter(
      (cb) => cb !== callback
    );
  }

  /**
   * Emits an event with an optional payload, synchronously calling all registered listeners.
   * If a wildcard '*' listener is registered, it will receive the event name and payload.
   *
   * @param event The event name to emit.
   * @param payload Optional data associated with the event.
   */
  public emit(event: string, payload?: any): void {
    const callbacks = this.listeners[event] || [];
    // Clone array to prevent issues if a listener unsubscribes during iteration
    [...callbacks].forEach((cb) => {
      try {
        cb(payload);
      } catch (err) {
        console.error(`[EventBus] Error in listener for event '${event}':`, err);
      }
    });

    // Notify wildcard listeners
    const wildcardCallbacks = this.listeners["*"] || [];
    [...wildcardCallbacks].forEach((cb) => {
      try {
        cb({ event, payload });
      } catch (err) {
        console.error(`[EventBus] Error in wildcard listener for event '${event}':`, err);
      }
    });
  }

  /**
   * Clears all registered listeners. Mainly useful for testing.
   */
  public clear(): void {
    this.listeners = {};
  }
}

export const eventBus = EventBus.getInstance();
