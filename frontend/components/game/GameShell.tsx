"use client";

import Link from "next/link";
import { useState } from "react";

import { Surface } from "@/components/a2ui/catalog";
import { EvidenceBoard } from "@/components/board/EvidenceBoard";
import { Timeline } from "@/components/board/Timeline";
import { useGame } from "@/lib/game-context";
import { latestPanel } from "@/lib/protocol/transcript";
import { useUi, type MobileTab } from "@/lib/store";

import { useGameCues } from "@/lib/use-game-cues";

import { ActionBar } from "./ActionBar";
import { CasePicker } from "./CasePicker";
import { InterrogationPanel } from "./InterrogationPanel";
import { MuteToggle } from "./MuteToggle";

function CasebookLink() {
  return (
    <Link
      href="/career"
      title="Your casebook"
      className="font-type border-on-desk/30 text-on-desk-soft hover:text-on-desk hover:bg-on-desk/10 grid h-8 place-items-center rounded-sm border px-2 text-xs uppercase"
    >
      Casebook
    </Link>
  );
}

const TABS: { id: MobileTab; label: string }[] = [
  { id: "suspects", label: "Suspects" },
  { id: "chat", label: "Case log" },
  { id: "board", label: "Board" },
];

export function GameShell() {
  const { state, messages, error } = useGame();
  const mobileTab = useUi((s) => s.mobileTab);
  const setMobileTab = useUi((s) => s.setMobileTab);

  const roster = latestPanel(messages, "roster");
  const map = latestPanel(messages, "map");
  const verdict = latestPanel(messages, "verdict");
  const [verdictClosed, setVerdictClosed] = useState(false);
  // The judge's reveal is the narration streamed right after the verdict surface.
  const reveal = verdict
    ? messages
        .slice(messages.indexOf(verdict) + 1)
        .filter((m) => m.role === "assistant" && typeof m.content === "string")
        .map((m) => m.content)
        .join("\n\n")
    : "";
  const briefing = state?.phase === "briefing";
  const flashKey = useGameCues(state);

  // Mobile tabs show a dot when something changed in a tab you are not looking at.
  const activity: Record<MobileTab, string> = {
    suspects: state ? state.suspects.map((s) => s.composure).join(",") : "",
    chat: String(messages.length),
    board: state ? `${state.clues.length}/${state.statements.length}/${state.timeline.length}` : "",
  };
  const [seen, setSeen] = useState<Record<MobileTab, string> | null>(null);
  if (state && (!seen || seen[mobileTab] !== activity[mobileTab])) {
    setSeen({ ...(seen ?? activity), [mobileTab]: activity[mobileTab] });
  }
  const unseen = (tab: MobileTab) => seen !== null && tab !== mobileTab && seen[tab] !== activity[tab];

  // On small screens only the selected tab's column shows; from lg up, all three do.
  const column = (tab: MobileTab) => (mobileTab === tab ? "flex" : "hidden lg:flex");

  return (
    <div className="mx-auto flex h-dvh max-w-[1500px] flex-col px-4 pt-3 pb-2">
      <header className="border-on-desk/15 mb-3 flex flex-wrap items-end justify-between gap-3 border-b pb-3">
        <div className="flex min-w-0 flex-1 items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-type text-brass text-xs tracking-[0.35em] uppercase">The Last Alibi</p>
            <h1 className="font-type text-on-desk text-xl sm:text-2xl">{state?.title ?? "Opening the case file…"}</h1>
          </div>
          <div className="flex gap-2 lg:hidden">
            <CasebookLink />
            <MuteToggle />
          </div>
        </div>
        <div className="flex items-center gap-3">
          {!briefing && <ActionBar />}
          <div className="hidden gap-2 lg:flex">
            <CasebookLink />
            <MuteToggle />
          </div>
        </div>
      </header>

      {flashKey > 0 && (
        <div
          key={flashKey}
          aria-hidden
          className="animate-contradiction pointer-events-none fixed inset-0 z-40 shadow-[inset_0_0_160px_40px_var(--string)]"
        />
      )}

      {!state && !error && (
        <p className="text-on-desk-soft animate-pulse italic" role="status">
          The Inspector&apos;s train pulls into the station…
        </p>
      )}
      {!state && error && (
        <div className="paper mx-auto mt-6 max-w-lg rounded-sm p-6" role="alert">
          <p className="font-type text-lg">The case file could not be opened</p>
          <p className="text-ink-soft mt-1">{error}</p>
        </div>
      )}

      {state && briefing && (
        <main className="min-h-0 flex-1 overflow-y-auto">
          <InterrogationPanel />
        </main>
      )}

      {state && !briefing && (
        <>
          <nav className="mb-3 flex gap-1 lg:hidden" aria-label="Sections">
            {TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setMobileTab(tab.id)}
                aria-current={mobileTab === tab.id ? "page" : undefined}
                className={`font-type relative flex-1 rounded-sm py-1.5 text-xs uppercase ${mobileTab === tab.id ? "bg-brass text-ink" : "bg-desk-raised text-on-desk-soft"}`}
              >
                {tab.label}
                {unseen(tab.id) && (
                  <>
                    <span className="bg-string absolute top-1 right-2 h-2 w-2 rounded-full" aria-hidden />
                    <span className="sr-only"> (new)</span>
                  </>
                )}
              </button>
            ))}
          </nav>

          <main className="grid min-h-0 flex-1 grid-cols-[minmax(0,1fr)] gap-5 lg:grid-cols-[290px_minmax(0,1fr)_380px]">
            <aside className={`${column("suspects")} min-h-0 flex-col gap-5 overflow-y-auto pr-1`}>
              {roster && <Surface message={roster} />}
              {map && <Surface message={map} />}
            </aside>

            <div className={`${column("chat")} min-h-0 flex-col`}>
              <InterrogationPanel />
            </div>

            <aside className={`${column("board")} min-h-0 flex-col gap-5 overflow-y-auto pr-1`}>
              <EvidenceBoard />
              <Timeline />
            </aside>
          </main>
        </>
      )}

      {verdict && state?.phase === "ended" && !verdictClosed && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="verdict-title"
          className="bg-desk/85 fixed inset-0 z-20 overflow-y-auto p-4 backdrop-blur-sm sm:p-10"
        >
          <div className="mx-auto grid max-w-3xl gap-4">
            <Surface message={verdict} />
            {reveal && (
              <article className="text-on-desk border-brass/50 border-l-2 pl-4 leading-relaxed whitespace-pre-line italic">
                {reveal}
              </article>
            )}
            <button
              type="button"
              onClick={() => setVerdictClosed(true)}
              className="font-type text-on-desk-soft hover:text-on-desk justify-self-center text-sm uppercase underline"
            >
              Close the file and review the board
            </button>
          </div>
        </div>
      )}
      <CasePicker />
    </div>
  );
}
