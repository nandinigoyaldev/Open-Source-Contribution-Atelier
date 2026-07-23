import { useState, useEffect, useRef, useCallback } from "react";

const POLL_INTERVAL = 5 * 60 * 1000;
const STORAGE_KEY = "atelier-build-version";

interface BuildMetadata {
  version: string;
  builtAt: string;
}

function readStoredVersion(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistVersion(version: string) {
  try {
    localStorage.setItem(STORAGE_KEY, version);
  } catch {
    // storage full or blocked — ignore
  }
}

export function useVersionCheck() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const initialVersion = useRef<string | null>(readStoredVersion());

  const checkForUpdate = useCallback(async () => {
    try {
      const res = await fetch("/build-metadata.json", {
        cache: "no-store",
        headers: { "Cache-Control": "no-cache" },
      });
      if (!res.ok) return;

      const meta: BuildMetadata = await res.json();
      if (!meta.version) return;

      const stored = initialVersion.current;

      if (stored === null) {
        persistVersion(meta.version);
        initialVersion.current = meta.version;
      } else if (stored !== meta.version) {
        setUpdateAvailable(true);
      }
    } catch {
      // offline or network error — silently skip
    }
  }, []);

  useEffect(() => {
    checkForUpdate();
    pollRef.current = setInterval(checkForUpdate, POLL_INTERVAL);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [checkForUpdate]);

  const dismiss = useCallback(() => {
    setUpdateAvailable(false);
    const meta = readStoredVersion();
    if (meta) persistVersion(meta);
  }, []);

  const refresh = useCallback(() => {
    window.location.reload();
  }, []);

  return { updateAvailable, dismiss, refresh };
}
