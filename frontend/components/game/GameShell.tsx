"use client";

import { useState } from "react";

import { Surface } from "@/components/a2ui/catalog";
import { EvidenceBoard } from "@/components/board/EvidenceBoard";
import { Timeline } from "@/components/board/Timeline";
import { useGame } from "@/lib/game-context";
import { latestPanel } from "@/lib/protocol/transcript";
import { useUi, type MobileTab } from "@/lib/store";

import { ActionBar } from "./ActionBar";
import { InterrogationPanel } from "./InterrogationPanel";

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
  // On small screens only the selected tab's column shows; from lg up, all three do.
  const column = (tab: MobileTab) => (mobileTab === tab ? "flex" : "hidden lg:flex");

  return (
    <div className="mx-auto flex h-dvh max-w-[1500px] flex-col px-4 pt-3 pb-2">
      <header className="border-on-desk/15 mb-3 flex flex-wrap items-end justify-between gap-3 border-b pb-3">
        <div>
          <p className="font-type text-brass text-xs tracking-[0.35em] uppercase">The Last Alibi</p>
          <h1 className="font-type text-on-desk text-xl sm:text-2xl">{state?.title ?? "Opening the case file…"}</h1>
        </div>
        {!briefing && <ActionBar />}
      </header>

      {!state && !error && (
        <p className="text-on-desk-soft animate-pulse italic" role="status">
          The Inspector&apos;s train pulls into the station…
        </p>
      )}
      {!state && error && (
        <p className="text-string" role="alert">
          Could not reach the game server: {error}
        </p>
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
                className={`font-type flex-1 rounded-sm py-1.5 text-xs uppercase ${mobileTab === tab.id ? "bg-brass text-ink" : "bg-desk-raised text-on-desk-soft"}`}
              >
                {tab.label}
              </button>
            ))}
          </nav>

          <main className="grid min-h-0 flex-1 gap-5 lg:grid-cols-[290px_minmax(0,1fr)_380px]">
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
    </div>
  );
}
