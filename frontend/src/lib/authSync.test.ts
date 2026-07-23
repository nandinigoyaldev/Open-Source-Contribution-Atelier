import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AuthSyncEventType } from "./authSync";

describe("authSync", () => {
  beforeEach(() => {
    vi.resetModules();
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  describe("storage event fallback (no BroadcastChannel)", () => {
    beforeEach(() => {
      vi.stubGlobal("BroadcastChannel", undefined);
    });

    it("broadcasts and receives via storage event", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("LOGIN");

      expect(handler).not.toHaveBeenCalled();

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGIN" }),
        }),
      );

      expect(handler).toHaveBeenCalledWith("LOGIN");
      unsub();
    });

    it("broadcasts LOGOUT event type", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("LOGOUT");

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGOUT" }),
        }),
      );

      expect(handler).toHaveBeenCalledWith("LOGOUT");
      unsub();
    });

    it("broadcasts TOKEN_REFRESHED event type", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("TOKEN_REFRESHED");

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "TOKEN_REFRESHED" }),
        }),
      );

      expect(handler).toHaveBeenCalledWith("TOKEN_REFRESHED");
      unsub();
    });

    it("ignores storage events with wrong key", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "wrong-key",
          newValue: JSON.stringify({ type: "LOGIN" }),
        }),
      );

      expect(handler).not.toHaveBeenCalled();
      unsub();
    });

    it("ignores storage events with null newValue", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: null,
        }),
      );

      expect(handler).not.toHaveBeenCalled();
      unsub();
    });

    it("ignores malformed JSON in storage event", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: "not-json",
        }),
      );

      expect(handler).not.toHaveBeenCalled();
      unsub();
    });

    it("ignores storage events with missing type field", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ foo: "bar" }),
        }),
      );

      expect(handler).not.toHaveBeenCalled();
      unsub();
    });

    it("does not broadcast sensitive data", async () => {
      const { broadcastAuthEvent } = await import("./authSync");
      broadcastAuthEvent("LOGIN");

      const stored = localStorage.getItem("atelier:auth-sync");
      expect(stored).toBeNull();
    });

    it("unsubscribe removes listeners", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      unsub();

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGIN" }),
        }),
      );

      expect(handler).not.toHaveBeenCalled();
    });

    it("handles multiple listeners independently", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler1 = vi.fn();
      const handler2 = vi.fn();
      const unsub1 = onAuthSyncEvent(handler1);
      const unsub2 = onAuthSyncEvent(handler2);

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGOUT" }),
        }),
      );

      expect(handler1).toHaveBeenCalledWith("LOGOUT");
      expect(handler2).toHaveBeenCalledWith("LOGOUT");

      unsub1();
      unsub2();
    });
  });

  describe("BroadcastChannel path", () => {
    let mockInstances: MockBroadcastChannel[];

    class MockBroadcastChannel {
      name: string;
      onmessage: ((e: MessageEvent) => void) | null = null;
      constructor(name: string) {
        this.name = name;
        mockInstances.push(this);
      }
      postMessage(data: unknown) {
        for (const instance of mockInstances) {
          if (instance !== this && instance.name === this.name) {
            instance.onmessage?.({ data } as MessageEvent);
          }
        }
      }
      addEventListener(
        _event: string,
        handler: (e: MessageEvent) => void,
      ) {
        this.onmessage = handler;
      }
      removeEventListener() {
        this.onmessage = null;
      }
      close() {
        this.onmessage = null;
      }
    }

    beforeEach(() => {
      mockInstances = [];
      vi.stubGlobal("BroadcastChannel", MockBroadcastChannel);
    });

    it("broadcasts and receives via BroadcastChannel", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("LOGIN");

      expect(handler).toHaveBeenCalledWith("LOGIN");
      unsub();
    });

    it("does not fire storage events when BroadcastChannel is available", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("LOGIN");

      // BroadcastChannel delivers immediately, so handler was called once.
      expect(handler).toHaveBeenCalledTimes(1);

      // A simulated storage event should not trigger it again.
      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGIN" }),
        }),
      );

      expect(handler).toHaveBeenCalledTimes(1);
      unsub();
    });

    it("handles BroadcastChannel postMessage failure gracefully", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      const originalPostMessage =
        mockInstances[0].postMessage.bind(mockInstances[0]);
      mockInstances[0].postMessage = () => {
        throw new Error("channel closed");
      };

      expect(() => broadcastAuthEvent("LOGIN")).not.toThrow();

      mockInstances[0].postMessage = originalPostMessage;
      unsub();
    });

    it("unsubscribe cleans up BroadcastChannel listener", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      unsub();

      broadcastAuthEvent("LOGIN");
      expect(handler).not.toHaveBeenCalled();
    });

    it("receives all event types via BroadcastChannel", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      const types: AuthSyncEventType[] = [
        "LOGIN",
        "LOGOUT",
        "TOKEN_REFRESHED",
      ];
      for (const type of types) {
        broadcastAuthEvent(type);
      }

      expect(handler).toHaveBeenCalledTimes(3);
      expect(handler).toHaveBeenNthCalledWith(1, "LOGIN");
      expect(handler).toHaveBeenNthCalledWith(2, "LOGOUT");
      expect(handler).toHaveBeenNthCalledWith(3, "TOKEN_REFRESHED");
      unsub();
    });
  });

  describe("BroadcastChannel unavailable fallback", () => {
    beforeEach(() => {
      vi.stubGlobal("BroadcastChannel", undefined);
    });

    it("falls back to storage event when BroadcastChannel is undefined", async () => {
      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("LOGIN");

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGIN" }),
        }),
      );

      expect(handler).toHaveBeenCalledWith("LOGIN");
      unsub();
    });

    it("falls back when BroadcastChannel constructor throws", async () => {
      vi.stubGlobal(
        "BroadcastChannel",
        class {
          constructor() {
            throw new Error("not supported");
          }
        },
      );

      const { broadcastAuthEvent, onAuthSyncEvent } = await import(
        "./authSync"
      );
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      broadcastAuthEvent("LOGOUT");

      window.dispatchEvent(
        new StorageEvent("storage", {
          key: "atelier:auth-sync",
          newValue: JSON.stringify({ type: "LOGOUT" }),
        }),
      );

      expect(handler).toHaveBeenCalledWith("LOGOUT");
      unsub();
    });
  });

  describe("concurrent events", () => {
    beforeEach(() => {
      vi.stubGlobal("BroadcastChannel", undefined);
    });

    it("handles rapid consecutive storage events", async () => {
      const { onAuthSyncEvent } = await import("./authSync");
      const handler = vi.fn();
      const unsub = onAuthSyncEvent(handler);

      const types: AuthSyncEventType[] = [
        "LOGIN",
        "LOGOUT",
        "TOKEN_REFRESHED",
      ];
      for (const type of types) {
        window.dispatchEvent(
          new StorageEvent("storage", {
            key: "atelier:auth-sync",
            newValue: JSON.stringify({ type }),
          }),
        );
      }

      expect(handler).toHaveBeenCalledTimes(3);
      expect(handler).toHaveBeenNthCalledWith(1, "LOGIN");
      expect(handler).toHaveBeenNthCalledWith(2, "LOGOUT");
      expect(handler).toHaveBeenNthCalledWith(3, "TOKEN_REFRESHED");
      unsub();
    });
  });
});
