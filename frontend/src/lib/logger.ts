export const logger = {
  error: (error: Error, errorInfo?: React.ErrorInfo) => {
    // In a real application, this would send the error to Sentry, LogRocket, etc.
    console.error("Centralized Error Log:", error, errorInfo);
  },
  warn: (message: string, data?: unknown) => {
    console.warn("Centralized Warn Log:", message, data);
  },
  info: (message: string, data?: unknown) => {
    console.info("Centralized Info Log:", message, data);
  },
};
