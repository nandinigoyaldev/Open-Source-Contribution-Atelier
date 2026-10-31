import type { VerificationFailure } from "../../hooks/useCertificateVerification";

export function VerificationError({
  kind,
  onRetry,
}: {
  kind: VerificationFailure;
  onRetry: () => void;
}) {
  const title =
    kind === "invalid-input"
      ? "Invalid Certificate Link"
      : kind === "not-found"
        ? "Certificate Not Found"
        : "Verification Temporarily Unavailable";
  const message =
    kind === "invalid-input"
      ? "Enter the certificate hash from the original link. It must contain 1–64 letters, numbers, hyphens or underscores."
      : kind === "not-found"
        ? "No certificate matches this hash. Check the copied link or ask the issuer for the correct verification link."
        : "We couldn't contact the verification service or read its response. This does not mean the certificate is invalid. Please try again.";
  return (
    <div role="alert" className="space-y-4 text-center">
      <h1 className="text-2xl font-black">{title}</h1>
      <p>{message}</p>
      {kind === "unavailable" && (
        <button
          type="button"
          onClick={onRetry}
          className="px-4 py-2 rounded-lg border-2 border-current font-bold focus-visible:outline-2 focus-visible:outline-offset-4"
        >
          Retry verification
        </button>
      )}
    </div>
  );
}
