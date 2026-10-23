import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "ghost" | "danger" | "desk" | "brass" | "accent";

// One variant per surface: ink-on-paper styles for cards, on-desk styles for the dark background.
// Never override a variant's colours with className; two text colours on one element resolve unpredictably.
const VARIANTS: Record<Variant, string> = {
  primary: "bg-ink text-paper hover:bg-ink/85",
  ghost: "border border-ink/30 text-ink hover:bg-ink/10",
  danger: "bg-string text-paper hover:bg-string/85",
  desk: "border border-on-desk/30 text-on-desk-soft hover:bg-on-desk/10 hover:text-on-desk",
  brass: "border border-brass/60 text-brass hover:bg-brass/10",
  accent: "bg-brass text-ink hover:bg-brass/85",
};

export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      className={`font-type rounded-sm px-3 py-1.5 text-sm tracking-wide uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${VARIANTS[variant]} ${className}`}
      {...props}
    />
  );
}

export function Stamp({ children, tone = "ink" }: { children: ReactNode; tone?: "ink" | "alert" | "success" }) {
  const colors = { ink: "border-ink-soft text-ink-soft", alert: "border-alert text-alert", success: "border-success text-success" };
  return (
    <span className={`font-type inline-block -rotate-2 rounded-sm border-2 px-1.5 text-xs uppercase ${colors[tone]}`}>
      {children}
    </span>
  );
}

export function PanelHeading({ children }: { children: ReactNode }) {
  return <h2 className="font-type text-on-desk-soft mb-3 text-sm tracking-[0.2em] uppercase">{children}</h2>;
}
