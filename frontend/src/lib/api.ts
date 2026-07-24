import { ENV } from "./env";
import type {
  AdminUser,
  Application,
  ApplicationStatus,
  DeleteSummary,
  Job,
  Match,
  MatchGraph,
  Me,
  ObsEvent,
  ObsRun,
  Profile,
  SearchSuggestion,
} from "./types";

/** Current access token, set by the SessionProvider on auth-state change. */
let _token: string | null = null;
export function setAuthToken(token: string | null): void {
  _token = token;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (_token) headers.set("Authorization", `Bearer ${_token}`);
  const res = await fetch(`${ENV.apiBaseUrl}${path}`, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body?.detail) detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  getMe: () => apiFetch<Me>("/api/me"),
  getProfile: () => apiFetch<Profile>("/api/profile"),
  updateProfile: (body: { skills?: string[]; summary?: string }) =>
    apiFetch<Profile>("/api/profile", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  // CV upload streams progress — see uploadCvStream in lib/sse.ts.
  getSearchSuggestions: () =>
    apiFetch<SearchSuggestion[]>("/api/search/suggestions"),
  getJobs: () => apiFetch<Job[]>("/api/jobs"),
  /** The caller's hidden jobs (newest-hidden first) for the restore view. */
  getHiddenJobs: () => apiFetch<Job[]>("/api/jobs/hidden"),
  getMatches: (minScore = 0) =>
    apiFetch<Match[]>(`/api/matches?min_score=${minScore}`),
  /** Both scoring stages for the fit-graph page (cosine + LLM). */
  getMatchGraph: () => apiFetch<MatchGraph>("/api/matches/graph"),
  getApplications: () => apiFetch<Application[]>("/api/applications"),
  transition: (id: string, target: ApplicationStatus) =>
    apiFetch<{ status: string }>(`/api/applications/${id}/transition`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target }),
    }),
  hideJobs: (jobIds: string[]) =>
    apiFetch<{ hidden: number }>("/api/jobs/hide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_ids: jobIds }),
    }),
  unhideJobs: (jobIds: string[]) =>
    apiFetch<{ unhidden: number }>("/api/jobs/unhide", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_ids: jobIds }),
    }),
  deleteApplications: (ids: string[]) =>
    apiFetch<{ deleted: number; files_deleted: number }>(
      "/api/applications/delete",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ application_ids: ids }),
      },
    ),
  deleteMyData: () =>
    apiFetch<DeleteSummary>("/api/data/delete", { method: "POST" }),
  getRuns: () => apiFetch<ObsRun[]>("/api/observability/runs"),
  getRunEvents: (runId: string) =>
    apiFetch<ObsEvent[]>(`/api/observability/runs/${runId}/events`),
  getAdminUsers: () => apiFetch<AdminUser[]>("/api/admin/users"),
  banUser: (id: string) => apiFetch<{ ok: boolean }>(`/api/admin/users/${id}/ban`, { method: "POST" }),
  unbanUser: (id: string) => apiFetch<{ ok: boolean }>(`/api/admin/users/${id}/unban`, { method: "POST" }),
  confirmUserEmail: (id: string) =>
    apiFetch<{ ok: boolean }>(`/api/admin/users/${id}/confirm-email`, { method: "POST" }),
  setUserRole: (id: string, role: "user" | "admin") =>
    apiFetch<{ ok: boolean }>(`/api/admin/users/${id}/role`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    }),
  getUserApplications: (id: string) =>
    apiFetch<Application[]>(`/api/admin/users/${id}/applications`),
  deleteJobAdmin: (id: string) =>
    apiFetch<{ ok: boolean }>(`/api/admin/jobs/${id}`, { method: "DELETE" }),
  getAdminObservabilitySummary: () => apiFetch<ObsRun[]>("/api/admin/observability/summary"),
  /** Absolute URL for a document download (caller appends auth via fetch/anchor). */
  documentUrl: (id: string, kind: "cover" | "cv") =>
    `${ENV.apiBaseUrl}/api/applications/${id}/documents/${kind}`,
  /** Fetch a document as a blob (Bearer-authed) for download. */
  downloadDocument: async (id: string, kind: "cover" | "cv"): Promise<Blob> => {
    const headers = new Headers();
    if (_token) headers.set("Authorization", `Bearer ${_token}`);
    const res = await fetch(api.documentUrl(id, kind), { headers });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const body = (await res.json()) as { detail?: string };
        if (body?.detail) detail = body.detail;
      } catch {
        /* non-JSON error body */
      }
      throw new ApiError(res.status, detail);
    }
    return res.blob();
  },
};

export function getAuthToken(): string | null {
  return _token;
}
