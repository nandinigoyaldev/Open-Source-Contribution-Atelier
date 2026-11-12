import { describe, expect, it } from "vitest";
import { ApiError, createApiError } from "../lib/apiErrors";

describe("Correlation ID across frontend error handling", () => {
  it("preserves correlationId on ApiError instances and computes safe supportRef", () => {
    const error = new ApiError("Failed operation", {
      status: 500,
      correlationId: "c1234567-89ab-cdef-0123-456789abcdef",
    });

    expect(error.correlationId).toBe("c1234567-89ab-cdef-0123-456789abcdef");
    expect(error.supportRef).toBe("c1234567");
  });

  it("extracts correlationId from response body if not explicitly passed", () => {
    const error = createApiError({
      status: 400,
      body: {
        error: true,
        message: "Invalid field",
        correlation_id: "corr-from-backend-body-1234",
      },
    });

    expect(error.correlationId).toBe("corr-from-backend-body-1234");
    expect(error.supportRef).toBe("corr-fro");
  });

  it("appends safe short reference to 5xx error message without stack trace", () => {
    const error = createApiError({
      status: 500,
      correlationId: "trace-987654321",
      body: {
        error: "internal_error",
      },
    });

    expect(error.message).toContain("(Ref: trace-98)");
    expect(error.message).not.toContain("stack");
  });
});
