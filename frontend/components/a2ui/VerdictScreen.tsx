"use client";

import { useState } from "react";

import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";

export function VerdictScreen() {
  const { state, newGame } = useGame();
  const [copied, setCopied] = useState(false);
  const verdict = state?.verdict;
  if (!state || !verdict) return null;
  const { score } = verdict;
  const nameOf = (id: string) => state.suspects.find((s) => s.id === id)?.name ?? id;
  const turnsUsed = state.maxTurns - state.turnsLeft;

  const share = async () => {
    const text = `The Last Alibi: "${state.title}" — ${score.culpritCorrect ? "Solved" : "Unsolved"} in ${turnsUsed} turns. ${score.rank} (${score.total}/100) 🕵️`;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };

  const rows: [string, number][] = [
    ["Culprit", score.culpritPoints],
    ["Motive", score.motivePoints],
    [`Key evidence (${score.validEvidence.length})`, score.evidencePoints],
    ["Turns to spare", score.turnPoints],
  ];

  return (
    <section className="paper rounded-sm p-5 sm:p-7" aria-labelledby="verdict-title">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-type text-ink-soft text-xs tracking-[0.3em] uppercase">Verdict</p>
          <h2 id="verdict-title" className="font-type text-3xl">
            {score.rank}
          </h2>
          <p className="text-ink-soft">
            It was <strong className="text-ink">{verdict.culpritName}</strong>. {verdict.motive}
          </p>
        </div>
        <Stamp tone={score.culpritCorrect ? "success" : "alert"}>{score.culpritCorrect ? "Solved" : "Wrong man"}</Stamp>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <table className="w-full text-sm">
          <caption className="font-type text-ink-soft mb-1 text-left text-xs uppercase">Score</caption>
          <tbody>
            {rows.map(([label, points]) => (
              <tr key={label} className="border-ink/10 border-b">
                <th scope="row" className="py-1 text-left font-normal">
                  {label}
                </th>
                <td className="py-1 text-right tabular-nums">{points}</td>
              </tr>
            ))}
            <tr>
              <th scope="row" className="font-type py-1 text-left">
                Total
              </th>
              <td className="font-type py-1 text-right tabular-nums">{score.total} / 100</td>
            </tr>
          </tbody>
        </table>

        <div>
          <h3 className="font-type text-ink-soft mb-1 text-xs uppercase">What really happened</h3>
          <ol className="grid gap-1 text-sm">
            {verdict.trueTimeline.map((e) => (
              <li key={`${e.time}-${e.event}`} className="grid grid-cols-[3.5rem_1fr] gap-2">
                <time className="font-type text-ink-soft">{e.time}</time>
                <span>
                  <strong className="font-normal">{nameOf(e.suspect)}:</strong> {e.event}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      {verdict.missedClues.length > 0 && (
        <div className="mt-5">
          <h3 className="font-type text-ink-soft mb-1 text-xs uppercase">Clues you missed</h3>
          <ul className="grid gap-1 text-sm">
            {verdict.missedClues.map((c) => (
              <li key={c.id}>
                <strong className="font-type font-normal">{c.title}:</strong> {c.text}
              </li>
            ))}
          </ul>
        </div>
      )}

      <footer className="mt-6 flex flex-wrap gap-2">
        <Button onClick={newGame}>Play again</Button>
        <Button variant="ghost" onClick={share}>
          {copied ? "Copied!" : "Share result"}
        </Button>
      </footer>
    </section>
  );
}
