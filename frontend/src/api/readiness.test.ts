import { describe, expect, it, vi } from "vitest";

import { READINESS_BUDGET_MS, READY_URL, waitForBackend } from "./readiness";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function htmlResponse(status = 200): Response {
  return new Response("<html><body>Service waking up</body></html>", {
    status,
    headers: { "Content-Type": "text/html; charset=utf-8" },
  });
}

/** A fake clock: sleeping advances time instantly, so budget behaviour is testable without waiting. */
function fakeClock() {
  let elapsed = 0;
  const delays: number[] = [];
  return {
    delays,
    elapsed: () => elapsed,
    now: () => elapsed,
    sleep: async (ms: number) => {
      delays.push(ms);
      elapsed += ms;
    },
  };
}

describe("waitForBackend", () => {
  it("returns ready when the first probe succeeds", async () => {
    const clock = fakeClock();
    const fetchImpl = vi.fn().mockResolvedValue(jsonResponse({ status: "ready" }));

    const result = await waitForBackend(READY_URL, { fetchImpl, ...clock });

    expect(result).toBe("ready");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("treats an HTML response as still waking, judged by Content-Type rather than by a parse error", async () => {
    const clock = fakeClock();
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(htmlResponse(200))
      .mockResolvedValueOnce(jsonResponse({ status: "ready" }));

    const result = await waitForBackend(READY_URL, { fetchImpl, ...clock });

    expect(result).toBe("ready");
    expect(fetchImpl).toHaveBeenCalledTimes(2);
  });

  it.each([502, 503, 504])("retries on %i while the server wakes", async (status) => {
    const clock = fakeClock();
    const fetchImpl = vi
      .fn()
      .mockResolvedValueOnce(htmlResponse(status))
      .mockResolvedValueOnce(jsonResponse({ status: "unavailable" }, status))
      .mockResolvedValueOnce(jsonResponse({ status: "ready" }));

    const result = await waitForBackend(READY_URL, { fetchImpl, ...clock });

    expect(result).toBe("ready");
    expect(fetchImpl).toHaveBeenCalledTimes(3);
  });

  it("retries after a network error", async () => {
    const clock = fakeClock();
    const fetchImpl = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(jsonResponse({ status: "ready" }));

    const result = await waitForBackend(READY_URL, { fetchImpl, ...clock });

    expect(result).toBe("ready");
  });

  it("backs off between attempts up to a cap", async () => {
    const clock = fakeClock();
    const fetchImpl = vi.fn().mockResolvedValue(htmlResponse(503));

    await waitForBackend(READY_URL, { fetchImpl, budgetMs: 30_000, ...clock });

    expect(clock.delays.slice(0, 7)).toEqual([1000, 2000, 3000, 4000, 5000, 5000, 5000]);
  });

  it("gives up with a timeout once the budget is spent instead of retrying forever", async () => {
    const clock = fakeClock();
    const fetchImpl = vi.fn().mockResolvedValue(htmlResponse(503));

    const result = await waitForBackend(READY_URL, { fetchImpl, ...clock });

    expect(result).toBe("timeout");
    expect(clock.elapsed()).toBeGreaterThanOrEqual(READINESS_BUDGET_MS);
    expect(clock.elapsed()).toBeLessThan(READINESS_BUDGET_MS + 6000);
  });

  it("uses a 100 second budget by default", () => {
    expect(READINESS_BUDGET_MS).toBe(100_000);
  });

  it("stops and reports aborted when the caller cancels", async () => {
    const clock = fakeClock();
    const controller = new AbortController();
    const fetchImpl = vi.fn().mockImplementation(async () => {
      controller.abort();
      return htmlResponse(503);
    });

    const result = await waitForBackend(READY_URL, { fetchImpl, signal: controller.signal, ...clock });

    expect(result).toBe("aborted");
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it("derives the readiness route from the versioned API base", () => {
    expect(READY_URL.endsWith("/api/ready")).toBe(true);
  });
});
