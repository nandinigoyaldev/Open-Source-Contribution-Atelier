/**
 * Manages WebWorker pool for secure code execution.
 *
 * @file sandboxManager.ts
 * @location frontend/src/utils/sandboxManager.ts
 */

// ============================================================
// Types
// ============================================================

interface WorkerEntry {
  worker: Worker;
  busy: boolean;
  id: number;
}

interface ExecutionContext {
  worker: Worker;
  workerId: number;
  resolve: (value: JSExecutionResult) => void;
  reject: (reason: Error) => void;
  timeoutId: number;
}

export interface JSExecutionResult {
  output: string;
  error: string | null;
  executionTime?: number;
}

export interface WorkerStatus {
  totalWorkers: number;
  busyWorkers: number;
  availableWorkers: number;
  activeExecutions: number;
}

// ============================================================
// Sandbox Manager
// ============================================================

export class SandboxManager {
  private static instance: SandboxManager | null = null;
  private workers: Worker[] = [];
  private maxWorkers: number = 4;
  private workerPool: WorkerEntry[] = [];
  private activeExecutions: Map<string, ExecutionContext> = new Map();
  private executionIdCounter: number = 0;
  private isInitialized: boolean = false;

  private constructor() {}

  /**
   * Get singleton instance.
   */
  static getInstance(): SandboxManager {
    if (!SandboxManager.instance) {
      SandboxManager.instance = new SandboxManager();
    }
    return SandboxManager.instance;
  }

  /**
   * Initialize the worker pool.
   */
  init(maxWorkers: number = 4): void {
    if (this.isInitialized) return;

    this.maxWorkers = maxWorkers;
    this.cleanup();

    for (let i = 0; i < this.maxWorkers; i++) {
      const worker = this.createWorker();
      this.workerPool.push({
        worker,
        busy: false,
        id: i,
      });
      this.workers.push(worker);
    }

    this.isInitialized = true;
    console.log(`[Sandbox] Initialized with ${this.maxWorkers} workers`);
  }

  /**
   * Create a new worker.
   */
  private createWorker(): Worker {
    const worker = new Worker(
      new URL("../workers/jsWorker.ts", import.meta.url),
      { type: "module" },
    );

    worker.onmessage = this.handleWorkerMessage.bind(this);
    worker.onerror = this.handleWorkerError.bind(this);

    return worker;
  }

  /**
   * Handle messages from workers.
   */
  private handleWorkerMessage(event: MessageEvent): void {
    const data = event.data;
    const executionId = data.id;

    const context = this.activeExecutions.get(executionId);
    if (!context) return;

    // Handle different response types
    if (data.type === "result") {
      context.resolve({
        output: data.results || "",
        error: null,
        executionTime: data.executionTime,
      });
      this.releaseWorker(executionId);
    } else if (data.type === "error") {
      context.resolve({
        output: "",
        error: data.error || "Execution error",
        executionTime: data.executionTime,
      });
      this.releaseWorker(executionId);
    } else if (data.type === "timeout") {
      context.reject(new Error(data.error || "Execution timed out"));
      this.releaseWorker(executionId);
    }
  }

  /**
   * Handle worker errors.
   */
  private handleWorkerError(error: ErrorEvent): void {
    console.error("[Sandbox] Worker error:", error);

    // Find and cleanup the affected execution
    for (const [executionId, context] of this.activeExecutions) {
      if (context.worker === error.target) {
        if (context.timeoutId) {
          clearTimeout(context.timeoutId);
        }
        context.reject(new Error(error.message || "Worker crashed"));
        this.releaseWorker(executionId);
        break;
      }
    }
  }

  /**
   * Execute code in the sandbox.
   */
  execute(code: string, timeoutMs: number = 5000): Promise<JSExecutionResult> {
    return new Promise((resolve, reject) => {
      // Get an available worker
      const workerEntry = this.workerPool.find((entry) => !entry.busy);
      if (!workerEntry) {
        reject(new Error("No workers available. Please try again later."));
        return;
      }

      const { worker, id } = workerEntry;
      const executionId = `exec_${++this.executionIdCounter}_${Date.now()}`;

      // Mark worker as busy
      workerEntry.busy = true;

      // Set execution timeout
      const timeoutId = window.setTimeout(() => {
        if (this.activeExecutions.has(executionId)) {
          // Terminate worker
          worker.terminate();
          // Create new worker to replace it
          const newWorker = this.createWorker();
          const index = this.workerPool.findIndex((entry) => entry.id === id);
          if (index !== -1) {
            this.workerPool[index].worker = newWorker;
            this.workerPool[index].busy = false;
          }
          this.activeExecutions.delete(executionId);
          reject(new Error(`Execution timed out after ${timeoutMs}ms`));
        }
      }, timeoutMs + 1000);

      // Store execution context
      this.activeExecutions.set(executionId, {
        worker,
        workerId: id,
        resolve,
        reject,
        timeoutId,
      });

      // Send execution message
      worker.postMessage({
        id: executionId,
        code,
        timeout: timeoutMs,
      });
    });
  }

  /**
   * Release a worker back to the pool.
   */
  private releaseWorker(executionId: string): void {
    const context = this.activeExecutions.get(executionId);
    if (context) {
      if (context.timeoutId) {
        clearTimeout(context.timeoutId);
      }

      const workerEntry = this.workerPool.find(
        (entry) => entry.id === context.workerId,
      );
      if (workerEntry) {
        workerEntry.busy = false;
      }

      this.activeExecutions.delete(executionId);
    }
  }

  /**
   * Clean up all workers.
   */
  cleanup(): void {
    for (const worker of this.workers) {
      worker.terminate();
    }
    this.workers = [];
    this.workerPool = [];
    this.activeExecutions.clear();
    this.executionIdCounter = 0;
    this.isInitialized = false;
  }

  /**
   * Get sandbox status.
   */
  getStatus(): WorkerStatus {
    const totalWorkers = this.workerPool.length;
    const busyWorkers = this.workerPool.filter((entry) => entry.busy).length;
    const activeExecutions = this.activeExecutions.size;

    return {
      totalWorkers,
      busyWorkers,
      availableWorkers: totalWorkers - busyWorkers,
      activeExecutions,
    };
  }

  /**
   * Reset the sandbox.
   */
  reset(): void {
    this.cleanup();
    this.init(this.maxWorkers);
  }
}

// Export singleton instance
export const sandboxManager = SandboxManager.getInstance();
