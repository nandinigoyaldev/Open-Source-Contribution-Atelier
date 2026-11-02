export interface ApiErrorOptions {
  status?: number;
  endpoint?: string;
  requestId?: string;
  retryable?: boolean;
  authExpired?: boolean;
  details?: string | null;
  /** Machine-readable error code returned by the API (e.g. `2fa_required`). */
  code?: string | null;
  /** Validation messages by field, from the API's `errors` object. */
  fieldErrors?: Record<string, string[]>;
  /** Stable machine-readable codes by field (e.g. `email_taken`), from `error_codes`. */
  fieldCodes?: Record<string, string[]>;
}

/** Keeps only `{ field: string[] }` entries; anything else in the body is ignored. */
function readFieldMap(value: unknown): Record<string, string[]> | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return undefined;
  }
  const result: Record<string, string[]> = {};
  for (const [field, entries] of Object.entries(value)) {
    if (!Array.isArray(entries)) continue;
    const texts = entries.filter(
      (entry): entry is string => typeof entry === "string" && entry !== "",
    );
    if (texts.length > 0) result[field] = texts;
  }
  return Object.keys(result).length > 0 ? result : undefined;
}

const DEFAULT_API_ERROR_MESSAGE =
  "We couldn't complete your request. Please try again in a moment.";

export class ApiError extends Error {
  status?: number;
  endpoint?: string;
  requestId?: string;
  retryable: boolean;
  authExpired: boolean;
  details?: string | null;
  code?: string | null;
  fieldErrors?: Record<string, string[]>;
  fieldCodes?: Record<string, string[]>;

  constructor(message: string, options: ApiErrorOptions = {}) {
    super(message);
    this.name = "ApiError";
    this.status = options.status;
    this.endpoint = options.endpoint;
    this.requestId = options.requestId;
    this.retryable = options.retryable ?? false;
    this.authExpired = options.authExpired ?? false;
    this.details = options.details ?? null;
    this.code = options.code ?? null;
    this.fieldErrors = options.fieldErrors;
    this.fieldCodes = options.fieldCodes;
  }
}

function isAuthEndpoint(endpoint?: string): boolean {
  return Boolean(endpoint && endpoint.includes("/auth/"));
}

function summarizeStatusMessage(
  status: number | undefined,
  endpoint?: string,
): string {
  switch (status) {
    case 400:
      return "Invalid request. Please check the submitted information and try again.";
    case 401:
      return isAuthEndpoint(endpoint)
        ? "Sign-in failed. Please check your credentials and try again."
        : "Your session has expired. Please sign in again.";
    case 403:
      return "You do not have permission to access this resource.";
    case 404:
      return "We couldn't find the requested resource.";
    case 408:
      return "The request timed out. Please try again.";
    case 409:
      return "That action could not be completed because of a conflict.";
    case 413:
      return "The payload is too large for this request.";
    case 422:
      return "Please review the submitted information and try again.";
    case 429:
      return "You're making requests too quickly. Please wait a moment and try again.";
    case 500:
    case 502:
    case 503:
    case 504:
      return "The server is having trouble right now. Please try again in a moment.";
    default:
      return DEFAULT_API_ERROR_MESSAGE;
  }
}

export function createApiError(params: {
  status?: number;
  endpoint?: string;
  requestId?: string;
  body?: unknown;
  retryable?: boolean;
  authExpired?: boolean;
}): ApiError {
  let bodyMessage: string | null = null;
  let detailsStr: string | null = null;
  let code: string | null = null;
  let fieldErrors: Record<string, string[]> | undefined;
  let fieldCodes: Record<string, string[]> | undefined;

  if (params.body && typeof params.body === "object") {
    const b = params.body as Record<string, unknown>;
    fieldErrors = readFieldMap(b.errors);
    fieldCodes = readFieldMap(b.error_codes);
    if (typeof b.code === "string" && b.code.trim()) {
      code = b.code.trim();
    }
    // Prefer the human-facing `message` field: throttling and auth errors use
    // it, while `error` often carries a machine token like "rate_limited".
    if (typeof b.message === "string" && b.message.trim()) {
      bodyMessage = b.message.trim();
    } else if (typeof b.detail === "string" && b.detail.trim()) {
      bodyMessage = b.detail.trim();
    } else if (typeof b.error === "string" && b.error.trim()) {
      bodyMessage = b.error.trim();
    } else if (
      Array.isArray(b.non_field_errors) &&
      b.non_field_errors.length > 0
    ) {
      bodyMessage = String(b.non_field_errors[0]);
    } else {
      const firstKey = Object.keys(b)[0];
      if (firstKey) {
        const val = b[firstKey];
        if (Array.isArray(val) && val.length > 0) {
          bodyMessage = `${firstKey}: ${val[0]}`;
        } else if (typeof val === "string" && val.trim()) {
          bodyMessage = `${firstKey}: ${val.trim()}`;
        }
      }
    }
    try {
      detailsStr = JSON.stringify(params.body);
    } catch {
      detailsStr = String(params.body);
    }
  } else if (typeof params.body === "string" && params.body.trim()) {
    bodyMessage = params.body.trim();
    detailsStr = bodyMessage;
  }

  const message =
    bodyMessage || summarizeStatusMessage(params.status, params.endpoint);

  return new ApiError(message, {
    status: params.status,
    endpoint: params.endpoint,
    requestId: params.requestId,
    retryable: params.retryable,
    authExpired: params.authExpired,
    details: detailsStr,
    code,
    fieldErrors,
    fieldCodes,
  });
}

export function getApiErrorMessage(
  error: unknown,
  fallback = DEFAULT_API_ERROR_MESSAGE,
): string {
  if (error instanceof ApiError) {
    return error.message || fallback;
  }

  if (error instanceof Error) {
    return error.message || fallback;
  }

  if (typeof error === "string" && error.trim()) {
    return error;
  }

  return fallback;
}

export function getApiErrorDetails(error: unknown): string | null {
  if (error instanceof ApiError) {
    const details: string[] = [];

    if (error.status) {
      details.push(`Status: ${error.status}`);
    }
    if (error.endpoint) {
      details.push(`Endpoint: ${error.endpoint}`);
    }
    if (error.requestId) {
      details.push(`Request ID: ${error.requestId}`);
    }
    if (error.authExpired) {
      details.push("Auth session expired: yes");
    }
    if (error.retryable) {
      details.push("Retryable: yes");
    }

    if (error.details) {
      details.push(error.details);
    }

    return details.length > 0 ? details.join("\n") : null;
  }

  if (error instanceof Error) {
    return error.stack || error.message || null;
  }

  if (typeof error === "string") {
    return error;
  }

  return null;
}

export function isRetryableApiError(error: unknown): boolean {
  return error instanceof ApiError && error.retryable;
}

export function isAuthExpiredApiError(error: unknown): boolean {
  return error instanceof ApiError && error.authExpired;
}
