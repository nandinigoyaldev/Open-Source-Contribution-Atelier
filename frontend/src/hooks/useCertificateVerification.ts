import { useEffect, useState } from "react";
import { fetchApi } from "../lib/api";
import { ApiError } from "../lib/apiErrors";

export interface VerifiedCertificate {
  verification_hash: string;
  course_name: string;
  issued_at: string;
  learner_name: string;
  is_active: boolean;
}

export type VerificationFailure = "invalid-input" | "not-found" | "unavailable";

type Result = {
  hash?: string;
  data: VerifiedCertificate | null;
  failure: VerificationFailure | null;
};

export function isCertificateHash(value: string): boolean {
  return /^[A-Za-z0-9_-]{1,64}$/.test(value);
}

function readCertificate(value: unknown): VerifiedCertificate {
  if (
    !value ||
    typeof value !== "object" ||
    !("is_valid" in value) ||
    typeof value.is_valid !== "boolean" ||
    !("certificate" in value)
  ) {
    throw new Error("Invalid certificate response");
  }
  const certificate = value.certificate;
  if (
    !certificate ||
    typeof certificate !== "object" ||
    !("verification_hash" in certificate) ||
    typeof certificate.verification_hash !== "string" ||
    !("course_name" in certificate) ||
    typeof certificate.course_name !== "string" ||
    !("issued_at" in certificate) ||
    typeof certificate.issued_at !== "string" ||
    !Number.isFinite(Date.parse(certificate.issued_at)) ||
    !("learner_name" in certificate) ||
    typeof certificate.learner_name !== "string" ||
    ("is_active" in certificate && typeof certificate.is_active !== "boolean")
  ) {
    throw new Error("Invalid certificate data");
  }
  return {
    verification_hash: certificate.verification_hash,
    course_name: certificate.course_name,
    issued_at: certificate.issued_at,
    learner_name: certificate.learner_name,
    is_active:
      value.is_valid &&
      (!("is_active" in certificate) || certificate.is_active === true),
  };
}

export function useCertificateVerification(hash?: string) {
  const cleanHash = hash?.trim();
  const [result, setResult] = useState<Result>({ data: null, failure: null });
  const [attempt, setAttempt] = useState(0);
  const [completedAttempt, setCompletedAttempt] = useState(-1);

  useEffect(() => {
    if (!cleanHash || !isCertificateHash(cleanHash)) return;
    let cancelled = false;
    const controller = new AbortController();
    async function verify() {
      let data: VerifiedCertificate | null = null;
      let failure: VerificationFailure | null = null;
      try {
        const response: unknown = await fetchApi(
          `/progress/verify/${encodeURIComponent(cleanHash!)}/`,
          {
            method: "GET",
            requireAuth: false,
            suppressErrorToast: true,
            maxRetries: 0,
            signal: controller.signal,
          },
        );
        data = readCertificate(response);
        if (data.verification_hash !== cleanHash)
          throw new Error("Certificate hash mismatch");
      } catch (error) {
        data = null;
        failure =
          error instanceof ApiError && error.status === 404
            ? "not-found"
            : "unavailable";
      }
      if (!cancelled) {
        setResult({ hash: cleanHash, data, failure });
        setCompletedAttempt(attempt);
      }
    }
    void verify();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [cleanHash, attempt]);

  const invalid = Boolean(
    hash !== undefined && (!cleanHash || !isCertificateHash(cleanHash)),
  );
  const loading =
    !invalid &&
    Boolean(cleanHash) &&
    (result.hash !== cleanHash || completedAttempt !== attempt);
  const current = !loading && result.hash === cleanHash;
  return {
    loading,
    data: current ? result.data : null,
    failure: invalid
      ? ("invalid-input" as const)
      : current
        ? result.failure
        : null,
    retry: () => setAttempt((value) => value + 1),
  };
}
