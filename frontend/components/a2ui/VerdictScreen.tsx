"use client";

import Link from "next/link";
import { useState } from "react";

import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";
import { RANKS, headline, toSearchParams, type SharedResult } from "@/lib/share";
import { useUi } from "@/lib/store";

export function VerdictScreen() {
  const { state } = useGame();
  const openCasePicker = useUi((s) => s.setCasePickerOpen);
  const [copied, setCopied] = useState(false);
  const verdict = state?.verdict;
  if (!state || !verdict) return null;
  const { score } = verdict;
  const nameOf = (id: string) => state.suspects.find((s) => s.id === id)?.name ?? id;
  const turnsUsed = state.maxTurns - state.turnsLeft;

  const share = async () => {
    const result: SharedResult = {
      title: state.title,
      rank: RANKS.find((r) => r === score.rank) ?? "Rookie",
      score: score.total,
      turns: turnsUsed,
      solved: score.culpritCorrect,
    };
    const url = `${window.location.origin}/r?${toSearchParams(result)}`;
    const text = `The Last Alibi, "${state.title}": ${headline(result)} (${score.total}/100). Can you do better?`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "The Last Alibi", text, url });
        return;
      }
      await navigator.clipboard.writeText(`${text} ${url}`);
      setCopied(true);
    } catch {
      // Share sheet dismissed, or clipboard unavailable: nothing to do.
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

      {state.daily && <DailyEntry />}

      <footer className="mt-6 flex flex-wrap gap-2">
        <Button onClick={() => openCasePicker(true)}>Play again</Button>
        <Button variant="ghost" onClick={share}>
          {copied ? "Link copied!" : "Share result"}
        </Button>
      </footer>
    </section>
  );
}

/** For the daily case: put your name on today's leaderboard. */
// Mirrors the agent's rule (app/daily.py); the agent still decides, this just catches typos early.
const NAME_PATTERN = /^[\p{L}\p{N}_ .'-]{2,24}$/u;

function DailyEntry() {
  const { state, messages, send, isRunning, error } = useGame();
  const [name, setName] = useState("");
  const [submittedAt, setSubmittedAt] = useState<number | null>(null);
  const listed = state?.daily?.leaderboardName;
  const trimmed = name.trim().replace(/\s+/g, " ");
  const valid = NAME_PATTERN.test(trimmed);
  // A rejected name comes back as narration (it lands in the case log, behind this dialog): show it here.
  const rejection =
    submittedAt !== null && !isRunning && !listed
      ? messages
          .slice(submittedAt)
          .filter((m) => m.role === "assistant" && typeof m.content === "string" && m.content)
          .map((m) => m.content as string)
          .at(-1)
      : undefined;

  return (
    <section className="border-ink/20 mt-5 border-t pt-4" aria-labelledby="daily-entry">
      <h3 id="daily-entry" className="font-type text-ink-soft mb-2 text-xs uppercase">
        Today&apos;s leaderboard
      </h3>
      {listed ? (
        <p className="text-sm">
          You&apos;re on today&apos;s board as <strong>{listed}</strong>.{" "}
          <Link href="/daily" className="underline">
            See the standings
          </Link>
        </p>
      ) : (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!valid) return;
            setSubmittedAt(messages.length);
            void send({ type: "set_name", name: trimmed });
          }}
        >
          <label className="grid min-w-0 flex-1 gap-1 text-sm">
            <span>Sign the case file to join today&apos;s leaderboard</span>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={24}
              autoComplete="nickname"
              placeholder="Inspector …"
              className="border-ink/30 min-w-0 rounded-sm border bg-white/60 p-2"
            />
          </label>
          <Button type="submit" disabled={isRunning || !valid}>
            Sign
          </Button>
          {trimmed && !valid && (
            <p className="text-ink-soft w-full text-xs">2-24 letters, numbers, spaces or . &apos; -</p>
          )}
          {(rejection || error) && (
            <p className="text-alert w-full text-sm" role="alert">
              {rejection ?? error}
            </p>
          )}
        </form>
      )}
    </section>
  );
}
