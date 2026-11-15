import { signedPct } from "@/lib/format";

interface ValueBadgeProps {
  ev: number;
  label?: string;
  size?: "sm" | "md";
}

/**
 * Badge « VALUE +X% » : vert lumineux, uniquement quand EV > seuil.
 * Le libellé du marché est optionnel (affiché sur les cartes de match).
 */
export default function ValueBadge({ ev, label, size = "md" }: ValueBadgeProps) {
  const dimensions =
    size === "sm"
      ? "px-2 py-0.5 text-[10px] gap-1"
      : "px-2.5 py-1 text-[11px] gap-1.5";

  return (
    <span
      className={`inline-flex items-center rounded-md border border-accent/50 bg-accent/10 font-mono font-semibold uppercase tracking-wide text-accent shadow-glow ${dimensions}`}
      title={label ? `Value bet : ${label}` : "Value bet détecté"}
    >
      <span className="relative flex h-1.5 w-1.5">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
        <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-accent" />
      </span>
      Value {signedPct(ev)}
      {label ? <span className="normal-case tracking-normal text-accent/80">· {label}</span> : null}
    </span>
  );
}
