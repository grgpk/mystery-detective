import { agentHeaders, agentUrl } from "@/lib/agent-server";

/** Spoiler-free case catalogue from the agent, for the case picker. */
export async function GET(): Promise<Response> {
  try {
    const response = await fetch(agentUrl("/cases"), { cache: "no-store", headers: agentHeaders() });
    if (!response.ok) throw new Error(`agent returned ${response.status}`);
    return Response.json(await response.json());
  } catch {
    return Response.json({ error: "The case archive is unreachable." }, { status: 502 });
  }
}
