const TONES = {
  neutral: "border-brass text-on-desk",
  alert: "border-string text-on-desk",
  success: "border-success text-on-desk",
} as const;

export function NarrationBlock({
  title,
  text,
  tone = "neutral",
}: {
  title?: string;
  text: string;
  tone?: keyof typeof TONES;
}) {
  return (
    <aside className={`border-y-2 py-3 text-center ${TONES[tone]}`} role={tone === "alert" ? "alert" : undefined}>
      {title && (
        <p className={`font-type text-lg tracking-[0.25em] uppercase ${tone === "alert" ? "text-string" : ""}`}>
          {title}
        </p>
      )}
      <p className="text-on-desk-soft italic">{text}</p>
    </aside>
  );
}
