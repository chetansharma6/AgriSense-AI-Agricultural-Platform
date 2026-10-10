import type { FactorKey, PriceRange, Yield } from "./types";

const factorLabels: Record<FactorKey, string> = {
  soil_ph: "Soil pH",
  drainage: "Drainage",
  season_temp: "Season temperature",
  frost_risk: "Frost risk",
  rainfall: "Rainfall",
  local_history: "Local track record",
};

export function factorLabel(key: FactorKey): string {
  return factorLabels[key];
}

export function scoreTone(
  score: number | null,
): "strong" | "fair" | "weak" | null {
  if (score === null) return null;
  if (score >= 75) return "strong";
  if (score >= 50) return "fair";
  return "weak";
}

export function describePh(ph: number | null): string {
  if (ph === null) return "No data";
  const description =
    ph < 5.5 ? "strongly acidic" :
    ph < 6.0 ? "moderately acidic" :
    ph < 6.5 ? "slightly acidic" :
    ph <= 7.3 ? "neutral" : "alkaline";
  return `${ph.toFixed(1)} — ${description}`;
}

const numberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

export function formatPrice(range: PriceRange | null): string {
  if (range === null || range.low === null || range.high === null || range.unit === null) {
    return "No data";
  }
  return `${numberFormat.format(range.low)}–${numberFormat.format(range.high)} ${range.unit}`;
}

export function formatYield(y: Yield | null): string {
  if (y === null || y.value === null || y.unit === null) return "No data";
  return `${numberFormat.format(y.value)} ${y.unit}`;
}

export function celsiusToF(c: number): number {
  return c * 9 / 5 + 32;
}

export function formatTemperature(c: number | null): string {
  if (c === null) return "No data";
  return `${c.toFixed(1)}°C / ${Math.round(celsiusToF(c))}°F`;
}

/** Null frost dates do not imply zero freeze risk. */
export function formatFrostDate(date: string | null): string {
  return date ?? "No data";
}

export function formatPercent(value: number | null): string {
  return value === null ? "No data" : `${numberFormat.format(value)}%`;
}

export function formatScore(score: number | null): string {
  return score === null ? "No data" : `${numberFormat.format(score)} / 100`;
}

const limitingLabels: Record<string, string> = {
  soil_ph: "soil pH",
  drainage: "drainage",
  season_temp: "season temperature",
  frost_risk: "freeze risk",
};

/** "Limited by freeze risk" style text for the factors that capped a score. */
export function limitedText(keys: string[]): string {
  return `Limited by ${keys.map((key) => limitingLabels[key] ?? key.replace(/_/g, " ")).join(", ")}`;
}
