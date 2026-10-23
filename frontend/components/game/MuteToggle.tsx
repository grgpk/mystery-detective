"use client";

import { useMuted } from "@/lib/use-game-cues";

export function MuteToggle() {
  const [muted, setMuted] = useMuted();
  return (
    <button
      type="button"
      onClick={() => setMuted(!muted)}
      aria-pressed={!muted}
      aria-label={muted ? "Sound off. Turn sound on" : "Sound on. Turn sound off"}
      title={muted ? "Sound off" : "Sound on"}
      className="border-on-desk/30 text-on-desk-soft hover:text-on-desk hover:bg-on-desk/10 grid h-8 w-8 place-items-center rounded-sm border"
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M4 9v6h4l5 4V5L8 9H4z" fill="currentColor" stroke="none" />
        {muted ? (
          <path d="M17 9l5 6M22 9l-5 6" strokeLinecap="round" />
        ) : (
          <path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12" strokeLinecap="round" />
        )}
      </svg>
    </button>
  );
}
