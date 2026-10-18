import { useCallback, useEffect, useState } from "react";

import { READY_URL, waitForBackend } from "@/api/readiness";

/** checking: just asked; waking: taking long enough to explain; ready; unavailable: budget spent. */
export type BackendStatus = "checking" | "waking" | "ready" | "unavailable";

// A healthy backend answers well inside this, so the "waking" notice never flashes on a normal visit.
export const WAKING_NOTICE_DELAY_MS = 3_000;
const TICK_MS = 500;

interface BackendReadiness {
  status: BackendStatus;
  elapsedMs: number;
  retry: () => void;
}

export function useBackendReadiness(): BackendReadiness {
  const [status, setStatus] = useState<BackendStatus>("checking");
  const [elapsedMs, setElapsedMs] = useState(0);
  const [run, setRun] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    const startedAt = Date.now();
    setStatus("checking");
    setElapsedMs(0);

    const ticker = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      setElapsedMs(elapsed);
      if (elapsed >= WAKING_NOTICE_DELAY_MS) {
        setStatus((current) => (current === "checking" ? "waking" : current));
      }
    }, TICK_MS);

    void waitForBackend(READY_URL, { signal: controller.signal }).then((result) => {
      clearInterval(ticker);
      if (result === "ready") setStatus("ready");
      if (result === "timeout") setStatus("unavailable");
    });

    return () => {
      controller.abort();
      clearInterval(ticker);
    };
  }, [run]);

  const retry = useCallback(() => setRun((current) => current + 1), []);

  return { status, elapsedMs, retry };
}
