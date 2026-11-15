interface KpiCardProps {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative" | "accent";
}

const TONES: Record<NonNullable<KpiCardProps["tone"]>, string> = {
  neutral: "text-fg",
  positive: "text-accent",
  negative: "text-danger",
  accent: "text-info",
};

export default function KpiCard({ label, value, hint, tone = "neutral" }: KpiCardProps) {
  return (
    <div className="card p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </p>
      <p className={`tnum mt-2 font-mono text-2xl font-semibold ${TONES[tone]}`}>{value}</p>
      {hint ? <p className="mt-1 text-[11px] leading-snug text-slate-500">{hint}</p> : null}
    </div>
  );
}
