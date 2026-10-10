import { factorLabel, formatWhole } from "./format";
import type { CropResult, FactorKey } from "./types";

const factors: FactorKey[] = ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"];

export function placeLabel(place: string | null | undefined, county?: string | null): string {
  if (place?.trim()) {
    const label = place.trim().replace(/,\s*(?:FL|Florida)$/i, "");
    return /^Florida$/i.test(label) ? "Florida" : `${label}, Florida`;
  }
  return county ? `${county.replace(/\s+County$/i, "")} County, Florida` : "Florida";
}

/** Summarize existing factor scores; do not calculate or modify suitability. */
export function resultsSummary(crops: CropResult[]): string {
  const ranked = [...crops].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  const names = ranked.slice(0, 3).map((crop) => crop.name ?? "Unnamed crop").join(", ");
  const top = ranked.slice(0, 5);
  const counts = new Map<FactorKey, number>();
  for (const crop of top) {
    const available = factors.filter((key) => crop.factors?.[key] != null);
    const lowest = Math.min(...available.map((key) => crop.factors![key]!));
    for (const key of available) {
      if (crop.factors![key] === lowest) counts.set(key, (counts.get(key) ?? 0) + 1);
    }
  }
  const candidates = factors.filter((key) => counts.has(key)).map((key) => {
    const values = top.map((crop) => crop.factors?.[key]).filter((value): value is number => value != null);
    return { key, count: counts.get(key)!, average: values.reduce((a, b) => a + b, 0) / values.length };
  }).sort((a, b) => b.count - a.count || a.average - b.average);
  const limit = candidates[0];
  return `Best fits here: ${names || "no crop recommendations available"}. Main limit: ${limit
    ? `${factorLabel(limit.key)} (average factor score ${formatWhole(limit.average)}/100 across the top ${top.length})`
    : "factor data unavailable"}.`;
}
