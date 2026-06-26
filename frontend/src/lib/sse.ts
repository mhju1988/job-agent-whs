import { fetchEventSource, type EventSourceMessage } from "@microsoft/fetch-event-source";
import { ENV } from "./env";
import { getAuthToken } from "./api";
import type { ProgressEvent, RunKind } from "./types";

export interface RunStreamHandlers {
  onProgress?: (e: ProgressEvent) => void;
  onResult?: (result: Record<string, unknown>) => void;
  onError?: (message: string) => void;
}

function dispatch(ev: EventSourceMessage, handlers: RunStreamHandlers): void {
  if (!ev.data) return;
  let data: Record<string, unknown>;
  try {
    data = JSON.parse(ev.data) as Record<string, unknown>;
  } catch {
    return; // ignore keepalives / malformed frames rather than killing the stream
  }
  if (ev.event === "progress") handlers.onProgress?.(data as ProgressEvent);
  else if (ev.event === "result") handlers.onResult?.(data);
  else if (ev.event === "error") handlers.onError?.(String(data.message ?? "Failed"));
}

/**
 * Stream an agent run via Server-Sent Events.
 *
 * Uses fetch-event-source (not native EventSource) so we can send the
 * Authorization header. Resolves when the terminal result/error event arrives.
 */
export async function runStream(
  kind: RunKind,
  body: Record<string, unknown>,
  handlers: RunStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAuthToken();
  await fetchEventSource(`${ENV.apiBaseUrl}/api/runs/${kind}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
    signal,
    openWhenHidden: true,
    async onopen(response) {
      if (!response.ok) {
        // Read the JSON body to surface the server's detail string (e.g. "No profile").
        let msg = `Server error (HTTP ${response.status})`;
        try {
          const json = (await response.json()) as { detail?: string };
          if (json?.detail) msg = String(json.detail);
        } catch { /* ignore unreadable body */ }
        throw new Error(msg);
      }
    },
    onmessage: (ev) => dispatch(ev, handlers),
    onerror(err) {
      handlers.onError?.(err instanceof Error ? err.message : "Connection error");
      throw err; // stop retrying
    },
  });
}

/**
 * Upload a CV (multipart) and stream the parse → embed → save → re-score
 * progress. No Content-Type header — the browser sets the multipart boundary.
 *
 * Unlike runStream, all errors (HTTP and network) are handled in an outer
 * try/catch so we can async-read the JSON error body from HTTP 4xx/5xx
 * responses and surface the server's `detail` string to the user.
 * The returned Promise always resolves — errors are delivered via onError.
 */
export async function uploadCvStream(
  file: File,
  handlers: RunStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAuthToken();
  const form = new FormData();
  form.append("file", file);
  try {
    await fetchEventSource(`${ENV.apiBaseUrl}/api/cv`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
      signal,
      openWhenHidden: true,
      onmessage: (ev) => dispatch(ev, handlers),
      onerror(err) {
        throw err; // propagate everything to the outer catch
      },
    });
  } catch (err) {
    if (signal?.aborted) return; // intentional cancel — not an error
    if (err instanceof Response) {
      // HTTP 4xx/5xx: read the JSON body to surface the server's detail string.
      let msg = `Upload failed (HTTP ${err.status})`;
      try {
        const body = (await err.json()) as { detail?: string };
        if (body?.detail) msg = String(body.detail);
      } catch {
        /* response body unreadable — keep the status-code message */
      }
      handlers.onError?.(msg);
    } else {
      // Network / connection error (DNS, CORS, etc.)
      handlers.onError?.(err instanceof Error ? err.message : "Connection error");
    }
  }
}
