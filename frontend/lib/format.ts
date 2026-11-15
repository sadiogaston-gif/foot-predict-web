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
  return value.slice(0, 5);
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
