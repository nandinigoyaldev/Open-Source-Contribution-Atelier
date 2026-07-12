/**
 * Manages WebWorker sandbox for secure code execution.
 *
 * @file sandboxManager.js
 * @location frontend/src/utils/sandboxManager.js
 */

class SandboxManager {
  constructor() {
    this.workers = [];
    this.maxWorkers = 4;
    this.workerPool = [];
    this.activeExecutions = new Map();
    this.executionIdCounter = 0;
  }

  /**
   * Initialize the worker pool.
   */
  init() {
    // Clean up any existing workers
    this.cleanup();

    // Create worker pool
    for (let i = 0; i < this.maxWorkers; i++) {
      const worker = this.createWorker();
      this.workerPool.push({
        worker,
        busy: false,
        id: i,
      });
      this.workers.push(worker);
    }

    console.log(`[Sandbox] Initialized with ${this.maxWorkers} workers`);
    return this;
  }

  /**
   * Create a new worker.
   */
  createWorker() {
    // Use Blob URL to create worker from string
    const workerCode = `
      ${this.getWorkerCode()}
    `;

    const blob = new Blob([workerCode], { type: "application/javascript" });
    const workerUrl = URL.createObjectURL(blob);
    const worker = new Worker(workerUrl);

    // Setup event listeners
    worker.onmessage = this.handleWorkerMessage.bind(this);
    worker.onerror = this.handleWorkerError.bind(this);

    return worker;
  }

  /**
   * Get the worker code as a string.
   */
  getWorkerCode() {
    // In production, this would import the worker file
    // For now, we'll use a simple implementation
    return `
      // Worker code loaded from sandbox.worker.js
      // In production, this would be the actual worker code
      self.onmessage = (e) => {
        const { type, code, context, timeout, executionId } = e.data;
        
        if (type === 'execute') {
          try {
            const consoleProxy = {
              log: (...args) => self.postMessage({ type: 'console', method: 'log', args, executionId }),
              error: (...args) => self.postMessage({ type: 'console', method: 'error', args, executionId }),
              warn: (...args) => self.postMessage({ type: 'console', method: 'warn', args, executionId }),
              info: (...args) => self.postMessage({ type: 'console', method: 'info', args, executionId }),
              debug: (...args) => self.postMessage({ type: 'console', method: 'debug', args, executionId }),
            };
            
            const sandboxContext = {
              console: consoleProxy,
              setTimeout: () => self.postMessage({ type: 'warning', message: 'setTimeout not allowed', executionId }),
              setInterval: () => self.postMessage({ type: 'warning', message: 'setInterval not allowed', executionId }),
              fetch: () => self.postMessage({ type: 'warning', message: 'fetch not allowed', executionId }),
              ...context,
            };
            
            const func = new Function(
              ...Object.keys(sandboxContext),
              \`"use strict";\\n\${code}\`
            );
            
            const result = func(...Object.values(sandboxContext));
            
            if (result && typeof result.then === 'function') {
              result
                .then((r) => self.postMessage({ type: 'result', result: r, executionId }))
                .catch((err) => self.postMessage({ type: 'error', error: err.message, stack: err.stack, executionId }));
            } else {
              self.postMessage({ type: 'result', result, executionId });
            }
          } catch (error) {
            self.postMessage({ type: 'error', error: error.message, stack: error.stack, executionId });
          }
        }
      };
    `;
  }

  /**
   * Handle messages from workers.
   */
  handleWorkerMessage(event) {
    const data = event.data;
    const executionId = data.executionId;

    // Find the execution context
    const context = this.activeExecutions.get(executionId);
    if (context && context.onMessage) {
      context.onMessage(data);
    }

    // Handle completion
    if (
      data.type === "result" ||
      data.type === "error" ||
      data.type === "timeout"
    ) {
      this.releaseWorker(executionId);
    }
  }

  /**
   * Handle worker errors.
   */
  handleWorkerError(error) {
    console.error("[Sandbox] Worker error:", error);
    // Try to find which execution this worker was handling
    for (const [executionId, context] of this.activeExecutions) {
      if (context.worker === error.target) {
        if (context.onMessage) {
          context.onMessage({
            type: "error",
            error: error.message || "Worker crashed",
            executionId,
          });
        }
        this.releaseWorker(executionId);
        break;
      }
    }
  }

  /**
   * Execute code in the sandbox.
   *
   * @param {string} code - Code to execute
   * @param {Object} context - Variables to inject
   * @param {number} timeout - Timeout in milliseconds
   * @param {Function} onMessage - Callback for messages
   * @returns {Promise} Execution result
   */
  execute(code, context = {}, timeout = 5000, onMessage = null) {
    return new Promise((resolve, reject) => {
      // Get an available worker
      const workerEntry = this.getAvailableWorker();
      if (!workerEntry) {
        reject(new Error("No workers available. Please try again later."));
        return;
      }

      const { worker, id } = workerEntry;
      const executionId = ++this.executionIdCounter;

      // Store execution context
      this.activeExecutions.set(executionId, {
        worker,
        workerId: id,
        onMessage,
        resolve,
        reject,
        startTime: Date.now(),
      });

      // Mark worker as busy
      workerEntry.busy = true;

      // Send execution message
      worker.postMessage({
        type: "execute",
        executionId,
        code,
        context,
        timeout,
      });

      // Set overall timeout
      const timeoutId = setTimeout(() => {
        if (this.activeExecutions.has(executionId)) {
          this.terminateExecution(executionId);
          reject(new Error(`Execution timed out after ${timeout}ms`));
        }
      }, timeout + 2000);

      // Store timeout ID
      const contextData = this.activeExecutions.get(executionId);
      if (contextData) {
        contextData.timeoutId = timeoutId;
      }
    });
  }

  /**
   * Get an available worker from the pool.
   */
  getAvailableWorker() {
    return this.workerPool.find((entry) => !entry.busy) || null;
  }

  /**
   * Release a worker back to the pool.
   */
  releaseWorker(executionId) {
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
   * Terminate an execution prematurely.
   */
  terminateExecution(executionId) {
    const context = this.activeExecutions.get(executionId);
    if (context) {
      context.worker.terminate();

      const index = this.workerPool.findIndex(
        (entry) => entry.id === context.workerId,
      );
      if (index !== -1) {
        this.workerPool.splice(index, 1);
      }

      this.activeExecutions.delete(executionId);
      this.createWorker();
    }
  }

  /**
   * Clean up all workers.
   */
  cleanup() {
    for (const worker of this.workers) {
      worker.terminate();
    }
    this.workers = [];
    this.workerPool = [];
    this.activeExecutions.clear();
    this.executionIdCounter = 0;
  }

  /**
   * Get sandbox status.
   */
  getStatus() {
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
  reset() {
    this.cleanup();
    this.init();
  }
}

// Export singleton instance
const sandboxManager = new SandboxManager();
export default sandboxManager;
