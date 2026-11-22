/** Helpers de formatage (français). */

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  weekday: "short",
  day: "2-digit",
  month: "short",
});

const longDateFormatter = new Intl.DateTimeFormat("fr-FR", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

export function formatDate(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return dateFormatter.format(parsed).replace(".", "");
}

export function formatLongDate(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(`${value}T12:00:00`);
  if (Number.isNaN(parsed.getTime())) return value;
  return longDateFormatter.format(parsed);
}

export function formatTime(value?: string | null): string {
  if (!value) return "—";
  // L'heure provient du backend au format "HH:MM" (heure du Royaume-Uni / GMT).
  // On interprète comme UTC et on convertit vers le fuseau local du navigateur
  // afin d'afficher l'heure correcte (ex: 23h à Paris au lieu de 22h GMT).
  const parsed = new Date(`1970-01-01T${value.slice(0, 5)}:00Z`);
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 5);
  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsed);
}

/**
 * Heure du coupon convertie vers le fuseau du navigateur.
 *
 * Le backend fournit désormais `kickoff_utc` (ISO 8601 avec fuseau, ex.
 * `2026-11-20T19:30:00Z`) — instant exact issu de The Odds API quand disponible.
 * Quand ce champ est absent (ancien cache), on reconstruit l'instant depuis
 * `date` + `time` interprétés dans Europe/Paris (fuseau d'affichage du pipeline).
 */
const PARIS_TZ = "Europe/Paris";

function zonedOffsetMs(instant: Date, timeZone: string): number {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const value = (type: string) => Number(parts.find((p) => p.type === type)?.value || 0);
  const asUtc = Date.UTC(
    value("year"),
    value("month") - 1,
    value("day"),
    value("hour") % 24,
    value("minute"),
    value("second"),
  );
  return asUtc - Math.floor(instant.getTime() / 1000) * 1000;
}

export function formatKickoffTime(
  date?: string | null,
  time?: string | null,
  kickoffUtc?: string | null,
): string {
  // 1) Instant exact fourni par le backend (ISO avec fuseau)
  if (kickoffUtc) {
    const instant = new Date(kickoffUtc);
    if (!Number.isNaN(instant.getTime())) {
      return new Intl.DateTimeFormat("fr-FR", {
        hour: "2-digit",
        minute: "2-digit",
      }).format(instant);
    }
  }

  // 2) Repli depuis date + time (fuseau Paris)
  if (!date || !time || !time.includes(":")) return formatTime(time);
  const [hh, mm] = time.slice(0, 5).split(":").map(Number);
  if (!Number.isFinite(hh) || !Number.isFinite(mm)) return formatTime(time);

  const y = Number(date.slice(0, 4));
  const mo = Number(date.slice(5, 7)) - 1;
  const d = Number(date.slice(8, 10));
  if (!Number.isFinite(y) || !Number.isFinite(mo) || !Number.isFinite(d)) {
    return formatTime(time);
  }

  // Heure "naïve" (telle qu'affichée à Paris) interprétée comme UTC.
  let naive = Date.UTC(y, mo, d, hh, mm, 0);
  // Deux passes : l'offset d'été/hiver dépend de l'instant, on converge vite.
  for (let i = 0; i < 2; i += 1) {
    naive = Date.UTC(y, mo, d, hh, mm, 0) - zonedOffsetMs(new Date(naive), PARIS_TZ);
  }

  return new Intl.DateTimeFormat("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(naive));
}

export function pct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value.toFixed(digits)}%`;
}

export function signedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

export function odds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(2);
}

export function units(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} u`;
}

export function resultLabel(result: "W" | "D" | "L"): string {
  return result === "W" ? "V" : result === "D" ? "N" : "D";
}
