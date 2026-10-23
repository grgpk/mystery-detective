import type { CatalogDefinitions } from "@copilotkit/a2ui-renderer";
import { z } from "zod";

// The only components the agent may emit. Must match agent/app/a2ui/catalog.py.
// Cards take ids and read live details from shared state, so a surface stays current as the game moves.
export const CATALOG_ID = "https://lastalibi.game/a2ui/catalog/v1";

export const catalogDefinitions = {
  Stack: {
    description: "Vertical list of child components, optionally titled.",
    props: z.object({ title: z.string().optional(), children: z.array(z.string()) }),
  },
  CaseBriefing: {
    description: "The case file handed to the detective at the start, with a Begin button.",
    props: z.object({}),
  },
  SuspectCard: {
    description: "A suspect with composure meter and Interrogate / Confront actions.",
    props: z.object({ suspectId: z.string() }),
  },
  LocationCard: {
    description: "A room in the house with an Examine action.",
    props: z.object({ locationId: z.string() }),
  },
  ClueCard: {
    description: "A discovered clue that can be pinned to the evidence board.",
    props: z.object({ clueId: z.string() }),
  },
  NarrationBlock: {
    description: "A narrated scene transition or banner.",
    props: z.object({
      title: z.string().optional(),
      text: z.string(),
      tone: z.enum(["neutral", "alert", "success"]).optional(),
    }),
  },
  ConfrontPicker: {
    description: "Pick a statement and a contradicting piece of evidence to confront a suspect with.",
    props: z.object({ suspectId: z.string() }),
  },
  AccusationForm: {
    description: "Name the culprit, motive, and up to three pieces of key evidence.",
    props: z.object({}),
  },
  VerdictScreen: {
    description: "Final score, rank, and the true timeline.",
    props: z.object({}),
  },
} satisfies CatalogDefinitions;
