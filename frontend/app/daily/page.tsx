import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { agentHeaders, agentUrl } from "@/lib/agent-server";
import type { DailyBoard } from "@/lib/protocol/types";

export const metadata: Metadata = {
  title: "Today's case · The Last Alibi",
  description: "One shared murder mystery a day, one attempt each. How do you rank?",
};

export default function DailyPage() {
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <p className="font-type text-brass text-xs tracking-[0.35em] uppercase">The Last Alibi</p>
      <Suspense fallback={<p className="text-on-desk-soft mt-4 italic">Pinning up today&apos;s standings…</p>}>
        <Board />
      </Suspense>
    </main>
  );
}

async function Board() {
  let board: DailyBoard;
  try {
    // Public standings: no session needed, so nothing personal is fetched here.
    const response = await fetch(agentUrl("/daily"), { cache: "no-store", headers: agentHeaders() });
    if (!response.ok) throw new Error(String(response.status));
    board = await response.json();
  } catch {
    return <p className="text-string mt-4">Today&apos;s case is unavailable right now.</p>;
  }
  const date = new Date(`${board.date}T00:00:00Z`).toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone: "UTC",
  });

  return (
    <>
      <h1 className="font-type text-on-desk text-3xl">Today&apos;s case</h1>
      <p className="text-on-desk-soft">{date}</p>

      <article className="paper animate-deal mt-5 rounded-sm p-5">
        <h2 className="font-type text-2xl">{board.case.title}</h2>
        <p className="text-ink-soft italic">{board.case.place}</p>
        <p className="mt-2">The same mystery for every detective today, one attempt each.</p>
        <Link
          href="/?daily=1"
          className="font-type bg-ink text-paper hover:bg-ink/85 mt-4 inline-block rounded-sm px-4 py-2 uppercase"
        >
          Play today&apos;s case
        </Link>
      </article>

      <section className="paper mt-6 rounded-sm p-5" aria-labelledby="standings">
        <h2 id="standings" className="font-type mb-3 text-lg">
          Standings{board.players > 0 && ` · ${board.players} detective${board.players === 1 ? "" : "s"}`}
        </h2>
        {board.leaderboard.length === 0 ? (
          <p className="italic">No one has closed today&apos;s case yet. Be the first.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="font-type text-ink-soft border-ink/20 border-b text-left text-xs uppercase">
                <th className="py-1 font-normal">#</th>
                <th className="py-1 font-normal">Detective</th>
                <th className="py-1 text-right font-normal">Score</th>
                <th className="py-1 text-right font-normal">Turns</th>
                <th className="hidden py-1 text-right font-normal sm:table-cell">Minutes</th>
              </tr>
            </thead>
            <tbody>
              {board.leaderboard.map((e) => (
                <tr key={e.rank} className="border-ink/10 border-b">
                  <td className="font-type py-1.5 tabular-nums">{e.rank}</td>
                  <td className="py-1.5">{e.name}</td>
                  <td className="py-1.5 text-right tabular-nums">{e.score}</td>
                  <td className="py-1.5 text-right tabular-nums">{e.turns}</td>
                  <td className="hidden py-1.5 text-right tabular-nums sm:table-cell">{e.minutes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="text-ink-soft mt-3 text-xs">Ranked by score, then fewest turns, then fastest.</p>
      </section>
    </>
  );
}
