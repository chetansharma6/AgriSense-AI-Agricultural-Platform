import { factorLabel, formatWhole, limitedText } from "./format";
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

/** Describe supplied evidence without changing scores or implying missing evidence is positive. */
export function cropHighlights(crop: CropResult): { reason: string; consideration: string; firstStep: string; window: string } {
  const strongest = factors.map((key) => ({ key, score: crop.factors?.[key] }))
    .filter((item): item is { key: FactorKey; score: number } => item.score != null && Number.isFinite(item.score))
    .sort((a, b) => b.score - a.score)[0];
  const text = (value: string | null | undefined) => value?.trim() || undefined;
  return {
    reason: strongest ? `Highest available factor: ${factorLabel(strongest.key)} (${formatWhole(strongest.score)}/100).` : "Factor evidence is unavailable; the reason for this ranking cannot be explained yet.",
    consideration: crop.limited_by?.length ? limitedText(crop.limited_by) : text(crop.action_plan?.major_risk) ?? crop.risk_notes?.find((note) => note.trim()) ?? crop.flags?.find((flag) => flag.trim()) ?? "No specific risk information is available; confirm local requirements before planting.",
    firstStep: text(crop.action_plan?.first_test) ?? text(crop.action_plan?.check_before_planting) ?? "A crop-specific first step is unavailable. Review the growing plan and consult UF/IFAS Extension before planting.",
    window: text(crop.action_plan?.planting_window) ?? text(crop.season_label) ?? "Planting window unavailable; confirm timing with UF/IFAS Extension.",
  };
}

export function cropPlanUrl(crop: CropResult, lat: number, lon: number, acres?: number, place?: string): string | null {
  if (!crop.id) return null;
  const query = new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4) });
  if (acres !== undefined) query.set("acres", String(acres));
  if (place) query.set("place", place);
  if (crop.name) query.set("crop", crop.name);
  return `/crops/${encodeURIComponent(crop.id)}?${query}`;
}
