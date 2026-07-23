import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { api, setAuthToken } from "../api";

describe("delete/hide api methods", () => {
  beforeEach(() => {
    setAuthToken("tok");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ hidden: 2 }), { status: 200 })),
    );
  });
  afterEach(() => vi.unstubAllGlobals());

  it("hideJobs POSTs job_ids and returns the body", async () => {
    const res = await api.hideJobs(["a", "b"]);
    expect(res).toEqual({ hidden: 2 });
    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/jobs/hide");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ job_ids: ["a", "b"] });
  });

  it("unhideJobs targets the unhide endpoint", async () => {
    await api.unhideJobs(["a"]);
    const [url] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/jobs/unhide");
  });

  it("getHiddenJobs GETs the hidden endpoint", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify([{ id: "j1" }]), { status: 200 })),
    );
    const res = await api.getHiddenJobs();
    expect(res).toEqual([{ id: "j1" }]);
    const [url] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/jobs/hidden");
  });

  it("deleteApplications POSTs application_ids", async () => {
    await api.deleteApplications(["x"]);
    const [url, init] = (fetch as unknown as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(String(url)).toContain("/api/applications/delete");
    expect(JSON.parse(init.body)).toEqual({ application_ids: ["x"] });
  });
});
