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
