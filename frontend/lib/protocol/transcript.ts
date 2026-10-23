import type { ActivityMessage, Message } from "@ag-ui/client";

// The agent's A2UI middleware turns `show_ui` tool results into activities of this type.
export const A2UI_ACTIVITY_TYPE = "a2ui-surface";

// Surfaces that live in fixed panels rather than inline in the case log.
export type PanelSurface = "roster" | "map" | "verdict";
const PANEL_SURFACES: readonly PanelSurface[] = ["roster", "map", "verdict"];

export type TranscriptEntry =
  | { kind: "speech"; id: string; speaker: string; text: string }
  | { kind: "player"; id: string; text: string }
  | { kind: "surface"; id: string; surfaceKind: string; message: ActivityMessage };

interface SurfaceOperation {
  createSurface?: { surfaceId: string };
}

export function surfaceId(message: ActivityMessage): string | null {
  const ops = message.content?.a2ui_operations as SurfaceOperation[] | undefined;
  return ops?.find((op) => op.createSurface)?.createSurface?.surfaceId ?? null;
}

/** Surface ids are `<kind>-<sequence>`, assigned by the agent. */
export function surfaceKind(message: ActivityMessage): string | null {
  const id = surfaceId(message);
  return id ? id.slice(0, id.lastIndexOf("-")) : null;
}

/** Agent message ids are `msg-<speaker>-<random>`; speaker is "narrator" or a suspect id. */
export function speakerOf(messageId: string): string {
  const [, speaker] = messageId.split("-");
  return speaker ?? "narrator";
}

function isA2UI(message: Message): message is ActivityMessage {
  return message.role === "activity" && message.activityType === A2UI_ACTIVITY_TYPE;
}

export function buildTranscript(messages: readonly Message[]): TranscriptEntry[] {
  const entries: TranscriptEntry[] = [];
  for (const message of messages) {
    if (message.role === "user" && typeof message.content === "string") {
      entries.push({ kind: "player", id: message.id, text: message.content });
    } else if (message.role === "assistant" && message.content) {
      entries.push({ kind: "speech", id: message.id, speaker: speakerOf(message.id), text: message.content });
    } else if (isA2UI(message)) {
      const kind = surfaceKind(message);
      if (kind && !PANEL_SURFACES.includes(kind as PanelSurface)) {
        entries.push({ kind: "surface", id: message.id, surfaceKind: kind, message });
      }
    }
  }
  return entries;
}

/** The most recent surface of a panel kind (the agent may re-emit panels on reconnect). */
export function latestPanel(messages: readonly Message[], kind: PanelSurface): ActivityMessage | null {
  for (let i = messages.length - 1; i >= 0; i--) {
    const message = messages[i];
    if (isA2UI(message) && surfaceKind(message) === kind) return message;
  }
  return null;
}
