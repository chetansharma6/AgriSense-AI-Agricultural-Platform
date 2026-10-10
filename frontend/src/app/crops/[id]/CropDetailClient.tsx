"use client";

import Link from "next/link";
import AiReport from "@/components/AiReport";
import FactorChart from "@/components/FactorChart";
import { FACTOR_WEIGHTS, SCORE_EXPLANATION } from "@/lib/weights";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getCropDetail } from "@/lib/api";
import { formatPrice, formatYield, scoreTone } from "@/lib/format";
import type { CropDetail } from "@/lib/types";

export function CropDetailSkeleton() {
  return (
    <div role="status" aria-label="Loading crop details" className="space-y-6">
      <p className="text-soil">Loading crop details…</p>
      <div aria-hidden="true" className="animate-pulse space-y-6 motion-reduce:animate-none">
        <div className="h-28 rounded-xl bg-soil/10" />
        <div className="h-52 rounded-xl bg-soil/10" />
        <div className="grid gap-4 sm:grid-cols-2"><div className="h-24 rounded-xl bg-soil/10" /><div className="h-24 rounded-xl bg-soil/10" /></div>
      </div>
    </div>
  );
}

function record(value: unknown): Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

function levelLabel(level: unknown): string {
  if (level === "county") return "county average";
  if (level === "state") return "Florida average";
  return typeof level === "string" ? level : "Level not provided";
}

function extensionUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch { return null; }
}

type DetailState = { key: string; attempt: number; data?: CropDetail; error?: ApiError };
const badges = {
  strong: { style: "bg-field text-white", label: "Strong fit" },
  fair: { style: "bg-sun text-ink", label: "Fair fit" },
  weak: { style: "bg-clay text-white", label: "Weak fit" },
};

export default function CropDetailClient() {
  const { id } = useParams<{ id: string }>();
  const params = useSearchParams();
  const rawLat = params.get("lat");
  const rawLon = params.get("lon");
  const lat = Number(rawLat);
  const lon = Number(rawLon);
  const valid = !!id && rawLat !== null && rawLon !== null && rawLat.trim() !== "" && rawLon.trim() !== ""
    && Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const key = `${id}:${lat},${lon}`;
  const [verdictSlot, setVerdictSlot] = useState<HTMLDivElement | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<DetailState | null>(null);
  const backUrl = valid ? `/results?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}` : "/";

  useEffect(() => {
    if (!valid) return;
    let active = true;
    getCropDetail(id, lat, lon).then(
      (data) => { if (active) setState({ key, attempt, data }); },
      (error: unknown) => {
        if (active) setState({ key, attempt, error: error instanceof ApiError ? error
          : new ApiError("Something went wrong loading this crop. Please try again.", 0) });
      },
    );
    return () => { active = false; };
  }, [id, lat, lon, valid, key, attempt]);

  const back = <Link href={backUrl} className="inline-block text-field underline underline-offset-4">← All crops for this spot</Link>;
  if (!valid) return <div>{back}<p className="mt-6">Choose a valid Florida location from the home page to view this crop.</p></div>;
  if (state?.key !== key || state.attempt !== attempt) return <div>{back}<div className="mt-6"><CropDetailSkeleton /></div></div>;
  if (state.error) return (
    <div>{back}<section role="alert" className="mt-6 rounded-xl border border-clay/25 bg-white/50 p-6">
      <h1 className="text-2xl font-semibold">{state.error.status === 404 ? "We don't have that crop" : "Couldn’t load this crop"}</h1>
      {state.error.status !== 404 && <p className="mt-3">{state.error.message}</p>}
      <button type="button" onClick={() => setAttempt((n) => n + 1)} className="mt-5 rounded-lg bg-field px-5 py-3 font-semibold text-white">Try again</button>
    </section></div>
  );
  const crop = state.data;
  if (!crop) return <CropDetailSkeleton />;
  const tone = scoreTone(crop.score);
  const requirements = record(crop.requirements);
  const history = record(record(crop).history ?? requirements.history);
  const rawAcres = history.county_acres ?? requirements.county_acres;
  const acres = typeof rawAcres === "number" ? rawAcres : record(rawAcres).value ?? record(rawAcres).acres;
  // The current backend price_range uses Florida state prices.
  const priceLevel = record(crop.price).level ?? history.price_level ?? requirements.price_level
    ?? (crop.price ? "state" : null);
  return (
    <div className="space-y-8">
      {back}
      <header className="rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-3xl font-semibold">{crop.name ?? "Unnamed crop"}</h1>
            <p className="mt-2 text-soil">{crop.location?.county ? `${crop.location.county} County, Florida` : "County: No data"}</p>
            <p className="mt-2 text-sm">{crop.season_label ?? "Season: No data"}</p>
          </div>
          <div className={`shrink-0 rounded-lg px-3 py-2 text-center ${tone ? badges[tone].style : "bg-sand text-soil"}`}>
            <p className="text-3xl font-bold">{crop.score ?? "—"}</p>
            <p className="text-xs font-semibold">{tone ? badges[tone].label : "No data"}</p>
          </div>
        </div>
        <div id="ai-verdict" ref={setVerdictSlot} />
      </header>
      <FactorChart factors={crop.factors} details={crop.factor_details} weights={FACTOR_WEIGHTS} explanation={SCORE_EXPLANATION} />
      <AiReport key={key} crop={crop} verdictSlot={verdictSlot} />
      <section aria-labelledby="track-record">
        <h2 id="track-record" className="mb-4 text-2xl font-semibold">Local track record</h2>
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div className="rounded-xl bg-white/50 p-5"><dt className="text-sm text-soil">Average yield</dt><dd className="mt-2 text-xl font-semibold">{formatYield(crop.avg_yield)}</dd><dd className="mt-2 text-sm text-soil">{levelLabel(crop.avg_yield?.level)}</dd></div>
          <div className="rounded-xl bg-white/50 p-5"><dt className="text-sm text-soil">Price range</dt><dd className="mt-2 text-xl font-semibold">{formatPrice(crop.price)}</dd><dd className="mt-2 text-sm text-soil">{levelLabel(priceLevel)}</dd></div>
          {typeof acres === "number" && Number.isFinite(acres) && <div className="rounded-xl bg-white/50 p-5"><dt className="text-sm text-soil">County acres</dt><dd className="mt-2 text-xl font-semibold">{acres.toLocaleString("en-US")} acres</dd><dd className="mt-2 text-sm text-soil">Reported area in this county</dd></div>}
        </dl>
      </section>
      {!!crop.flags?.length && <section className="rounded-xl border border-sun/40 bg-sun/15 p-5" aria-labelledby="watch-out">
        <h2 id="watch-out" className="text-2xl font-semibold">Watch out for</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5">{crop.flags.map((flag, i) => <li key={i}>{flag}</li>)}</ul>
      </section>}
      <section aria-labelledby="growing-it">
        <h2 id="growing-it" className="text-2xl font-semibold">Growing it</h2>
        <p className="mt-4 whitespace-pre-line leading-relaxed">{crop.general_guidance ?? "Growing guidance is unavailable."}</p>
        <div className="mt-5 flex flex-wrap gap-3">{crop.extension_links?.map((link, i) => {
          const url = extensionUrl(link.url);
          return url ? <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-field px-4 py-3 text-sm font-semibold text-field hover:bg-leaf/15">{link.title ?? "UF/IFAS Extension resource"} ↗</a> : null;
        })}</div>
      </section>
      <aside className="rounded-xl border border-soil/25 bg-sand p-5 text-sm leading-relaxed">General guidance only. Confirm fertilizer and pesticide decisions with your county UF/IFAS Extension office and always follow product labels.</aside>
    </div>
  );
}
