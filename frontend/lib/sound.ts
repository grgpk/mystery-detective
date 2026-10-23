// Synthesised with the Web Audio API: no audio files to load, and nothing plays before the first user gesture
// (browsers block audio until then; the context is created lazily on first use).

export type Cue = "clue" | "contradiction" | "solved" | "unsolved" | "key";

const MUTE_KEY = "last-alibi:muted";
const MASTER_VOLUME = 0.35;

let context: AudioContext | null = null;
let master: GainNode | null = null;
let muted = readMuted();
const listeners = new Set<(muted: boolean) => void>();

function readMuted(): boolean {
  try {
    return typeof window !== "undefined" && window.localStorage.getItem(MUTE_KEY) === "1";
  } catch {
    return false;
  }
}

export function isMuted(): boolean {
  return muted;
}

export function setMuted(value: boolean): void {
  muted = value;
  try {
    window.localStorage.setItem(MUTE_KEY, value ? "1" : "0");
  } catch {
    // Not persisted; the toggle still works for this visit.
  }
  listeners.forEach((listener) => listener(value));
}

export function subscribeMuted(listener: (muted: boolean) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function audio(): { ctx: AudioContext; out: GainNode } | null {
  if (typeof window === "undefined" || !("AudioContext" in window)) return null;
  if (!context) {
    context = new AudioContext();
    master = context.createGain();
    master.gain.value = MASTER_VOLUME;
    master.connect(context.destination);
  }
  if (context.state === "suspended") void context.resume();
  return { ctx: context, out: master! };
}

function tone(
  { ctx, out }: { ctx: AudioContext; out: GainNode },
  frequency: number,
  start: number,
  duration: number,
  { type = "sine", volume = 0.5 }: { type?: OscillatorType; volume?: number } = {},
) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = type;
  osc.frequency.value = frequency;
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  osc.connect(gain).connect(out);
  osc.start(start);
  osc.stop(start + duration + 0.05);
}

function click({ ctx, out }: { ctx: AudioContext; out: GainNode }, start: number) {
  // A short filtered noise burst: a typewriter key.
  const buffer = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.03), ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length) ** 3;
  const source = ctx.createBufferSource();
  const filter = ctx.createBiquadFilter();
  const gain = ctx.createGain();
  source.buffer = buffer;
  filter.type = "bandpass";
  filter.frequency.value = 2400 + Math.random() * 900;
  gain.gain.value = 0.25;
  source.connect(filter).connect(gain).connect(out);
  source.start(start);
}

export function play(cue: Cue): void {
  if (muted) return;
  const a = audio();
  if (!a) return;
  const t = a.ctx.currentTime + 0.01;
  switch (cue) {
    case "clue": // a bright two-note chime
      tone(a, 880, t, 0.5, { volume: 0.35 });
      tone(a, 1318.5, t + 0.12, 0.7, { volume: 0.3 });
      break;
    case "contradiction": // the "dun, dun, DUN" sting
      [196, 185, 155.6].forEach((f, i) => {
        tone(a, f, t + i * 0.22, i === 2 ? 1.4 : 0.25, { type: "sawtooth", volume: i === 2 ? 0.35 : 0.25 });
        tone(a, f / 2, t + i * 0.22, i === 2 ? 1.4 : 0.25, { type: "triangle", volume: 0.4 });
      });
      break;
    case "solved": // a rising major arpeggio
      [523.3, 659.3, 784, 1046.5].forEach((f, i) => tone(a, f, t + i * 0.13, 0.9, { type: "triangle", volume: 0.35 }));
      break;
    case "unsolved": // a falling minor line
      [440, 392, 349.2, 311.1].forEach((f, i) => tone(a, f, t + i * 0.2, 0.8, { type: "triangle", volume: 0.3 }));
      break;
    case "key":
      click(a, t);
      break;
  }
}
