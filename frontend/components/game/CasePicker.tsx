"use client";

import { useEffect, useRef, useState } from "react";

import { Button, Stamp } from "@/components/ui";
import { useGame } from "@/lib/game-context";
import Link from "next/link";

import { DAILY_CASE_ID, NEW_CASE_ID, type CaseCatalogue, type DailyBoard } from "@/lib/protocol/types";
import { useUi } from "@/lib/store";

export function CasePicker() {
  const { state, newGame, resumeGame } = useGame();
  const open = useUi((s) => s.casePickerOpen);
  const setOpen = useUi((s) => s.setCasePickerOpen);
  const dialog = useRef<HTMLDialogElement>(null);
  const [catalogue, setCatalogue] = useState<CaseCatalogue | null>(null);
  const [daily, setDaily] = useState<DailyBoard | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    if (open && !element.open) element.showModal();
    if (!open && element.open) element.close();
  }, [open]);

  // Refetch on every open: the generated-case pool fills and drains between visits.
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    fetch("/api/cases")
      .then((response) => (response.ok ? response.json() : Promise.reject(new Error(String(response.status)))))
      .then((data: CaseCatalogue) => !cancelled && setCatalogue(data))
      .catch(() => !cancelled && setError("The case archive is unreachable. Try again in a moment."));
    fetch("/api/daily")
      .then((response) => (response.ok ? response.json() : null))
      .then((data: DailyBoard | null) => !cancelled && setDaily(data))
      .catch(() => undefined); // the daily card just doesn't show
    return () => {
      cancelled = true;
    };
  }, [open]);

  const cases = catalogue?.cases ?? null;
  const fresh = catalogue?.fresh;

  const currentCaseId = state?.caseId;
  const inProgress = state?.phase === "investigating" || state?.phase === "accusing";

  const start = (caseId?: string) => {
    setOpen(false);
    newGame(caseId);
  };

  const surprise = () => {
    // Prefer a case other than the one just played; fall back to any.
    const others = (cases ?? []).filter((c) => c.caseId !== currentCaseId);
    const pool = others.length ? others : (cases ?? []);
    start(pool.length ? pool[Math.floor(Math.random() * pool.length)].caseId : undefined);
  };

  return (
    <dialog
      ref={dialog}
      onClose={() => setOpen(false)}
      aria-labelledby="case-picker-title"
      className="paper m-auto w-[min(42rem,calc(100vw-2rem))] rounded-sm p-0 backdrop:bg-black/70"
    >
      <div className="p-5 sm:p-7">
        <header className="mb-4 flex items-start justify-between gap-3">
          <div>
            <p className="font-type text-ink-soft text-xs tracking-[0.3em] uppercase">Case files</p>
            <h2 id="case-picker-title" className="font-type text-2xl">
              Choose your next case
            </h2>
          </div>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="text-ink-soft hover:text-ink px-2 text-2xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </header>

        {inProgress && (
          <p className="text-alert mb-4 text-sm">Starting a new case abandons the one you are working on.</p>
        )}

        {error && (
          <p className="text-alert text-sm" role="alert">
            {error}
          </p>
        )}
        {open && !cases && !error && (
          <p className="text-ink-soft animate-pulse italic" role="status">
            Fetching the files from the archive…
          </p>
        )}

        {daily && (
          <div className="border-brass bg-paper-shade/40 mb-3 grid gap-1 rounded-sm border-2 p-3">
            <span className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-type text-lg">Today&apos;s case: {daily.case.title}</span>
              <Stamp tone={daily.you?.phase === "ended" ? "success" : "ink"}>
                {daily.you?.phase === "ended" ? "Played" : daily.date}
              </Stamp>
            </span>
            <span className="text-sm">
              The same mystery for every detective today, one attempt each.{" "}
              {daily.players > 0 &&
                `${daily.players} detective${daily.players === 1 ? " has" : "s have"} closed it so far.`}
            </span>
            {daily.you?.phase === "ended" && (
              <span className="text-ink-soft text-sm">
                You scored {daily.you.score}
                {daily.you.rank && `, rank ${daily.you.rank} of ${daily.players}`}.
              </span>
            )}
            <span className="mt-1 flex flex-wrap gap-2">
              {daily.you ? (
                <Button
                  onClick={() => {
                    setOpen(false);
                    resumeGame(daily.you!.threadId);
                  }}
                >
                  {daily.you.phase === "ended" ? "See your verdict" : "Continue today's case"}
                </Button>
              ) : (
                <Button onClick={() => start(DAILY_CASE_ID)}>Play today&apos;s case</Button>
              )}
              <Link
                href="/daily"
                className="font-type border-ink/30 hover:bg-ink/10 rounded-sm border px-3 py-1.5 text-sm uppercase"
              >
                Leaderboard
              </Link>
            </span>
          </div>
        )}

        {fresh?.enabled && (
          <button
            type="button"
            onClick={() => start(NEW_CASE_ID)}
            className="border-string/60 hover:border-string hover:bg-paper-shade/60 mb-3 grid w-full gap-1 rounded-sm border-2 border-dashed p-3 text-left transition-colors"
          >
            <span className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="font-type text-lg">A brand-new mystery</span>
              <Stamp tone={fresh.ready > 0 ? "success" : "ink"}>
                {fresh.ready > 0 ? `${fresh.ready} ready` : fresh.generating ? "Being written" : "None ready"}
              </Stamp>
            </span>
            <span className="text-sm">
              A case nobody has played before, written for you and checked for fair play before it reaches you.
            </span>
            {fresh.ready === 0 && (
              <span className="text-ink-soft text-xs italic">
                None is ready yet; you will get a case from the archive while the next one is written.
              </span>
            )}
          </button>
        )}

        {cases && (
          <ul className="grid gap-3">
            {cases.map((c) => (
              <li key={c.caseId}>
                <button
                  type="button"
                  onClick={() => start(c.caseId)}
                  className="border-ink/20 hover:border-ink hover:bg-paper-shade/60 grid w-full gap-1 rounded-sm border p-3 text-left transition-colors"
                >
                  <span className="flex flex-wrap items-baseline justify-between gap-2">
                    <span className="font-type text-lg">{c.title}</span>
                    {c.caseId === currentCaseId && <Stamp>Current case</Stamp>}
                  </span>
                  <span className="text-ink-soft text-sm italic">{c.place}</span>
                  <span className="text-sm">{c.blurb}</span>
                  <span className="text-ink-soft text-xs">{c.suspects} suspects</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <footer className="mt-5 flex flex-wrap gap-2">
          <Button onClick={surprise} disabled={!cases}>
            Surprise me
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </footer>
      </div>
    </dialog>
  );
}
