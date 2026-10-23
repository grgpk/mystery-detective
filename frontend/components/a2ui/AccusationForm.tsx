"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import { useGame } from "@/lib/game-context";

const MAX_EVIDENCE = 3;

export function AccusationForm() {
  const { state, send, isRunning } = useGame();
  const [suspectId, setSuspectId] = useState("");
  const [motiveId, setMotiveId] = useState("");
  const [evidence, setEvidence] = useState<string[]>([]);
  if (!state) return null;

  const closed = state.phase === "ended";
  const toggle = (clueId: string) =>
    setEvidence((current) =>
      current.includes(clueId)
        ? current.filter((id) => id !== clueId)
        : current.length < MAX_EVIDENCE
          ? [...current, clueId]
          : current,
    );

  return (
    <form
      className="paper max-w-xl rounded-sm p-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (!suspectId || !motiveId) return;
        const name = state.suspects.find((s) => s.id === suspectId)?.name;
        void send({ type: "accuse", accusation: { suspectId, motiveId, evidence } }, `I accuse ${name}.`);
      }}
    >
      <h3 className="font-type mb-1 text-xl">The accusation</h3>
      <p className="text-ink-soft mb-4 text-sm">This ends the case. Choose carefully, Inspector.</p>

      <fieldset disabled={closed || isRunning} className="grid gap-4">
        <label className="grid gap-1 text-sm">
          <span className="font-type text-ink-soft text-xs uppercase">The killer</span>
          <select
            className="border-ink/30 rounded-sm border bg-white/60 p-2"
            value={suspectId}
            onChange={(e) => setSuspectId(e.target.value)}
            required
          >
            <option value="">Name the culprit…</option>
            {state.suspects.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}, {s.role}
              </option>
            ))}
          </select>
        </label>

        <fieldset className="grid gap-1 text-sm">
          <legend className="font-type text-ink-soft mb-1 text-xs uppercase">The motive</legend>
          {state.motiveOptions.map((m) => (
            <label key={m.id} className="flex items-center gap-2">
              <input
                type="radio"
                name="motive"
                value={m.id}
                checked={motiveId === m.id}
                onChange={() => setMotiveId(m.id)}
                required
              />
              {m.label}
            </label>
          ))}
        </fieldset>

        <fieldset className="grid gap-1 text-sm">
          <legend className="font-type text-ink-soft mb-1 text-xs uppercase">
            Key evidence ({evidence.length}/{MAX_EVIDENCE})
          </legend>
          {state.clues.length === 0 && <p className="text-ink-soft italic">You have found no physical evidence.</p>}
          {state.clues.map((c) => (
            <label key={c.id} className="flex items-start gap-2">
              <input
                type="checkbox"
                className="mt-1"
                checked={evidence.includes(c.id)}
                disabled={!evidence.includes(c.id) && evidence.length >= MAX_EVIDENCE}
                onChange={() => toggle(c.id)}
              />
              <span>
                <strong className="font-type font-normal">{c.title}</strong>
                <span className="text-ink-soft"> — {c.text}</span>
              </span>
            </label>
          ))}
        </fieldset>
      </fieldset>

      <Button type="submit" variant="danger" className="mt-5" disabled={closed || isRunning || !suspectId || !motiveId}>
        {closed ? "Case closed" : "Make the accusation"}
      </Button>
    </form>
  );
}
