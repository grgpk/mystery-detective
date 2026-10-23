"use client";

import dynamic from "next/dynamic";

// The game reads browser-only state (thread id in localStorage), so it renders on the client only.
const GameApp = dynamic(() => import("./GameApp"), {
  ssr: false,
  loading: () => (
    <p className="text-on-desk-soft p-6 italic" role="status">
      Opening the case file…
    </p>
  ),
});

export function ClientGame() {
  return <GameApp />;
}
