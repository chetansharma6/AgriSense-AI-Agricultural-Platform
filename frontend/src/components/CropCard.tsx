import Link from "next/link";
import { factorLabel, limitedText, formatPrice, formatYield, scoreTone, formatDisplayText, formatWhole } from "@/lib/format";
import { cropHighlights, cropPlanUrl } from "@/lib/presentation";
import DataStatusChips from "./DataStatusChips";
import type { Confidence, Provenance, CropResult, FactorKey } from "@/lib/types";

interface CropCardProps {
  crop: CropResult;
  rank: number;
  lat: number;
  lon: number;
  acres?: number;
  compact?: boolean;
  place?: string;
  featured?: boolean;
  provenance?: Provenance | null;
  confidence?: Confidence | null;
}

const factorKeys: FactorKey[] = ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"];
const tones = {
  strong: { label: "Strong fit", badge: "bg-field text-white", bar: "bg-field" },
  fair: { label: "Fair fit", badge: "bg-sun text-ink", bar: "bg-sun" },
  weak: { label: "Weak fit", badge: "bg-clay text-white", bar: "bg-clay" },
};

export default function CropCard({ crop, rank, lat, lon, place, acres, compact = false, featured = false, provenance, confidence }: CropCardProps) {
  const tone = scoreTone(crop.score);
  const factors = factorKeys.map((key) => ({ key, score: crop.factors?.[key] ?? null }));
  const highlights = cropHighlights(crop);
  const href = cropPlanUrl(crop, lat, lon, acres, place);
  const content = (
    <article className={`card h-full rounded-xl ${featured ? "border-2 border-field bg-mint" : "border border-field/20 bg-white/60"} ${compact ? "p-4 sm:p-5" : "p-5 sm:p-6"}`}>
      {featured && <h2 className="mb-4 text-2xl font-semibold text-field">Your Best Match</h2>}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-soil">#{rank}</p>
          <h3 className="mt-1 text-xl font-semibold">{crop.name ?? "Unnamed crop"}</h3>
          <p className="mt-2 text-sm leading-relaxed text-soil">{formatDisplayText(highlights.window)}</p>
        </div>
        <div className={`shrink-0 rounded-2xl px-3 py-3 text-center ${tone ? tones[tone].badge : "bg-sand text-soil"}`}>
          <p className="text-3xl font-bold">{crop.score == null ? "—" : formatWhole(crop.score)}<span className="text-sm font-medium"> /100</span></p>
          <p className="text-sm font-semibold">{tone ? tones[tone].label : "Score unavailable"}</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-soil">Suitability score · not a measure of data coverage</p>
      <div className="mt-3"><DataStatusChips provenance={provenance} confidence={confidence} /></div>
      <dl className="mt-4 space-y-3 text-sm leading-relaxed">
        <div><dt className="font-semibold">{featured ? "Why this crop" : "Strongest evidence"}</dt><dd>{formatDisplayText(highlights.reason)}</dd></div>
        <div><dt className="font-semibold">Main consideration</dt><dd>{formatDisplayText(highlights.consideration)}</dd></div>
        {featured && <div><dt className="font-semibold">First step</dt><dd>{formatDisplayText(highlights.firstStep)}</dd></div>}
      </dl>
      {href ? <Link href={href} className="mt-4 inline-flex min-h-11 items-center rounded-lg bg-field px-4 py-3 text-sm font-semibold text-white focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-field" aria-label={`View growing plan for ${crop.name ?? "this crop"}`}>View growing plan <span className="ml-2" aria-hidden="true">↗</span></Link> : <p className="mt-4 text-sm text-soil">Growing plan unavailable: crop identifier missing.</p>}
      <details className="mt-4 border-t border-field/20 pt-2">
        <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-field">Factors, market &amp; scoring details</summary>
        {crop.scale?.fit && <p className="mt-3 text-sm">{{ good: "Fits your size", small: "Tight for your size", too_small: "Needs more land" }[crop.scale.fit]}{crop.scale.note ? `: ${formatDisplayText(crop.scale.note)}` : ""}</p>}
        {rank <= 3 && <p className="mt-3 text-sm"><span className="font-semibold">First action:</span> {formatDisplayText(highlights.firstStep)}</p>}
        {crop.est_gross_value && <p className="mt-3 text-sm">Rough gross value: ${formatWhole(crop.est_gross_value.low)}–${formatWhole(crop.est_gross_value.high)} before costs</p>}
        <div className={`mt-5 grid gap-2 ${compact ? "sm:grid-cols-2 sm:gap-x-6 lg:grid-cols-3" : ""}`}>
          {factors.map(({ key, score }) => {
            const factorTone = scoreTone(score);
            return (
              <div key={key}>
                <div className="mb-1 flex justify-between gap-2 text-sm">
                  <span>{factorLabel(key)}</span><span>{formatWhole(score)}</span>
                </div>
                {score !== null && (
                  <div role="meter" aria-label={factorLabel(key)} aria-valuemin={0} aria-valuemax={100} aria-valuenow={score}
                    className="h-1.5 overflow-hidden rounded-full bg-soil/10">
                    <div className={`h-full rounded-full ${factorTone ? tones[factorTone].bar : "bg-soil"}`} style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="mt-5 text-sm leading-relaxed text-soil">Price: {formatPrice(crop.price)} · Yield: {formatYield(crop.avg_yield)}</p>
        {!!crop.limited_by?.length && <p className="mt-3 inline-block rounded-full bg-clay/10 px-3 py-1 text-sm font-semibold text-clay">{limitedText(crop.limited_by)}</p>}
        {!!crop.risk_notes?.length && <ul className="mt-3 list-disc space-y-1 pl-5 text-sm" aria-label="Crop risks">{crop.risk_notes.map((note, index) => <li key={index}>{formatDisplayText(note)}</li>)}</ul>}
        {!!crop.flags?.length && <ul className="mt-3 list-disc space-y-1 pl-5 text-sm">{crop.flags.map((flag, index) => <li key={index}>{formatDisplayText(flag)}</li>)}</ul>}
      </details>
    </article>
  );
  return content;
}
