import { describe, it, expect, beforeEach, vi } from "vitest";
import { EventBus, eventBus } from "./events";

describe("EventBus", () => {
  beforeEach(() => {
    eventBus.clear();
  });

  it("should subscribe and receive emitted events", () => {
    const mockCallback = vi.fn();
    eventBus.on("test:event", mockCallback);
    
    eventBus.emit("test:event", { data: 123 });
    
    expect(mockCallback).toHaveBeenCalledTimes(1);
    expect(mockCallback).toHaveBeenCalledWith({ data: 123 });
  });

  it("should not trigger callbacks for different events", () => {
    const mockCallback = vi.fn();
    eventBus.on("test:event", mockCallback);
    
    eventBus.emit("other:event", { data: 456 });
    
    expect(mockCallback).not.toHaveBeenCalled();
  });

  it("should handle multiple listeners for the same event", () => {
    const cb1 = vi.fn();
    const cb2 = vi.fn();
    
    eventBus.on("multi:event", cb1);
    eventBus.on("multi:event", cb2);
    
    eventBus.emit("multi:event", "payload");
    
    expect(cb1).toHaveBeenCalledWith("payload");
    expect(cb2).toHaveBeenCalledWith("payload");
  });

  it("should unsubscribe successfully", () => {
    const mockCallback = vi.fn();
    eventBus.on("unsubscribe:event", mockCallback);
    
    // First emit should hit
    eventBus.emit("unsubscribe:event");
    expect(mockCallback).toHaveBeenCalledTimes(1);
    
    // Unsubscribe
    eventBus.off("unsubscribe:event", mockCallback);
    
    // Second emit should not hit
    eventBus.emit("unsubscribe:event");
    expect(mockCallback).toHaveBeenCalledTimes(1);
  });

  it("should trigger wildcard listeners for any event", () => {
    const wildcardCallback = vi.fn();
    eventBus.on("*", wildcardCallback);
    
    eventBus.emit("some:random:event", "hello");
    
    expect(wildcardCallback).toHaveBeenCalledTimes(1);
    expect(wildcardCallback).toHaveBeenCalledWith({ event: "some:random:event", payload: "hello" });
  });

  it("should not break when emitting an event with no listeners", () => {
    expect(() => {
      eventBus.emit("nobody:listening", "test");
    }).not.toThrow();
  });

  it("should continue executing listeners if one throws an error", () => {
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    
    const throwingCb = vi.fn(() => {
      throw new Error("Bad listener");
    });
    const goodCb = vi.fn();
    
    eventBus.on("error:event", throwingCb);
    eventBus.on("error:event", goodCb);
    
    eventBus.emit("error:event", "payload");
    
    expect(throwingCb).toHaveBeenCalled();
    expect(goodCb).toHaveBeenCalled();
    expect(consoleErrorSpy).toHaveBeenCalled();
    
    consoleErrorSpy.mockRestore();
  });
});
