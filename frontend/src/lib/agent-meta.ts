/** Fixed colour dots per agent for the observability views. */
const AGENT_DOT: Record<string, string> = {
  scout: "bg-sky-500",
  matcher: "bg-violet-500",
  writer: "bg-emerald-500",
  tracker: "bg-amber-500",
};

export function agentDot(agent: string): string {
  return AGENT_DOT[agent.toLowerCase()] ?? "bg-muted-foreground";
}
