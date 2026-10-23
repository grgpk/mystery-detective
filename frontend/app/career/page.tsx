import type { Metadata } from "next";
import { cookies } from "next/headers";
import Link from "next/link";
import { Suspense } from "react";

import { agentHeaders, agentUrl } from "@/lib/agent-server";
import type { Career } from "@/lib/protocol/types";
import { SESSION_COOKIE } from "@/lib/session";

export const metadata: Metadata = { title: "Your casebook · The Last Alibi", robots: { index: false } };

export default function CareerPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <nav className="mb-4 text-sm">
        <Link href="/" className="text-on-desk-soft hover:text-on-desk">
          ← Back to the case
        </Link>
      </nav>
      <p className="font-type text-brass text-xs tracking-[0.35em] uppercase">Your casebook</p>
      <Suspense fallback={<p className="text-on-desk-soft mt-4 italic">Fetching your service record…</p>}>
        <Record />
      </Suspense>
    </main>
  );
}

const pct = (v: number | null) => (v === null ? "–" : `${Math.round(v * 100)}%`);

async function Record() {
  const session = (await cookies()).get(SESSION_COOKIE)?.value;
  let career: Career | null = null;
  if (session) {
    try {
      const response = await fetch(agentUrl("/career"), {
        cache: "no-store",
        headers: agentHeaders({ "X-Session-Id": session }),
      });
      if (response.ok) career = await response.json();
    } catch {
      career = null;
    }
  }
  if (!career) {
    return <p className="text-on-desk-soft mt-4">Your service record is unavailable right now.</p>;
  }

  return (
    <>
      <h1 className="font-type text-on-desk text-3xl">{career.title}</h1>
      <p className="text-on-desk-soft">
        {career.next
          ? `${career.next.solvesNeeded} more solved case${career.next.solvesNeeded === 1 ? "" : "s"} to ${career.next.title}.`
          : "The top of the ladder. The Yard salutes you."}
      </p>

      <section className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="Record">
        {(
          [
            ["Solved", `${career.solved} / ${career.closed}`],
            ["Solve rate", pct(career.solveRate)],
            ["Best score", career.bestScore ?? "–"],
            ["Best rank", career.bestRank ?? "–"],
            ["Solve streak", `${career.streak.current} (best ${career.streak.best})`],
            [
              "Daily streak",
              `${career.dailyStreak.current}${career.dailyStreak.playedToday ? "" : " · play today!"} (best ${career.dailyStreak.best})`,
            ],
            ["Hints taken", career.hintsUsed],
            [
              "By level",
              (["easy", "normal", "hard"] as const)
                .filter((l) => career.byDifficulty[l])
                .map((l) => `${l[0].toUpperCase()}${l.slice(1)} ${career.byDifficulty[l]!.solved}/${career.byDifficulty[l]!.closed}`)
                .join(" · ") || "–",
            ],
          ] as const
        ).map(([label, value]) => (
          <div key={label} className="paper rounded-sm p-3">
            <p className="font-type text-ink-soft text-[11px] uppercase">{label}</p>
            <p className="font-type text-lg leading-snug">{value}</p>
          </div>
        ))}
      </section>

      <section className="paper mt-6 rounded-sm p-5" aria-labelledby="cases">
        <h2 id="cases" className="font-type mb-3 text-lg">
          Closed cases
        </h2>
        {career.casebook.length === 0 ? (
          <p className="italic">
            No cases closed yet.{" "}
            <Link href="/" className="underline">
              Take one on.
            </Link>
          </p>
        ) : (
          <ol className="grid gap-2">
            {career.casebook.map((c, i) => (
              <li key={`${c.closedOn}-${i}`} className="border-ink/10 flex flex-wrap items-baseline justify-between gap-x-4 border-b pb-2">
                <span>
                  <span className={c.solved ? "" : "line-through decoration-alert"}>{c.title}</span>
                  <span className="text-ink-soft text-xs">
                    {" "}
                    · {c.closedOn}
                    {c.daily && " · daily"}
                    {c.difficulty !== "normal" && ` · ${c.difficulty}`}
                  </span>
                </span>
                <span className="font-type text-sm tabular-nums">
                  {c.score} · {c.rank}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
      <p className="text-on-desk-soft mt-4 text-xs">Your casebook is kept for this browser.</p>
    </>
  );
}
