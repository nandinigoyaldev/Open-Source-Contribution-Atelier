import { transform } from "sucrase";

self.addEventListener("message", async (event) => {
  const { id, code } = event.data;

  let output = "";
  let error = null;

  // Create interceptors for console
  const intercept = (level: string) => {
    return (...args: any[]) => {
      const msg = args
        .map((a) => {
          if (a instanceof Error) {
            return a.toString();
          }
          return typeof a === "object" ? JSON.stringify(a, null, 2) : String(a);
        })
        .join(" ");
      output += `${msg}\n`;
    };
  };

  const customConsole = {
    log: intercept("log"),
    info: intercept("info"),
    warn: intercept("warn"),
    error: intercept("error"),
    debug: intercept("debug"),
    clear: () => {
      output = "";
    },
  };

  try {
    // 1. Transpile TS to JS using sucrase
    const compiled = transform(code, { transforms: ["typescript"] }).code;

    // 2. Wrap execution to intercept console and run asynchronously
    const executionFn = new Function(
      "console",
      `
      return (async () => {
        try {
          ${compiled}
        } catch (e) {
          throw e;
        }
      })();
      `
    );

    // 3. Execute
    await executionFn(customConsole);
  } catch (err: any) {
    error = err.toString();
  }

  // Send results back
  self.postMessage({ id, results: output, error });
});
