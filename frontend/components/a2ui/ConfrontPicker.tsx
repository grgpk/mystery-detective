"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import { useGame } from "@/lib/game-context";

export function ConfrontPicker({ suspectId }: { suspectId: string }) {
  const { state, send, isRunning } = useGame();
  const [statementId, setStatementId] = useState("");
  const [evidenceId, setEvidenceId] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const suspect = state?.suspects.find((s) => s.id === suspectId);
  if (!state || !suspect) return null;

  const nameOf = (id: string) => state.suspects.find((s) => s.id === id)?.name ?? id;
  // Their own words first: that's where a lie can be broken.
  const statements = [...state.statements].sort(
    (a, b) => Number(b.suspect === suspectId) - Number(a.suspect === suspectId),
  );
  const canSubmit = statementId && evidenceId && statementId !== evidenceId && !isRunning && !submitted;
  const closed = submitted || state.phase !== "investigating";

  return (
    <form
      className="paper max-w-xl rounded-sm p-4"
      onSubmit={(event) => {
        event.preventDefault();
        if (!canSubmit) return;
        setSubmitted(true);
        void send(
          { type: "confront", suspectId, items: [statementId, evidenceId] },
          `I confront ${suspect.name}.`,
        );
      }}
    >
      <h3 className="font-type mb-3 text-lg">Confront {suspect.name}</h3>
      <fieldset disabled={closed} className="grid min-w-0 gap-3 sm:grid-cols-2">
        <label className="grid min-w-0 gap-1 text-sm">
          <span className="font-type text-ink-soft text-xs uppercase">The statement</span>
          <select
            className="border-ink/30 w-full min-w-0 rounded-sm border bg-white/60 p-2"
            value={statementId}
            onChange={(e) => setStatementId(e.target.value)}
            required
          >
            <option value="">Choose a statement…</option>
            {statements.map((st) => (
              <option key={st.id} value={st.id}>
                {nameOf(st.suspect)}: “{st.text}”
              </option>
            ))}
          </select>
        </label>
        <label className="grid min-w-0 gap-1 text-sm">
          <span className="font-type text-ink-soft text-xs uppercase">Against</span>
          <select
            className="border-ink/30 w-full min-w-0 rounded-sm border bg-white/60 p-2"
            value={evidenceId}
            onChange={(e) => setEvidenceId(e.target.value)}
            required
          >
            <option value="">Choose evidence or a statement…</option>
            <optgroup label="Clues">
              {state.clues.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </optgroup>
            <optgroup label="Statements">
              {statements
                .filter((st) => st.id !== statementId)
                .map((st) => (
                  <option key={st.id} value={st.id}>
                    {nameOf(st.suspect)}: “{st.text}”
                  </option>
                ))}
            </optgroup>
          </select>
        </label>
      </fieldset>
      <p className="text-ink-soft mt-3 text-xs">Costs one turn. If they don&apos;t truly contradict, the suspect will shrug it off.</p>
      <Button type="submit" variant="danger" className="mt-3" disabled={!canSubmit}>
        {submitted ? "Presented" : "Confront"}
      </Button>
    </form>
  );
}
