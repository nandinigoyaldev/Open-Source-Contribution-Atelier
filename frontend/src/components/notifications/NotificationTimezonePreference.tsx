import { useEffect, useRef, useState } from "react";
import { fetchApi } from "../../lib/api";

const timezoneOptions = (() => {
  const intl = Intl as typeof Intl & {
    supportedValuesOf?: (key: "timeZone") => string[];
  };
  return (
    intl.supportedValuesOf?.("timeZone") ?? [
      "Asia/Kolkata",
      "Europe/London",
      "America/New_York",
      "America/Los_Angeles",
    ]
  );
})();

function readTimezone(profile: unknown): string {
  if (
    !profile ||
    typeof profile !== "object" ||
    !("timezone" in profile) ||
    typeof profile.timezone !== "string" ||
    !profile.timezone.trim()
  ) {
    throw new Error("The profile did not return a timezone.");
  }
  return profile.timezone;
}

export function NotificationTimezonePreference() {
  const [timezone, setTimezone] = useState("");
  const [savedTimezone, setSavedTimezone] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);
  const saveInFlight = useRef(false);
  const mounted = useRef(false);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    setLoading(true);
    setError("");
    fetchApi<unknown>("/auth/me/", {
      signal: controller.signal,
      suppressErrorToast: true,
      maxRetries: 0,
    })
      .then((profile) => {
        const value = readTimezone(profile);
        if (controller.signal.aborted) return;
        setTimezone(value);
        setSavedTimezone(value);
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setError("Could not load your saved timezone. Please try again.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, [loadAttempt]);

  const save = async () => {
    if (saveInFlight.current || !timezone || timezone === savedTimezone) return;
    saveInFlight.current = true;
    setSaving(true);
    setError("");
    setStatus("");
    try {
      // Timezone is a persisted profile field, not a channel-preference field.
      const profile = await fetchApi<unknown>("/auth/me/", {
        method: "PUT",
        body: JSON.stringify({ timezone }),
        suppressErrorToast: true,
      });
      const value = readTimezone(profile);
      if (!mounted.current) return;
      setTimezone(value);
      setSavedTimezone(value);
      setStatus("Timezone saved.");
    } catch {
      if (mounted.current) {
        setError(
          "Could not save your timezone. Your selection is still here; try saving again.",
        );
      }
    } finally {
      saveInFlight.current = false;
      if (mounted.current) setSaving(false);
    }
  };

  const options = [...new Set(["UTC", ...timezoneOptions, timezone])].filter(
    Boolean,
  );

  return (
    <section
      aria-labelledby="notification-timezone-title"
      className="rounded-2xl border-4 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411] p-6 space-y-3"
    >
      <h2
        id="notification-timezone-title"
        className="font-display text-xl font-black uppercase text-black dark:text-white"
      >
        Notification timezone
      </h2>
      <p
        id="notification-timezone-help"
        className="text-sm text-gray-500 dark:text-[#c4bbae]"
      >
        This is your account timezone, also used when scheduling notification
        digests.
      </p>
      {loading ? (
        <p role="status">Loading saved timezone…</p>
      ) : savedTimezone ? (
        <>
          <label htmlFor="notification-timezone" className="block font-bold">
            Timezone
          </label>
          <select
            id="notification-timezone"
            value={timezone}
            disabled={saving}
            aria-describedby="notification-timezone-help"
            onChange={(event) => {
              setTimezone(event.target.value);
              setStatus("");
              setError("");
            }}
            className="w-full p-2.5 rounded-lg border-2 border-black dark:border-[#2e2924] bg-white dark:bg-[#151411]"
          >
            {options.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
          <button
            type="button"
            disabled={saving || timezone === savedTimezone}
            onClick={save}
            className="px-4 py-2 bg-primary text-white rounded-lg font-bold disabled:opacity-50"
          >
            {saving ? "Saving timezone…" : "Save timezone"}
          </button>
        </>
      ) : (
        <button
          type="button"
          onClick={() => setLoadAttempt((value) => value + 1)}
        >
          Retry loading timezone
        </button>
      )}
      {error && <p role="alert">{error}</p>}
      <p role="status" aria-live="polite">
        {status}
      </p>
    </section>
  );
}
