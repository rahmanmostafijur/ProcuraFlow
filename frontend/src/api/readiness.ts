import { API_BASE_URL } from "./client";

/** Everything the caller may wait for a sleeping backend: Render's free tier wakes in about a minute. */
export const READINESS_BUDGET_MS = 100_000;
// A host may legitimately hold one request open while it wakes, so a single probe gets a long timeout.
const PROBE_TIMEOUT_MS = 40_000;
const BACKOFF_STEP_MS = 1_000;
const BACKOFF_CAP_MS = 5_000;
const JSON_CONTENT_TYPE = "application/json";

/** `/api/v1` -> `/api/ready`: the readiness route lives beside the versioned API, not under it. */
export const READY_URL = `${API_BASE_URL.replace(/\/v\d+$/, "")}/ready`;

export type ReadinessResult = "ready" | "timeout" | "aborted";

interface WaitOptions {
  budgetMs?: number;
  signal?: AbortSignal;
  fetchImpl?: typeof fetch;
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
}

async function probe(url: string, signal: AbortSignal | undefined, fetchImpl: typeof fetch): Promise<boolean> {
  const controller = new AbortController();
  const forwardAbort = () => controller.abort();
  signal?.addEventListener("abort", forwardAbort);
  const timer = setTimeout(forwardAbort, PROBE_TIMEOUT_MS);
  try {
    const response = await fetchImpl(url, {
      signal: controller.signal,
      cache: "no-store",
      headers: { Accept: JSON_CONTENT_TYPE },
    });
    // A waking host answers with an HTML placeholder page (often 200), or 502/503/504. Neither is our API.
    if (!response.ok || !response.headers.get("content-type")?.includes(JSON_CONTENT_TYPE)) {
      return false;
    }
    const body: unknown = await response.json();
    return typeof body === "object" && body !== null && (body as { status?: unknown }).status === "ready";
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", forwardAbort);
  }
}

function sleepUnlessAborted(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms);
    function done() {
      clearTimeout(timer);
      signal?.removeEventListener("abort", done);
      resolve();
    }
    signal?.addEventListener("abort", done);
  });
}

/**
 * Poll the readiness endpoint until the API (and its database) answers, retrying with a capped
 * backoff. Resolves "timeout" once the budget is spent, so callers can show an error rather than
 * an endless spinner.
 */
export async function waitForBackend(url: string = READY_URL, options: WaitOptions = {}): Promise<ReadinessResult> {
  const {
    budgetMs = READINESS_BUDGET_MS,
    signal,
    fetchImpl = (input, init) => fetch(input, init),
    now = Date.now,
    sleep = (ms) => sleepUnlessAborted(ms, signal),
  } = options;
  const startedAt = now();

  for (let attempt = 0; ; attempt += 1) {
    if (signal?.aborted) return "aborted";
    const remainingMs = budgetMs - (now() - startedAt);
    if (remainingMs <= 0) return "timeout";

    const isReady = await probe(url, signal, fetchImpl);
    if (signal?.aborted) return "aborted";
    if (isReady) return "ready";

    const backoffMs = Math.min(BACKOFF_STEP_MS * (attempt + 1), BACKOFF_CAP_MS);
    await sleep(Math.min(backoffMs, Math.max(budgetMs - (now() - startedAt), 0)));
  }
}
