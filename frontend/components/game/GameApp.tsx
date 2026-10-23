"use client";

import { CopilotKitProvider } from "@copilotkit/react-core/v2";

import { gameCatalog } from "@/components/a2ui/catalog";
import { GameProvider } from "@/lib/game-context";

import { GameShell } from "./GameShell";

// The agent keeps the whole game server-side, so each run only needs the latest action, not the transcript.
const sendNoHistory = () => [];

export default function GameApp() {
  return (
    <CopilotKitProvider
      runtimeUrl="/api/copilotkit"
      messageFilter={sendNoHistory}
      a2ui={{ catalog: gameCatalog, includeSchema: false }}
      enableInspector={false}
    >
      <GameProvider>
        <GameShell />
      </GameProvider>
    </CopilotKitProvider>
  );
}
