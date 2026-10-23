"use client";

import { useEffect, useRef, useState } from "react";

import { play } from "@/lib/sound";

const CHARS_PER_TICK = 2;
const TICK_MS = 28;
const CLICK_EVERY = 6; // characters between key sounds

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Types text out like a typewriter; click or press a key to finish at once. Screen readers get the full text
 * immediately, and reduced-motion users never see the animation.
 */
export function Typewriter({ text, className = "" }: { text: string; className?: string }) {
  const [shown, setShown] = useState(() => (prefersReducedMotion() ? text.length : 0));
  const progress = useRef(shown);
  const done = shown >= text.length;

  useEffect(() => {
    if (done) return;
    const finish = () => {
      progress.current = text.length;
      setShown(text.length);
    };
    const timer = setInterval(() => {
      const before = progress.current;
      const next = Math.min(text.length, before + CHARS_PER_TICK);
      progress.current = next;
      setShown(next);
      if (Math.floor(next / CLICK_EVERY) > Math.floor(before / CLICK_EVERY) && /\S/.test(text[next - 1] ?? "")) {
        play("key");
      }
    }, TICK_MS);
    window.addEventListener("keydown", finish, { once: true });
    return () => {
      clearInterval(timer);
      window.removeEventListener("keydown", finish);
    };
  }, [done, text]);

  return (
    <p
      className={className}
      onClick={() => {
        progress.current = text.length;
        setShown(text.length);
      }}
    >
      <span className="sr-only">{text}</span>
      <span aria-hidden>
        {text.slice(0, shown)}
        {!done && <span className="animate-caret ml-px inline-block h-[1em] w-[2px] translate-y-[2px] bg-current" />}
        {/* Reserve the final height so the card doesn't grow while typing. */}
        <span className="invisible">{text.slice(shown)}</span>
      </span>
    </p>
  );
}
