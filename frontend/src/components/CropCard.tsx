import Link from "next/link";
import { factorLabel, limitedText, formatPrice, formatYield, scoreTone, formatDisplayText, formatWhole } from "@/lib/format";
import type { CropResult, FactorKey } from "@/lib/types";

interface CropCardProps {
  crop: CropResult;
  rank: number;
  lat: number;
  lon: number;
  compact?: boolean;
  place?: string;
}

const factorKeys: FactorKey[] = ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"];
const tones = {
  strong: { label: "Strong fit", badge: "bg-field text-white", bar: "bg-field" },
  fair: { label: "Fair fit", badge: "bg-sun text-ink", bar: "bg-sun" },
  weak: { label: "Weak fit", badge: "bg-clay text-white", bar: "bg-clay" },
};

export default function CropCard({ crop, rank, lat, lon, place, compact = false }: CropCardProps) {
  const tone = scoreTone(crop.score);
  const factors = factorKeys.map((key) => ({ key, score: crop.factors?.[key] ?? null }))
    .sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  const top = factors.slice(0, 3);
  const low = factors.filter((factor) => factor.score !== null && factor.score < 60 && !top.some((item) => item.key === factor.key))
    .sort((a, b) => (a.score ?? 0) - (b.score ?? 0));
  const visibleFactors = [...top, ...low].slice(0, 4);
  const content = (
    <article className={`card h-full rounded-xl border border-field/20 bg-white/60 ${compact ? "p-4 sm:p-5" : "p-5 sm:p-6"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-soil">#{rank}</p>
          <h3 className="mt-1 text-xl font-semibold">{crop.name ?? "Unnamed crop"}</h3>
          <p className="mt-2 text-sm leading-relaxed text-soil">{crop.season_label ?? "Season: No data"}</p>
        </div>
        <div className={`shrink-0 rounded-lg px-3 py-2 text-center ${tone ? tones[tone].badge : "bg-sand text-soil"}`}>
          <p className="text-3xl font-bold">{crop.score === null ? "—" : formatWhole(crop.score)}</p>
          <p className="text-sm font-semibold">{tone ? tones[tone].label : "No data"}</p>
        </div>
      </div>
      <div className={`mt-5 grid gap-2 ${compact ? "sm:grid-cols-2 sm:gap-x-6 lg:grid-cols-3" : ""}`}>
        {visibleFactors.map(({ key, score }) => {
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
      {crop.flags?.[0] && !crop.flags[0].startsWith("Limited by") && <p className="mt-3 inline-block rounded-full bg-sun/20 px-3 py-1 text-sm text-ink">{formatDisplayText(crop.flags[0])}</p>}
    </article>
  );
  if (!crop.id) return content;
  const query = new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4) });
  if (place) query.set("place", place);
  if (crop.name) query.set("crop", crop.name);
  return (
    <Link href={`/crops/${encodeURIComponent(crop.id)}?${query}`}
      className="crop-card-link block min-w-0 rounded-xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-field">
      {content}
    </Link>
  );
}
