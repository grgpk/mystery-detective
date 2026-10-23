// Mirrors agent/app/models/public.py and actions.py. The agent is the source of truth for these shapes.

export type Phase = "briefing" | "investigating" | "accusing" | "ended";
export type Mood = "calm" | "guarded" | "nervous" | "cracking";
export type StatementKind = "alibi" | "claim" | "testimony" | "confession";

export interface PublicSuspect {
  id: string;
  name: string;
  role: string;
  appearance: string;
  composure: number;
  mood: Mood;
}

export interface PublicLocation {
  id: string;
  label: string;
  description: string;
  examined: boolean;
}

export interface PublicClue {
  id: string;
  title: string;
  text: string;
  location: string | null;
  isNew: boolean;
}

export interface PublicStatement {
  id: string;
  suspect: string;
  text: string;
  kind: StatementKind;
}

export interface TimelineEvent {
  time: string;
  suspect: string;
  event: string;
  source: "claimed" | "verified";
}

export interface BoardLink {
  from: string;
  to: string;
}

export interface Board {
  pins: string[];
  links: BoardLink[];
  notes: string;
}

export interface Option {
  id: string;
  label: string;
}

export interface ScoreBreakdown {
  culpritCorrect: boolean;
  motiveCorrect: boolean;
  validEvidence: string[];
  culpritPoints: number;
  motivePoints: number;
  evidencePoints: number;
  turnPoints: number;
  total: number;
  rank: string;
}

export interface Verdict {
  score: ScoreBreakdown;
  culpritName: string;
  motive: string;
  trueTimeline: TimelineEvent[];
  foundClues: string[];
  missedClues: PublicClue[];
}

export interface PublicState {
  caseId: string;
  title: string;
  place: string;
  briefing: string;
  phase: Phase;
  turnsLeft: number;
  maxTurns: number;
  victim: { name: string; causeOfDeath: string; timeOfDeath: string; crimeScene: string };
  suspects: PublicSuspect[];
  locations: PublicLocation[];
  topics: Option[];
  motiveOptions: Option[];
  clues: PublicClue[];
  statements: PublicStatement[];
  timeline: TimelineEvent[];
  conversation: { suspectId: string; questionsLeft: number } | null;
  board: Board;
  lastContradiction: BoardLink | null;
  verdict: Verdict | null;
  daily: { date: string; leaderboardName: string | null } | null;
}

export interface Accusation {
  suspectId: string;
  motiveId: string;
  evidence: string[];
}

export type GameAction =
  | { type: "start"; caseId?: string }
  | { type: "begin" }
  | { type: "interrogate"; suspectId: string; question: string }
  | { type: "examine"; locationId: string }
  | { type: "hint" }
  | { type: "open_confront"; suspectId: string }
  | { type: "confront"; suspectId: string; items: [string, string] }
  | { type: "open_accuse" }
  | { type: "accuse"; accusation: Accusation }
  | { type: "set_name"; name: string }
  | { type: "sync_board"; board: Board };

/** Turns a hint costs (agent/app/engine/hints.py HINT_COST). */
export const HINT_COST = 2;

export function isPublicState(value: unknown): value is PublicState {
  return typeof value === "object" && value !== null && "caseId" in value && "suspects" in value;
}

/** Spoiler-free summary from the agent's case catalogue. */
export interface CaseSummary {
  caseId: string;
  title: string;
  place: string;
  blurb: string;
  suspects: number;
}

/** What /api/cases returns: the hand-written archive plus the generated-case pool's status. */
export interface CaseCatalogue {
  cases: CaseSummary[];
  fresh: { enabled: boolean; ready: number; generating: boolean };
}

/** Asks the agent for a freshly generated case from its pool. */
export const NEW_CASE_ID = "new";

/** Asks the agent for today's shared case. */
export const DAILY_CASE_ID = "daily";

export interface LeaderboardEntry {
  rank: number;
  name: string;
  score: number;
  turns: number;
  minutes: number;
}

/** What /api/daily returns: today's case, the leaderboard, and the caller's own daily game if any. */
export interface DailyBoard {
  date: string;
  case: { caseId: string; title: string; place: string };
  players: number;
  leaderboard: LeaderboardEntry[];
  you: { threadId: string; phase: Phase; score: number | null; rank: number | null; name: string | null } | null;
}
