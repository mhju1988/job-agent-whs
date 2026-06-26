import type { ApplicationStatus } from "./types";

/** Status metadata: label + the CSS-var key (--status-<key>) for color. */
export const STATUS_META: Record<ApplicationStatus, { label: string; key: string }> = {
  new: { label: "New", key: "new" },
  ready_to_send: { label: "Ready to send", key: "ready" },
  applied: { label: "Applied", key: "applied" },
  interview: { label: "Interview", key: "interview" },
  offer: { label: "Offer", key: "offer" },
  rejected: { label: "Rejected", key: "rejected" },
};

export const STATUS_ORDER: ApplicationStatus[] = [
  "new",
  "ready_to_send",
  "applied",
  "interview",
  "offer",
  "rejected",
];

/** Forward-only transitions; mirrors TrackerAgent._ALLOWED_TRANSITIONS. */
export const ALLOWED_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  new: ["ready_to_send"],
  ready_to_send: ["applied"],
  applied: ["interview", "rejected"],
  interview: ["offer", "rejected"],
  offer: ["rejected"],
  rejected: [],
};

/** True when moving an application from `from` to `to` is an allowed transition. */
export function canTransition(
  from: ApplicationStatus,
  to: ApplicationStatus,
): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}
