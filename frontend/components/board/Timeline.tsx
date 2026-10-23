"use client";

import { useGame } from "@/lib/game-context";

export function Timeline() {
  const { state } = useGame();
  if (!state) return null;
  const lanes = state.suspects
    .map((s) => ({ suspect: s, events: state.timeline.filter((e) => e.suspect === s.id) }))
    .filter((lane) => lane.events.length > 0);

  return (
    <section aria-labelledby="timeline-heading">
      <h2 id="timeline-heading" className="font-type text-on-desk-soft mb-2 text-sm tracking-[0.2em] uppercase">
        Timeline
      </h2>
      {lanes.length === 0 ? (
        <p className="text-on-desk-soft text-sm italic">Accounts of the evening will appear here.</p>
      ) : (
        <ul className="grid gap-3">
          {lanes.map(({ suspect, events }) => (
            <li key={suspect.id}>
              <p className="font-type text-on-desk text-xs uppercase">{suspect.name}</p>
              <ol className="border-on-desk/20 ml-1 border-l pl-3 text-sm">
                {events.map((e) => (
                  <li key={`${e.time}-${e.event}`} className="relative py-0.5">
                    <span
                      className={`absolute top-2 -left-[17px] h-2 w-2 rounded-full ${e.source === "verified" ? "bg-brass" : "border-on-desk-soft border bg-transparent"}`}
                      aria-hidden
                    />
                    <time className="font-type text-on-desk-soft mr-2">{e.time}</time>
                    <span className={e.source === "verified" ? "text-on-desk" : "text-on-desk-soft italic"}>
                      {e.event}
                    </span>
                    <span className="sr-only">({e.source})</span>
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ul>
      )}
      <p className="text-on-desk-soft mt-2 text-xs">
        <span className="bg-brass mr-1 inline-block h-2 w-2 rounded-full" aria-hidden /> verified
        <span className="border-on-desk-soft mr-1 ml-3 inline-block h-2 w-2 rounded-full border" aria-hidden /> claimed
      </p>
    </section>
  );
}
