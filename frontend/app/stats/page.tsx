import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";

import { agentHeaders, agentUrl } from "@/lib/agent-server";

export const metadata: Metadata = { title: "Stats · The Last Alibi", robots: { index: false } };

type Props = PageProps<"/stats">;

interface Target {
  value: number | null;
  min: number | null;
  max: number | null;
  met: boolean | null;
}

interface Stats {
  days: number;
  games: { opened: number; begun: number; accused: number; solved: number; abandoned: number };
  targets: Record<"accusation_rate" | "solve_rate", Target>;
  accused_games: {
    avg_turns_used: number | null;
    avg_hints: number | null;
    avg_minutes_to_accuse: number | null;
    avg_score: number | null;
    ranks: Record<string, number>;
  };
  stalls: Record<string, number>;
  difficulty: Record<string, { begun: number; accusation_rate: number | null; solve_rate: number | null }>;
  cases: {
    caseId: string;
    title: string;
    generated: boolean;
    opened: number;
    begun: number;
    accused: number;
    solveRate: number | null;
    avgScore: number | null;
  }[];
}

const DAY_OPTIONS = [7, 30, 90];

const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v * 100)}%`);
const num = (v: number | null) => (v === null ? "–" : String(v));

function allowed(token: string | undefined): boolean {
  const expected = process.env.STATS_TOKEN;
  if (!expected) return process.env.NODE_ENV !== "production"; // open in local dev only
  return token === expected;
}

export default function StatsPage({ searchParams }: Props) {
  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <p className="font-type text-brass text-xs tracking-[0.35em] uppercase">The Last Alibi</p>
      <h1 className="font-type text-on-desk mb-6 text-3xl">Case statistics</h1>
      <Suspense fallback={<p className="text-on-desk-soft italic">Pulling the files…</p>}>
        <StatsBody searchParams={searchParams} />
      </Suspense>
    </main>
  );
}

async function StatsBody({ searchParams }: Pick<Props, "searchParams">) {
  const params = await searchParams;
  const token = typeof params.token === "string" ? params.token : undefined;
  if (!allowed(token)) notFound();
  const days = DAY_OPTIONS.includes(Number(params.days)) ? Number(params.days) : 30;

  let stats: Stats;
  try {
    const response = await fetch(agentUrl(`/stats?days=${days}`), { cache: "no-store", headers: agentHeaders() });
    if (!response.ok) throw new Error(String(response.status));
    stats = await response.json();
  } catch {
    return <p className="text-string">The agent is unreachable, so there are no statistics to show.</p>;
  }
  const { games, targets, accused_games: accused } = stats;

  return (
    <>
      <nav className="mb-6 flex gap-2 text-sm" aria-label="Period">
        {DAY_OPTIONS.map((d) => (
          <Link
            key={d}
            href={{ query: { ...(token ? { token } : {}), days: d } }}
            aria-current={d === days ? "page" : undefined}
            className={`rounded-sm border px-3 py-1 ${d === days ? "border-brass text-brass" : "border-on-desk/25 text-on-desk-soft"}`}
          >
            Last {d} days
          </Link>
        ))}
      </nav>

      <section className="mb-6 grid gap-4 sm:grid-cols-2" aria-label="Targets">
        <TargetCard title="Reach an accusation" target={targets.accusation_rate} goal="at least 70% of begun games" />
        <TargetCard title="Solve rate" target={targets.solve_rate} goal="40-70% (lower is unfair, higher too easy)" />
      </section>

      <section className="paper mb-6 rounded-sm p-5" aria-labelledby="funnel">
        <h2 id="funnel" className="font-type mb-3 text-lg">
          Games
        </h2>
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {(
            [
              ["Opened", games.opened],
              ["Begun", games.begun],
              ["Accused", games.accused],
              ["Solved", games.solved],
              ["Abandoned", games.abandoned],
            ] as const
          ).map(([label, value]) => (
            <div key={label}>
              <dt className="font-type text-ink-soft text-xs uppercase">{label}</dt>
              <dd className="font-type text-2xl tabular-nums">{value}</dd>
            </div>
          ))}
        </dl>
        <p className="text-ink-soft mt-4 text-sm">
          Accused games: {num(accused.avg_turns_used)} turns used, {num(accused.avg_hints)} hints,{" "}
          {num(accused.avg_minutes_to_accuse)} minutes, average score {num(accused.avg_score)}.
          {Object.keys(accused.ranks).length > 0 &&
            ` Ranks: ${Object.entries(accused.ranks)
              .map(([rank, n]) => `${rank} ${n}`)
              .join(", ")}.`}
        </p>
      </section>

      <section className="paper mb-6 rounded-sm p-5" aria-labelledby="stalls">
        <h2 id="stalls" className="font-type mb-1 text-lg">
          Where abandoned games stalled
        </h2>
        <p className="text-ink-soft mb-3 text-sm">Begun, not accused, idle for over an hour.</p>
        {Object.keys(stats.stalls).length === 0 ? (
          <p className="italic">No abandoned games.</p>
        ) : (
          <ul className="grid gap-1">
            {Object.entries(stats.stalls).map(([reason, n]) => (
              <li key={reason} className="flex justify-between gap-4">
                <span>{reason}</span>
                <span className="tabular-nums">{n}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      {Object.keys(stats.difficulty).length > 0 && (
        <section className="paper mb-6 rounded-sm p-5" aria-labelledby="by-difficulty">
          <h2 id="by-difficulty" className="font-type mb-3 text-lg">
            By difficulty
          </h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="font-type text-ink-soft border-ink/20 border-b text-left text-xs uppercase">
                <th className="py-1 font-normal">Level</th>
                <th className="py-1 text-right font-normal">Begun</th>
                <th className="py-1 text-right font-normal">Reach accusation</th>
                <th className="py-1 text-right font-normal">Solve rate</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(stats.difficulty).map(([level, row]) => (
                <tr key={level} className="border-ink/10 border-b">
                  <td className="py-1 capitalize">{level}</td>
                  <td className="py-1 text-right tabular-nums">{row.begun}</td>
                  <td className="py-1 text-right tabular-nums">{pct(row.accusation_rate)}</td>
                  <td className="py-1 text-right tabular-nums">{pct(row.solve_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section className="paper overflow-x-auto rounded-sm p-5" aria-labelledby="per-case">
        <h2 id="per-case" className="font-type mb-3 text-lg">
          By case
        </h2>
        <table className="w-full min-w-[560px] text-sm">
          <thead>
            <tr className="font-type text-ink-soft border-ink/20 border-b text-left text-xs uppercase">
              <th className="py-1 font-normal">Case</th>
              <th className="py-1 text-right font-normal">Opened</th>
              <th className="py-1 text-right font-normal">Begun</th>
              <th className="py-1 text-right font-normal">Accused</th>
              <th className="py-1 text-right font-normal">Solve rate</th>
              <th className="py-1 text-right font-normal">Avg score</th>
            </tr>
          </thead>
          <tbody>
            {stats.cases.map((c) => (
              <tr key={c.caseId} className="border-ink/10 border-b">
                <td className="py-1">
                  {c.title}
                  {c.generated && <span className="text-ink-soft"> (generated)</span>}
                </td>
                <td className="py-1 text-right tabular-nums">{c.opened}</td>
                <td className="py-1 text-right tabular-nums">{c.begun}</td>
                <td className="py-1 text-right tabular-nums">{c.accused}</td>
                <td className="py-1 text-right tabular-nums">{pct(c.solveRate)}</td>
                <td className="py-1 text-right tabular-nums">{num(c.avgScore)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </>
  );
}

function TargetCard({ title, target, goal }: { title: string; target: Target; goal: string }) {
  const status = target.met === null ? "No data yet" : target.met ? "On target" : "Off target";
  const tone = target.met === null ? "text-ink-soft" : target.met ? "text-success" : "text-alert";
  return (
    <article className="paper rounded-sm p-5">
      <h2 className="font-type text-ink-soft text-xs uppercase">{title}</h2>
      <p className="font-type text-4xl tabular-nums">{pct(target.value)}</p>
      <p className={`font-type text-sm uppercase ${tone}`}>{status}</p>
      <p className="text-ink-soft mt-1 text-xs">Goal: {goal}</p>
    </article>
  );
}
