/**
 * WebWorker for secure code execution in isolated thread.
 * 
 * @file sandbox.worker.js
 * @location frontend/src/workers/sandbox.worker.js
 */

// ============================================================
// Safe Console Implementation
// ============================================================

const safeConsole = {
  log: (...args) => postMessage({ type: 'console', method: 'log', args }),
  error: (...args) => postMessage({ type: 'console', method: 'error', args }),
  warn: (...args) => postMessage({ type: 'console', method: 'warn', args }),
  info: (...args) => postMessage({ type: 'console', method: 'info', args }),
  debug: (...args) => postMessage({ type: 'console', method: 'debug', args }),
  table: (data) => postMessage({ type: 'console', method: 'table', args: [data] }),
  clear: () => postMessage({ type: 'console', method: 'clear', args: [] }),
  time: (label) => postMessage({ type: 'console', method: 'time', args: [label] }),
  timeEnd: (label) => postMessage({ type: 'console', method: 'timeEnd', args: [label] }),
  group: (label) => postMessage({ type: 'console', method: 'group', args: [label] }),
  groupEnd: () => postMessage({ type: 'console', method: 'groupEnd', args: [] }),
  groupCollapsed: (label) => postMessage({ type: 'console', method: 'groupCollapsed', args: [label] }),
  trace: (...args) => postMessage({ type: 'console', method: 'trace', args }),
};

// ============================================================
// Execution State
// ============================================================

let executionTimeout = null;
let isExecuting = false;

// ============================================================
// Code Execution
// ============================================================

function executeCode(code, context = {}, timeout = 5000, executionId) {
  if (isExecuting) {
    postMessage({ 
      type: 'error', 
      error: 'Another execution is already in progress',
      executionId 
    });
    return;
  }

  isExecuting = true;
  const startTime = performance.now();

  // Clear previous timeout
  if (executionTimeout) {
    clearTimeout(executionTimeout);
    executionTimeout = null;
  }

  // Set execution timeout
  executionTimeout = setTimeout(() => {
    postMessage({ 
      type: 'timeout', 
      message: `⚠️ Execution timed out after ${timeout}ms`,
      executionId 
    });
    isExecuting = false;
    executionTimeout = null;
    // Terminate worker to clean up
    self.close();
  }, timeout);

  try {
    // Build the sandbox context with safe APIs
    const sandboxContext = {
      console: safeConsole,
      // Block unsafe APIs
      setTimeout: () => {
        postMessage({ 
          type: 'warning', 
          message: '⛔ setTimeout is not allowed in sandbox',
          executionId 
        });
        return null;
      },
      setInterval: () => {
        postMessage({ 
          type: 'warning', 
          message: '⛔ setInterval is not allowed in sandbox',
          executionId 
        });
        return null;
      },
      fetch: () => {
        postMessage({ 
          type: 'warning', 
          message: '⛔ fetch is not allowed in sandbox',
          executionId 
        });
        return null;
      },
      alert: () => {
        postMessage({ 
          type: 'warning', 
          message: '⛔ alert is not allowed in sandbox',
          executionId 
        });
        return null;
      },
      prompt: () => {
        postMessage({ 
          type: 'warning', 
          message: '⛔ prompt is not allowed in sandbox',
          executionId 
        });
        return null;
      },
      confirm: () => {
        postMessage({ 
          type: 'warning', 
          message: '⛔ confirm is not allowed in sandbox',
          executionId 
        });
        return null;
      },
      // Safe utilities
      Math: Math,
      Date: Date,
      Array: Array,
      Object: Object,
      String: String,
      Number: Number,
      Boolean: Boolean,
      ...context,
    };

    // Create function from code with sandbox context
    const func = new Function(
      ...Object.keys(sandboxContext),
      `"use strict";\n${code}`
    );

    // Execute with context
    const result = func(...Object.values(sandboxContext));

    // Handle promise result
    if (result && typeof result.then === 'function') {
      result
        .then((asyncResult) => {
          const executionTime = performance.now() - startTime;
          postMessage({ 
            type: 'result', 
            result: asyncResult,
            executionTime,
            executionId 
          });
        })
        .catch((error) => {
          const executionTime = performance.now() - startTime;
          postMessage({ 
            type: 'error', 
            error: error.message || String(error),
            stack: error.stack,
            executionTime,
            executionId 
          });
        })
        .finally(() => {
          isExecuting = false;
          if (executionTimeout) {
            clearTimeout(executionTimeout);
            executionTimeout = null;
          }
        });
    } else {
      const executionTime = performance.now() - startTime;
      postMessage({ 
        type: 'result', 
        result,
        executionTime,
        executionId 
      });
      isExecuting = false;
      if (executionTimeout) {
        clearTimeout(executionTimeout);
        executionTimeout = null;
      }
    }
  } catch (error) {
    const executionTime = performance.now() - startTime;
    postMessage({ 
      type: 'error', 
      error: error.message || String(error),
      stack: error.stack,
      executionTime,
      executionId 
    });
    isExecuting = false;
    if (executionTimeout) {
      clearTimeout(executionTimeout);
      executionTimeout = null;
    }
  }
}

// ============================================================
// Message Handlers
// ============================================================

self.onmessage = (event) => {
  const { type, code, context, timeout, executionId } = event.data;

  switch (type) {
    case 'execute':
      executeCode(code, context, timeout, executionId);
      break;

    case 'terminate':
      if (executionTimeout) {
        clearTimeout(executionTimeout);
        executionTimeout = null;
      }
      isExecuting = false;
      self.close();
      break;

    default:
      postMessage({ 
        type: 'error', 
        error: `Unknown message type: ${type}`,
        executionId 
      });
  }
};

// ============================================================
// Error Handlers
// ============================================================

self.onerror = (error) => {
  postMessage({ 
    type: 'error', 
    error: error.message || 'Worker error occurred',
    stack: error.stack,
  });
  isExecuting = false;
};

self.onunhandledrejection = (event) => {
  postMessage({ 
    type: 'error', 
    error: event.reason?.message || 'Unhandled promise rejection',
    stack: event.reason?.stack,
  });
  isExecuting = false;
};