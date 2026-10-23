import "server-only";

// Server-side access to the Python agent. The shared secret never reaches the browser.
const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8000/agent";
const AGENT_SHARED_SECRET = process.env.AGENT_SHARED_SECRET ?? "";

export const agentRunUrl = AGENT_URL;

export function agentUrl(path: string): URL {
  return new URL(path, AGENT_URL);
}

export function agentHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return AGENT_SHARED_SECRET ? { "X-Agent-Key": AGENT_SHARED_SECRET, ...extra } : extra;
}
