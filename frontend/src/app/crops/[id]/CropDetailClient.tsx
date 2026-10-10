"use client";

import { parseAcres } from "@/lib/acreage";
import Link from "next/link";
import AiReport from "@/components/AiReport";
import FactorChart from "@/components/FactorChart";
import { placeLabel } from "@/lib/presentation";
import { explanationFor, weightsFor } from "@/lib/weights";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, getCropDetail } from "@/lib/api";
import { formatPrice, limitedText, formatYield, scoreTone, formatWhole, formatDisplayText, formatGuideTitle } from "@/lib/format";
import type { CropDetail } from "@/lib/types";

export function CropDetailSkeleton() {
  return (
    <div role="status" aria-live="polite" aria-label="Loading crop details" className="space-y-6">
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
  const landAcres = parseAcres(params.get("acres"));
  const rawLat = params.get("lat");
  const rawLon = params.get("lon");
  const lat = Number(rawLat);
  const lon = Number(rawLon);
  const valid = (landAcres === undefined || Number.isFinite(landAcres)) && !!id && rawLat !== null && rawLon !== null && rawLat.trim() !== "" && rawLon.trim() !== ""
    && Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const key = `${id}:${lat},${lon}:${landAcres ?? ""}`;
  const [verdictSlot, setVerdictSlot] = useState<HTMLDivElement | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<DetailState | null>(null);
  const current = state?.key === key && state.attempt === attempt ? state.data : undefined;
  const place = placeLabel(params.get("place"), current?.location?.county);
  const name = current?.name ?? id.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const query = new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4) });
  if (landAcres !== undefined) query.set("acres", String(landAcres));
  if (params.get("place")) query.set("place", params.get("place")!);
  const backUrl = valid ? `/results?${query}` : "/";
  useEffect(() => { document.title = `${name} at ${place} · AgriSense`; }, [name, place]);

  useEffect(() => {
    if (!valid) return;
    let active = true;
    getCropDetail(id, lat, lon, landAcres).then(
      (data) => { if (active) setState({ key, attempt, data }); },
      (error: unknown) => {
        if (active) setState({ key, attempt, error: error instanceof ApiError ? error
          : new ApiError("Something went wrong loading this crop. Please try again.", 0) });
      },
    );
    return () => { active = false; };
  }, [id, lat, lon, landAcres, valid, key, attempt]);

  const back = <nav aria-label="Breadcrumbs" className="no-print"><ol className="flex flex-wrap items-center gap-x-2 text-sm">
    <li><Link href="/" className="inline-flex min-h-11 items-center text-field underline underline-offset-4">Home</Link></li><li aria-hidden="true">→</li>
    <li><Link href={backUrl} className="inline-flex min-h-11 items-center text-field underline underline-offset-4">{place} results</Link></li><li aria-hidden="true">→</li>
    <li aria-current="page" className="py-3">{name}</li>
  </ol></nav>;
  if (!valid) return <div>{back}<p className="mt-6">Choose a valid Florida location from the home page to view this crop.</p></div>;
  if (state?.key !== key || state.attempt !== attempt) return <div>{back}<div className="mt-6"><CropDetailSkeleton /></div></div>;
  if (state.error) return (
    <div>{back}<section role="alert" className="mt-6 rounded-xl border border-clay/25 bg-white/50 p-5 sm:p-6">
      <h1 className="section-title">{state.error.status === 404 ? "We don't have that crop" : "Couldn’t load this crop"}</h1>
      {state.error.status !== 404 && <p className="mt-3">{state.error.message}</p>}
      <button type="button" onClick={() => setAttempt((n) => n + 1)} className="mt-5 rounded-lg bg-field px-5 py-3 font-semibold text-white">Try again</button>
    </section></div>
  );
  const crop = state.data;
  if (!crop) return <CropDetailSkeleton />;
  const tone = scoreTone(crop.score);
  const requirements = record(crop.requirements);
  const history = record(record(crop).history ?? requirements.history);
  const historyValue = crop.factor_details?.local_history?.value;
  const acreageMatch = typeof historyValue === "string" ? /^([\d,.]+) acres in county\b/i.exec(historyValue) : null;
  const rawAcres = history.county_acres ?? requirements.county_acres
    ?? (acreageMatch ? Number(acreageMatch[1].replace(/,/g, "")) : undefined);
  const acres = typeof rawAcres === "number" ? rawAcres : record(rawAcres).value ?? record(rawAcres).acres;
  const hasAcres = typeof acres === "number" && Number.isFinite(acres);
  // The current backend price_range uses Florida state prices.
  const priceLevel = record(crop.price).level ?? history.price_level ?? requirements.price_level
    ?? (crop.price ? "state" : null);
  return (
    <div className="space-y-8">
      <div className="no-print flex flex-wrap items-center justify-between gap-3">{back}<button type="button" onClick={() => window.print()} className="min-h-11 rounded-lg border border-field bg-white/50 px-4 py-3 text-sm font-semibold text-field hover:bg-leaf/15">Download report</button></div>
      <header className="card rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h1 className="page-title">{crop.name ?? "Unnamed crop"}</h1>
            <p className="mt-2 text-soil">{crop.location?.county ? `${crop.location.county} County, Florida` : "County: No data"}</p>
            <p className="mt-2 text-sm">{crop.season_label ?? "Season: No data"}</p>
          </div>
          <div className={`shrink-0 rounded-lg px-3 py-2 text-center ${tone ? badges[tone].style : "bg-sand text-soil"}`}>
            <p className="text-3xl font-bold">{crop.score === null ? "—" : formatWhole(crop.score)}</p>
            <p className="text-sm font-semibold">{tone ? badges[tone].label : "No data"}</p>
          </div>
        </div>
        {!!crop.limited_by?.length && <p className="mt-3 inline-block rounded-full bg-clay/10 px-3 py-1 text-sm font-semibold text-clay">Score capped at {crop.scale?.fit === "too_small" ? Math.min(40, crop.scoring?.critical_cap ?? 45) : crop.scoring?.critical_cap ?? 45}. {limitedText(crop.limited_by)}</p>}
        <div id="ai-verdict" ref={setVerdictSlot} />
      </header>
      <FactorChart factors={crop.factors} details={crop.factor_details} weights={weightsFor(crop.scoring)} explanation={explanationFor(crop.scoring)} />
      <AiReport key={key} crop={crop} acres={landAcres} verdictSlot={verdictSlot} />
      <section aria-labelledby="track-record">
        <h2 id="track-record" className="section-title mb-5">Local track record</h2>
        <dl className={`grid gap-4 ${hasAcres ? "sm:grid-cols-3" : "sm:grid-cols-2"}`}>
          <div className="card min-w-0 rounded-xl bg-white/50 p-5"><dt className="text-sm text-soil">Average yield</dt><dd className="mt-2 break-words text-xl font-semibold">{formatYield(crop.avg_yield)}</dd><dd className="mt-2 text-sm text-soil">{levelLabel(crop.avg_yield?.level)}</dd></div>
          <div className="card min-w-0 rounded-xl bg-white/50 p-5"><dt className="text-sm text-soil">Price range</dt><dd className="mt-2 break-words text-xl font-semibold">{formatPrice(crop.price)}</dd><dd className="mt-2 text-sm text-soil">{levelLabel(priceLevel)}</dd></div>
          {hasAcres && <div className="card min-w-0 rounded-xl bg-white/50 p-5"><dt className="text-sm text-soil">County acres</dt><dd className="mt-2 break-words text-xl font-semibold">{formatWhole(acres as number)} acres</dd><dd className="mt-2 text-sm text-soil">Reported area in this county</dd></div>}
        </dl>
      </section>
      {!!crop.flags?.length && <section className="card rounded-xl border border-sun/40 bg-sun/15 p-5" aria-labelledby="watch-out">
        <h2 id="watch-out" className="section-title">Watch out for</h2>
        <ul className="mt-3 list-disc space-y-2 pl-5">{crop.flags.map((flag, i) => <li key={i}>{formatDisplayText(flag)}</li>)}</ul>
      </section>}
      <section aria-labelledby="growing-it">
        <h2 id="growing-it" className="section-title">Growing it</h2>
        <p className="mt-4 whitespace-pre-line leading-relaxed">{formatDisplayText(crop.general_guidance ?? "Growing guidance is unavailable.")}</p>
        <div className="mt-5 flex flex-wrap gap-3">{crop.extension_links?.map((link, i) => {
          const url = extensionUrl(link.url);
          return url ? <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-field px-4 py-3 text-sm font-semibold text-field hover:bg-leaf/15">{formatGuideTitle(link.title)}</a> : null;
        })}</div>
      </section>
      {crop.nutrient_plan && <section className="card rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="feeding-soil">
        <h2 id="feeding-soil" className="section-title">Feeding the soil</h2>
        {crop.nutrient_plan.lime_note && <p className="mt-4 leading-relaxed">{crop.nutrient_plan.lime_note}</p>}
        <p className="mt-4">Get a soil test before choosing fertilizer or lime.</p>
        {crop.nutrient_plan.n_lb_per_acre !== null && <p className="mt-4 leading-relaxed">UF/IFAS suggests about {crop.nutrient_plan.n_lb_per_acre} lb of nitrogen per acre per season, split into several applications.</p>}
        <ul className="mt-4 space-y-3" aria-label="Soil feeding checklist">{crop.nutrient_plan.practices.map((practice, i) => <li key={i} className="flex items-start gap-3"><span aria-hidden="true" className="text-field">✓</span><span>{practice}</span></li>)}</ul>
        <div className="mt-4 flex flex-wrap gap-3">{crop.nutrient_plan.sources.map((source, i) => {
          const url = extensionUrl(source.url);
          return url ? <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center text-sm text-field underline underline-offset-4">{source.title}</a> : null;
        })}</div>
      </section>}
      <aside className="card report-disclaimer rounded-xl border border-soil/25 bg-sand p-5 text-sm leading-relaxed">General guidance only. Confirm fertilizer and pesticide decisions with your county UF/IFAS Extension office and always follow product labels.</aside>
    </div>
  );
}
