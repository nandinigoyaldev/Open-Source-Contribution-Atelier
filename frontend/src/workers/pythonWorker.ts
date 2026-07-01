import { loadPyodide, PyodideInterface } from "pyodide";

let pyodideReadyPromise: Promise<PyodideInterface> | null = null;

async function initPyodide() {
  if (pyodideReadyPromise) return pyodideReadyPromise;

  pyodideReadyPromise = loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/",
  });

  const pyodide = await pyodideReadyPromise;

  // We can pre-load standard packages here if needed.
  // await pyodide.loadPackage("numpy");

  return pyodide;
}

// Ensure it starts loading immediately
initPyodide();

self.onmessage = async (event) => {
  const { id, pythonCode } = event.data;

  try {
    const pyodide = await initPyodide();

    // Redirect stdout and stderr
    let output = "";
    let errorOutput = "";

    pyodide.setStdout({
      batched: (msg) => {
        output += msg + "\n";
      },
    });
    pyodide.setStderr({
      batched: (msg) => {
        errorOutput += msg + "\n";
      },
    });

    // Execute the code
    await pyodide.runPythonAsync(pythonCode);

    self.postMessage({
      id,
      results: output,
      error: errorOutput ? errorOutput : null,
    });
  } catch (error: unknown) {
    self.postMessage({ id, error: (error as Error).message });
  }
};
