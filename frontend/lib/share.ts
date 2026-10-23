// A shared result travels entirely in the URL, so the results page and its preview image need no storage.
// Values are clamped on the way in: a hand-edited link can only ever show a plausible card.

export const RANKS = ["Rookie", "Inspector", "Chief Inspector", "Legendary Detective"] as const;
export type Rank = (typeof RANKS)[number];

export interface SharedResult {
  title: string;
  rank: Rank;
  score: number;
  turns: number;
  solved: boolean;
}

const MAX_TITLE = 80;

export function toSearchParams(result: SharedResult): URLSearchParams {
  return new URLSearchParams({
    t: result.title,
    r: result.rank,
    s: String(result.score),
    n: String(result.turns),
    ok: result.solved ? "1" : "0",
  });
}

function int(value: unknown, min: number, max: number): number {
  const n = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : min;
}

export function fromSearchParams(params: Record<string, string | string[] | undefined>): SharedResult | null {
  const get = (key: string) => {
    const value = params[key];
    return Array.isArray(value) ? value[0] : value;
  };
  const title = (get("t") ?? "").trim().slice(0, MAX_TITLE);
  const rank = RANKS.find((r) => r === get("r"));
  if (!title || !rank) return null;
  return { title, rank, score: int(get("s"), 0, 100), turns: int(get("n"), 0, 99), solved: get("ok") === "1" };
}

export function headline(result: SharedResult): string {
  return result.solved
    ? `Solved in ${result.turns} turn${result.turns === 1 ? "" : "s"}: ${result.rank}`
    : `The killer got away: ${result.rank}`;
}
