import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, setAuthToken } from "@/lib/api";

describe("api client", () => {
  beforeEach(() => setAuthToken("test-token"));
  afterEach(() => vi.unstubAllGlobals());

  it("attaches the Bearer token", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ user_id: "u-1", profile_label: "x", scout_sources: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await api.getMe();

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Headers;
    expect(headers.get("Authorization")).toBe("Bearer test-token");
  });

  it("maps a non-2xx response to ApiError with the detail message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        statusText: "Conflict",
        json: async () => ({ detail: "Cannot transition" }),
      }),
    );

    await expect(api.transition("a-1", "applied")).rejects.toBeInstanceOf(ApiError);
    await expect(api.transition("a-1", "applied")).rejects.toMatchObject({
      status: 409,
      message: "Cannot transition",
    });
  });

  it("surfaces the real status + detail on a failed document download", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        json: async () => ({ detail: "Not authenticated" }),
      }),
    );

    await expect(api.downloadDocument("a-1", "cover")).rejects.toMatchObject({
      status: 401,
      message: "Not authenticated",
    });
  });
});
