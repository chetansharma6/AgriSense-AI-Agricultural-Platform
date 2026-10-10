import type { FactorDetail, FactorKey, PriceRange, Yield } from "./types";

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
  const unit = range.unit.replace(/\$|USD/gi, "").replace(/^\s*(?:\/|per)\s*/i, "").trim().toLowerCase();
  return `$${range.low.toFixed(2)}–$${range.high.toFixed(2)} per ${unit}`;
}

export function formatYield(y: Yield | null): string {
  if (y === null || y.value === null || y.unit === null) return "No data";
  return `${formatWhole(y.value)} ${y.unit.toLowerCase().replace(/\s*\/\s*/g, "/")}`;
}

export function celsiusToF(c: number): number {
  return c * 9 / 5 + 32;
}

export function formatTemperature(c: number | null): string {
  if (c === null) return "No data";
  return `${c.toFixed(1)}°C (${Math.round(celsiusToF(c))}°F)`.replace(/-/g, "−");
}

/** Null frost dates do not imply zero freeze risk. */
export function formatFrostDate(date: string | null): string {
  if (!date) return "No data";
  const match = /^(\d{2})-(\d{2})$/.exec(date);
  if (!match) return date;
  const month = Number(match[1]);
  const day = Number(match[2]);
  const parsed = new Date(Date.UTC(2000, month - 1, day));
  if (parsed.getUTCMonth() !== month - 1 || parsed.getUTCDate() !== day) return "No data";
  return new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(parsed);
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


export function formatWhole(value: number | null): string {
  return value === null || !Number.isFinite(value) ? "No data" : Math.round(value).toLocaleString("en-US");
}

export function formatDays(value: number | null): string {
  return value === null ? "No data" : `${formatWhole(value)} days`;
}

export function formatMillimeters(value: number | null): string {
  return value === null ? "No data" : `${formatWhole(value)} mm`;
}

/** Format API prose for display only; never alter the data used for scoring. */
export function formatDisplayText(text: string): string {
  return text
    .replace(/\$?([\d,]+(?:\.\d+)?)\s*[–-]\s*\$?([\d,]+(?:\.\d+)?)\s*(?:\$\s*\/|per)\s*(cwt|lbs?|bu|tons?)\b/gi,
      (_, low: string, high: string, unit: string) => formatPrice({ low: Number(low.replace(/,/g, "")), high: Number(high.replace(/,/g, "")), unit }))
    .replace(/\$([\d,]+(?:\.\d+)?)\s*(?:\/|per)\s*(cwt|lbs?|bu|tons?)\b/gi,
      (_, value: string, unit: string) => `$${Number(value.replace(/,/g, "")).toFixed(2)} per ${unit.toLowerCase()}`)
    .replace(/([\d,]+(?:\.\d+)?)\s*(cwt|lbs?|bu|tons?)\s*\/\s*acre\b/gi,
      (_, value: string, unit: string) => `${formatWhole(Number(value.replace(/,/g, "")))} ${unit.toLowerCase()}/acre`)
    .replace(/\$\s*\/\s*(cwt|lbs?|bu|tons?)\b/gi, (_, unit: string) => `per ${unit.toLowerCase()}`)
    .replace(/\bper\s+(CWT|LBS?|BU|TONS?)\b/g, (_, unit: string) => `per ${unit.toLowerCase()}`)
    .replace(/crop tolerates about 0(?:\.0+)?(?![\d.])/gi, "this crop doesn't tolerate frost")
    .replace(/([−-]?\d+(?:\.\d+)?)\s*[–-]\s*([−-]?\d+(?:\.\d+)?)\s*°?\s*C\b(?!\s*\([^)]*°F\))/g,
      (_, low: string, high: string) => {
        const a = Number(low.replace("−", "-"));
        const b = Number(high.replace("−", "-"));
        return `${a.toFixed(1)}–${b.toFixed(1)}°C (${Math.round(celsiusToF(a))}–${Math.round(celsiusToF(b))}°F)`.replace(/-(?=\d)/g, "−");
      })
    .replace(/([−-]?\d+(?:\.\d+)?)\s*°?\s*C\b(?!\s*\([^)]*°F\))/g, (_, c: string) => formatTemperature(Number(c.replace("−", "-"))))
    .replace(/([\d,]+(?:\.\d+)?)\s+(days?|freezing nights|acres|mm)\b/gi, (_, value: string, unit: string) => `${formatWhole(Number(value.replace(/,/g, "")))} ${unit.toLowerCase()}`)
    .replace(/(\d+\.\d+) of them hard/gi, (_, value: string) => `${formatWhole(Number(value.replace(/,/g, "")))} of them hard`)
    .replace(/<=/g, "≤").replace(/>=/g, "≥");
}

export function formatIdealRange(ideal: string | null, key: FactorKey): string {
  if (ideal === null) return "ideal: No data";
  let text = ideal.replace(/^ideal\s*:?[ ]*/i, "").trim();
  if (/^(?:<=|≤)\s*0(?:\.0+)?$/.test(text)) return "ideal: none";
  if (key === "drainage") text = text.toLowerCase();
  text = formatDisplayText(text).replace(/(\d)\s*-\s*(?=\d)/g, "$1–");
  if (key === "season_temp" && !/°C/.test(text)) text += "°C";
  return `ideal: ${text}`;
}

export function formatFactorDetail(key: FactorKey, detail: FactorDetail | null | undefined): string {
  let value = "No data";
  if (detail?.value != null) {
    if (typeof detail.value === "number") {
      if (key === "season_temp") value = `${formatTemperature(detail.value)}${/avg/i.test(detail.unit ?? "") ? " avg" : ""}`;
      else {
        const number = key === "soil_ph" ? detail.value.toFixed(1) : formatWhole(detail.value);
        value = `${number}${detail.unit ? ` ${detail.unit.toLowerCase().replace(/^ph$/, "pH")}` : ""}`;
      }
    } else value = key === "drainage" ? detail.value.toLowerCase() : formatDisplayText(detail.value);
  }
  return `${value} · ${formatIdealRange(detail?.ideal ?? null, key)}`;
}

export function formatGuideTitle(title: string | null): string {
  return `UF/IFAS guide: ${(title ?? "Extension resource").replace(/^Chapter\s+\d+\.\s*/i, "")} ↗`;
}
