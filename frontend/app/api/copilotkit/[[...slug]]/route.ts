import { HttpAgent } from "@ag-ui/client";
import { CopilotRuntime, createCopilotRuntimeHandler } from "@copilotkit/runtime/v2";
import type { NextRequest } from "next/server";

import { agentHeaders, agentRunUrl } from "@/lib/agent-server";
import { SESSION_COOKIE } from "@/lib/session";

function sessionFrom(request: Request): string | null {
  const cookies = request.headers.get("cookie") ?? "";
  const match = cookies.match(new RegExp(`(?:^|;\\s*)${SESSION_COOKIE}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : null;
}

const runtime = new CopilotRuntime({
  // Per request, so the anonymous session travels to the agent, which uses it to own game threads.
  agents: ({ request }) => ({
    game_master: new HttpAgent({
      url: agentRunUrl,
      headers: agentHeaders({ "X-Session-Id": sessionFrom(request) ?? "" }),
    }),
  }),
  // Turns `show_ui` tool results carrying `a2ui_operations` into A2UI surface activities.
  a2ui: {},
});

const handler = createCopilotRuntimeHandler({ runtime, basePath: "/api/copilotkit" });

async function handle(request: NextRequest): Promise<Response> {
  if (!sessionFrom(request)) {
    return Response.json({ error: "Missing session. Reload the page." }, { status: 401 });
  }
  return handler(request);
}

export { handle as GET, handle as POST };
