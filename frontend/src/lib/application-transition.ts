import { canTransition } from "./status";
import type { Application, ApplicationStatus } from "./types";

/**
 * Pure optimistic-cache update for an application transition. Returns a NEW
 * array with the matching app's status set to `target` — but only when the move
 * is allowed (`canTransition`). An illegal/stale move leaves the app unchanged,
 * so the optimistic UI never flickers into an illegal state (the server rejects
 * it and `onError` rolls back).
 */
export function applyOptimisticTransition(
  apps: Application[],
  id: string,
  target: ApplicationStatus,
): Application[] {
  return apps.map((app) =>
    app.id === id && canTransition(app.status, target)
      ? { ...app, status: target }
      : app,
  );
}
