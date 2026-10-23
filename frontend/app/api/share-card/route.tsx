import { ImageResponse } from "next/og";

import { fromSearchParams, headline } from "@/lib/share";

const PAPER = "#f2e8d5";
const INK = "#221c16";
const DESK = "#1c1814";
const STRING = "#b3201f";
const BRASS = "#c9a45c";

/** Fetches just the glyphs we need from Google Fonts; falls back to the default font if offline. */
async function typewriterFont(text: string): Promise<ArrayBuffer | null> {
  try {
    const css = await (
      await fetch(`https://fonts.googleapis.com/css2?family=Special+Elite&text=${encodeURIComponent(text)}`)
    ).text();
    const url = css.match(/src: url\((.+?)\) format\('(opentype|truetype)'\)/)?.[1];
    return url ? await (await fetch(url)).arrayBuffer() : null;
  } catch {
    return null;
  }
}

export async function GET(request: Request): Promise<Response> {
  const result = fromSearchParams(Object.fromEntries(new URL(request.url).searchParams));
  const title = result?.title ?? "The Last Alibi";
  const line = result ? headline(result) : "A new murder every time you press Play";
  const stamp = result ? (result.solved ? "SOLVED" : "UNSOLVED") : "CASE FILE";
  const score = result ? `${result.score} / 100` : "";
  const font = await typewriterFont(`THE LAST ALIBI${title}${line}${stamp}${score}0123456789/`);

  return new ImageResponse(
    (
      <div style={{ display: "flex", width: "100%", height: "100%", background: DESK, padding: 48 }}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
            width: "100%",
            height: "100%",
            background: PAPER,
            color: INK,
            padding: "52px 64px",
            borderLeft: `14px solid ${BRASS}`,
            fontFamily: font ? "Special Elite" : undefined,
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div style={{ fontSize: 30, letterSpacing: 10, color: "#5b4f43" }}>THE LAST ALIBI</div>
            <div
              style={{
                display: "flex",
                border: `6px solid ${result?.solved === false ? STRING : INK}`,
                color: result?.solved === false ? STRING : INK,
                padding: "6px 22px",
                fontSize: 40,
                transform: "rotate(-6deg)",
              }}
            >
              {stamp}
            </div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
            <div style={{ fontSize: 66, lineHeight: 1.1 }}>{title}</div>
            <div style={{ fontSize: 40, color: STRING }}>{line}</div>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 30, color: "#5b4f43" }}>
            <div>Can you do better?</div>
            <div>{score}</div>
          </div>
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      fonts: font ? [{ name: "Special Elite", data: font, weight: 400, style: "normal" }] : undefined,
      headers: { "Cache-Control": "public, max-age=86400, immutable" },
    },
  );
}
