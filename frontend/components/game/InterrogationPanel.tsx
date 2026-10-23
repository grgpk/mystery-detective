"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { Surface } from "@/components/a2ui/catalog";
import { Button } from "@/components/ui";
import { useGame } from "@/lib/game-context";
import { buildTranscript, type TranscriptEntry } from "@/lib/protocol/transcript";
import type { Option, PublicState } from "@/lib/protocol/types";
import { useUi } from "@/lib/store";

const MAX_QUESTION = 500;

function suggestedQuestion(topic: Option): string {
  return topic.label.endsWith("?") ? topic.label : `What can you tell me about ${topic.label.toLowerCase()}?`;
}

function Entry({ entry, state }: { entry: TranscriptEntry; state: PublicState | null }) {
  switch (entry.kind) {
    case "surface":
      return <Surface message={entry.message} />;
    case "player":
      return (
        <p className="text-on-desk-soft ml-auto max-w-[85%] text-right italic">
          <span className="font-type text-brass mr-2 text-xs not-italic uppercase">You</span>
          {entry.text}
        </p>
      );
    case "speech": {
      const suspect = state?.suspects.find((s) => s.id === entry.speaker);
      if (!suspect) return <p className="text-on-desk border-brass/40 border-l-2 pl-3 italic">{entry.text}</p>;
      return (
        <figure className="paper max-w-[85%] rounded-sm p-3">
          <figcaption className="font-type text-ink-soft mb-1 text-xs uppercase">{suspect.name}</figcaption>
          <blockquote className="leading-relaxed">“{entry.text.trim()}”</blockquote>
        </figure>
      );
    }
  }
}

export function InterrogationPanel() {
  const { state, messages, send, isRunning, error } = useGame();
  const activeSuspectId = useUi((s) => s.activeSuspectId);
  const [question, setQuestion] = useState("");
  const logEnd = useRef<HTMLDivElement>(null);
  const entries = useMemo(() => buildTranscript(messages), [messages]);
  const lastText = entries.at(-1)?.kind === "speech" ? (entries.at(-1) as { text: string }).text : "";

  useEffect(() => {
    logEnd.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [entries.length, lastText]);

  const suspect = state?.suspects.find((s) => s.id === activeSuspectId);
  const investigating = state?.phase === "investigating";
  const conversation = state?.conversation;
  const questionsLeft = conversation && conversation.suspectId === activeSuspectId ? conversation.questionsLeft : 0;

  const ask = (text: string) => {
    const trimmed = text.trim();
    if (!suspect || !trimmed || isRunning) return;
    setQuestion("");
    void send({ type: "interrogate", suspectId: suspect.id, question: trimmed }, `${suspect.name}, ${trimmed}`);
  };

  return (
    <section className="flex h-full min-h-0 flex-col" aria-label="Case log">
      <div className="min-h-0 flex-1 overflow-y-auto pr-1" aria-live="polite">
        <ol className="flex flex-col gap-4 pb-4">
          {entries.map((entry) => (
            <li key={entry.id} className="flex flex-col">
              <Entry entry={entry} state={state} />
            </li>
          ))}
        </ol>
        {isRunning && (
          <p className="text-on-desk-soft animate-pulse text-sm italic" role="status">
            {suspect ? `${suspect.name} considers the question…` : "The fog shifts…"}
          </p>
        )}
        {error && (
          <p className="text-string text-sm" role="alert">
            {error}
          </p>
        )}
        <div ref={logEnd} />
      </div>

      {investigating && (
        <form
          className="border-on-desk/15 mt-2 border-t pt-3"
          onSubmit={(event) => {
            event.preventDefault();
            ask(question);
          }}
        >
          {suspect ? (
            <>
              <p className="text-on-desk-soft mb-2 text-xs">
                Questioning <strong className="text-on-desk">{suspect.name}</strong> ·{" "}
                {questionsLeft > 0
                  ? `${questionsLeft} question${questionsLeft === 1 ? "" : "s"} left this turn`
                  : "next question starts a new turn (3 questions per turn)"}
              </p>
              <div className="mb-2 flex flex-wrap gap-1.5">
                {state?.topics.map((topic) => (
                  <button
                    key={topic.id}
                    type="button"
                    disabled={isRunning}
                    onClick={() => ask(suggestedQuestion(topic))}
                    className="border-on-desk/25 text-on-desk-soft hover:border-brass hover:text-on-desk rounded-full border px-2.5 py-0.5 text-xs transition-colors disabled:opacity-40"
                  >
                    {topic.label}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <label className="sr-only" htmlFor="question">
                  Your question for {suspect.name}
                </label>
                <input
                  id="question"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  maxLength={MAX_QUESTION}
                  autoComplete="off"
                  placeholder={`Ask ${suspect.name.split(" ").at(-1)} anything…`}
                  className="bg-desk-raised text-on-desk placeholder:text-on-desk-soft/60 border-on-desk/20 focus:border-brass min-w-0 flex-1 rounded-sm border px-3 py-2"
                />
                <Button type="submit" variant="accent" disabled={isRunning || !question.trim()}>
                  Ask
                </Button>
              </div>
            </>
          ) : (
            <p className="text-on-desk-soft text-sm italic">Choose a suspect to interrogate, or examine a room.</p>
          )}
        </form>
      )}
    </section>
  );
}
