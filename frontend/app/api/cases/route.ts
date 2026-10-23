const AGENT_URL = process.env.AGENT_URL ?? "http://localhost:8000/agent";

/** Spoiler-free case catalogue from the agent, for the case picker. */
export async function GET(): Promise<Response> {
  try {
    const response = await fetch(new URL("/cases", AGENT_URL), { cache: "no-store" });
    if (!response.ok) throw new Error(`agent returned ${response.status}`);
    return Response.json(await response.json());
  } catch {
    return Response.json({ error: "The case archive is unreachable." }, { status: 502 });
  }
}
