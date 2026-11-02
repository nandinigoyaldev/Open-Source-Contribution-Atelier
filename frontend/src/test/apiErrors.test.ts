import { describe, expect, it } from "vitest";
import { ApiError, createApiError, getApiErrorMessage } from "../lib/apiErrors";

describe("apiErrors", () => {
  it("maps common statuses to user-friendly messages", () => {
    expect(createApiError({ status: 401 }).message).toContain(
      "session has expired",
    );
    expect(createApiError({ status: 403 }).message).toContain("permission");
    expect(createApiError({ status: 404 }).message).toContain("couldn't find");
    expect(createApiError({ status: 500 }).message).toContain("server");
  });

  it("preserves ApiError messages for display helpers", () => {
    const error = new ApiError("Custom message", {
      status: 503,
      retryable: true,
    });
    expect(getApiErrorMessage(error)).toBe("Custom message");
  });

  it("extracts error details from response body", () => {
    const errWithDetail = createApiError({
      status: 400,
      body: { detail: "Failed to verify Google token" },
    });
    expect(errWithDetail.message).toBe("Failed to verify Google token");
    expect(errWithDetail.details).toBe(
      '{"detail":"Failed to verify Google token"}',
    );

    const errWithError = createApiError({
      status: 400,
      body: { error: "Invalid token" },
    });
    expect(errWithError.message).toBe("Invalid token");
  });

  describe("field errors", () => {
    const body = {
      error: true,
      code: "validation_error",
      message: "An account with this email address already exists.",
      errors: {
        email: ["An account with this email address already exists."],
        password: [
          "Password must contain at least one number.",
          "Password must contain at least one special character (!@#$%^&* etc).",
        ],
      },
      error_codes: {
        email: ["email_taken"],
        password: ["password_no_number", "password_no_special"],
      },
    };

    it("keeps the per-field messages and codes from the API", () => {
      const error = createApiError({ status: 400, body });
      expect(error.message).toBe(
        "An account with this email address already exists.",
      );
      expect(error.code).toBe("validation_error");
      expect(error.fieldErrors?.email).toEqual([
        "An account with this email address already exists.",
      ]);
      expect(error.fieldErrors?.password).toHaveLength(2);
      expect(error.fieldCodes?.email).toEqual(["email_taken"]);
      expect(error.fieldCodes?.password).toEqual([
        "password_no_number",
        "password_no_special",
      ]);
    });

    it("leaves them undefined when the body has none", () => {
      const error = createApiError({ status: 400, body: { detail: "No." } });
      expect(error.fieldErrors).toBeUndefined();
      expect(error.fieldCodes).toBeUndefined();
    });

    it("ignores malformed values instead of throwing", () => {
      const error = createApiError({
        status: 400,
        body: {
          message: "Bad.",
          errors: { email: "not a list", name: [1, null, ""], ok: ["fine"] },
          error_codes: ["nope"],
        },
      });
      expect(error.fieldErrors).toEqual({ ok: ["fine"] });
      expect(error.fieldCodes).toBeUndefined();
      expect(
        createApiError({ status: 400, body: { errors: "x" } }).fieldErrors,
      ).toBeUndefined();
      expect(
        createApiError({ status: 400, body: { errors: null } }).fieldErrors,
      ).toBeUndefined();
    });

    it("reports the status message when there is no body at all", () => {
      expect(createApiError({ status: 500 }).fieldErrors).toBeUndefined();
    });
  });
});
