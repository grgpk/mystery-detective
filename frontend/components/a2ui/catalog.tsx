"use client";

import type { ActivityMessage } from "@ag-ui/client";
import { createCatalog, viewerTheme } from "@copilotkit/a2ui-renderer";
import { createA2UIMessageRenderer, type A2UITheme } from "@copilotkit/react-core/v2";

import { AccusationForm } from "./AccusationForm";
import { CaseBriefing } from "./CaseBriefing";
import { ClueCard } from "./ClueCard";
import { ConfrontPicker } from "./ConfrontPicker";
import { CATALOG_ID, catalogDefinitions } from "./definitions";
import { LocationCard } from "./LocationCard";
import { NarrationBlock } from "./NarrationBlock";
import { SuspectCard } from "./SuspectCard";
import { VerdictScreen } from "./VerdictScreen";

export const gameCatalog = createCatalog(
  catalogDefinitions,
  {
    Stack: ({ props, children }) => (
      <section className="grid gap-2">
        {props.title && (
          <h2 className="font-type text-on-desk-soft text-sm tracking-[0.2em] uppercase">{props.title}</h2>
        )}
        {props.children.map((id) => (
          <div key={id}>{children(id)}</div>
        ))}
      </section>
    ),
    CaseBriefing: () => <CaseBriefing />,
    SuspectCard: ({ props }) => <SuspectCard suspectId={props.suspectId} />,
    LocationCard: ({ props }) => <LocationCard locationId={props.locationId} />,
    ClueCard: ({ props }) => <ClueCard clueId={props.clueId} />,
    NarrationBlock: ({ props }) => <NarrationBlock title={props.title} text={props.text} tone={props.tone} />,
    ConfrontPicker: ({ props }) => <ConfrontPicker suspectId={props.suspectId} />,
    AccusationForm: () => <AccusationForm />,
    VerdictScreen: () => <VerdictScreen />,
  },
  { catalogId: CATALOG_ID },
);

const a2uiRenderer = createA2UIMessageRenderer({
  theme: viewerTheme as A2UITheme,
  catalog: gameCatalog,
  // Our components talk to the game through useGame(); no generic A2UI action should reach the agent.
  onAction: () => null,
});

const RenderSurface = a2uiRenderer.render;

/** Renders one agent-emitted A2UI surface, wherever the layout places it. */
export function Surface({ message }: { message: ActivityMessage }) {
  return (
    <RenderSurface activityType={message.activityType} content={message.content} message={message} agent={undefined} />
  );
}
