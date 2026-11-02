import {
  DEFAULT_PRIORITY,
  type BlockContext,
  type BlockResult,
  type LessonBlockHandler,
} from "./types";

/** Thrown inside the renderer when a handler returns something it should not. */
export class BlockHandlerError extends Error {
  constructor(
    public readonly handlerId: string,
    message: string,
    public readonly cause?: unknown,
  ) {
    super(
      `Lesson block handler "${handlerId}" ${message}` +
        (cause instanceof Error ? `: ${cause.message}` : ""),
    );
    this.name = "BlockHandlerError";
  }
}

export interface ResolvedBlock {
  handlerId: string;
  result: BlockResult;
}

export class LessonBlockRegistry {
  private handlers = new Map<
    string,
    { handler: LessonBlockHandler; seq: number }
  >();
  private seq = 0;
  private ordered: LessonBlockHandler[] | null = null;

  /** Adds a handler (or replaces the one with the same id). Returns a function that removes it. */
  register(handler: LessonBlockHandler): () => void {
    if (!handler || !handler.id || typeof handler.render !== "function") {
      throw new TypeError(
        "A lesson block handler needs an id and a render function",
      );
    }
    const existing = this.handlers.get(handler.id);
    // a replacement keeps its place among handlers of the same priority
    this.handlers.set(handler.id, {
      handler,
      seq: existing ? existing.seq : this.seq++,
    });
    this.ordered = null;
    return () => {
      if (this.handlers.get(handler.id)?.handler === handler)
        this.unregister(handler.id);
    };
  }

  unregister(id: string): boolean {
    const removed = this.handlers.delete(id);
    if (removed) this.ordered = null;
    return removed;
  }

  has(id: string): boolean {
    return this.handlers.has(id);
  }

  get(id: string): LessonBlockHandler | undefined {
    return this.handlers.get(id)?.handler;
  }

  /** Handlers in the order they are tried. */
  list(): LessonBlockHandler[] {
    if (!this.ordered) {
      this.ordered = Array.from(this.handlers.values())
        .sort(
          (a, b) =>
            (a.handler.priority ?? DEFAULT_PRIORITY) -
              (b.handler.priority ?? DEFAULT_PRIORITY) || a.seq - b.seq,
        )
        .map((entry) => entry.handler);
    }
    return this.ordered;
  }

  /**
   * Asks the handlers in order and returns the first answer. A handler that throws, or that does
   * not move forward, raises a {@link BlockHandlerError}, so the caller can show the error and
   * carry on instead of looping forever or losing the page.
   */
  resolve(ctx: BlockContext): ResolvedBlock | null {
    for (const handler of this.list()) {
      let result: BlockResult | null;
      try {
        result = handler.render(ctx);
      } catch (err) {
        throw new BlockHandlerError(handler.id, "threw while rendering", err);
      }
      if (result == null) continue;
      if (!Number.isInteger(result.next) || result.next <= ctx.index) {
        throw new BlockHandlerError(
          handler.id,
          `returned next=${String(result.next)} for a block starting at line ${ctx.index}; it must move forward`,
        );
      }
      return { handlerId: handler.id, result };
    }
    return null;
  }
}

export function createLessonBlockRegistry(
  handlers: LessonBlockHandler[] = [],
): LessonBlockRegistry {
  const registry = new LessonBlockRegistry();
  handlers.forEach((handler) => registry.register(handler));
  return registry;
}
