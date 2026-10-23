import { agentHeaders, agentUrl } from "@/lib/agent-server";
import { SESSION_COOKIE } from "@/lib/session";

/** Today's case and leaderboard, plus the caller's own daily game (found by their session cookie). */
export async function GET(request: Request): Promise<Response> {
  const session = request.headers.get("cookie")?.match(new RegExp(`(?:^|;\\s*)${SESSION_COOKIE}=([^;]+)`))?.[1];
  try {
    const response = await fetch(agentUrl("/daily"), {
      cache: "no-store",
      headers: agentHeaders(session ? { "X-Session-Id": decodeURIComponent(session) } : {}),
    });
    if (!response.ok) throw new Error(`agent returned ${response.status}`);
    return Response.json(await response.json());
  } catch {
    return Response.json({ error: "The daily case is unavailable." }, { status: 502 });
  }
}
