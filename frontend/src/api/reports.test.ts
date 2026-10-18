import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { downloadInventoryStatusCsv } from "./reports";

describe("downloadInventoryStatusCsv", () => {
  const createObjectURL = vi.fn(() => "blob:csv-url");
  const revokeObjectURL = vi.fn();

  beforeEach(() => {
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    createObjectURL.mockClear();
    revokeObjectURL.mockClear();
  });

  it("fetches through the authenticated client, so the bearer token is sent", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue({ data: new Blob(["sku\n"]) });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    await downloadInventoryStatusCsv();

    expect(get).toHaveBeenCalledWith("/reports/inventory-status.csv", { responseType: "blob" });
  });

  it("saves the response as inventory-status.csv and releases the object URL", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ data: new Blob(["sku\n"]) });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      expect(this.download).toBe("inventory-status.csv");
      expect(this.href).toContain("blob:csv-url");
    });

    await downloadInventoryStatusCsv();

    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:csv-url");
    expect(document.querySelector("a[download]")).toBeNull();
  });

  it("propagates a failed request so the page can tell the user", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("403"));

    await expect(downloadInventoryStatusCsv()).rejects.toThrow("403");
    expect(createObjectURL).not.toHaveBeenCalled();
  });
});
