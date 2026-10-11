"use client";

import { parseAcres } from "@/lib/acreage";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import CropCard from "@/components/CropCard";
import LandSummary from "@/components/LandSummary";
import DataStatusChips from "@/components/DataStatusChips";
import { ApiError, getRecommendations } from "@/lib/api";
import ResultsSkeleton from "@/components/ResultsSkeleton";
import { placeLabel, resultsSummary } from "@/lib/presentation";
import type { RecommendResponse } from "@/lib/types";

type RequestState = {
  key: string;
  attempt: number;
  data?: RecommendResponse;
  error?: string;
};

// Render free-plan servers can take about a minute to wake after being idle.
const SLOW_AFTER_MS = 5_000;

const filters = ["All", "Strong fit (75+)", "Summer crops", "Fall/Winter crops", "Needs irrigation", "Fits my land size"] as const;
type CropFilter = typeof filters[number];

export default function ResultsClient() {
  const params = useSearchParams();
  const acres = parseAcres(params.get("acres"));
  const rawLat = params.get("lat");
  const rawLon = params.get("lon");
  const lat = Number(rawLat);
  const lon = Number(rawLon);
  const valid = (acres === undefined || Number.isFinite(acres)) && rawLat !== null && rawLon !== null && rawLat.trim() !== "" && rawLon.trim() !== ""
    && Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const key = `${lat},${lon}:${acres ?? ""}`;
  const [filter, setFilter] = useState<CropFilter>("All");
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<RequestState | null>(null);
  const [slowFor, setSlowFor] = useState<string | null>(null);
  const slow = slowFor === `${key}:${attempt}`;

  useEffect(() => {
    if (!valid) return;
    let active = true;
    const slowTimer = setTimeout(() => setSlowFor(`${key}:${attempt}`), SLOW_AFTER_MS);
    getRecommendations(lat, lon, acres).then(
      (data) => { if (active) setState({ key, attempt, data }); },
      (error: unknown) => {
        if (active) setState({ key, attempt, error: error instanceof ApiError
          ? error.message : "Something went wrong while checking your land. Please try again." });
      },
    );
    return () => { active = false; clearTimeout(slowTimer); };
  }, [lat, lon, acres, valid, key, attempt]);

  const current = state?.key === key && state.attempt === attempt ? state.data : undefined;
  const place = placeLabel(params.get("place"), current?.location?.county);
  const title = `${place}${acres !== undefined && Number.isFinite(acres) ? ` for ${acres.toLocaleString("en-US", { maximumFractionDigits: 20 })} acres` : ""}`;
  useEffect(() => { document.title = `${title} results · AgriSense`; }, [title]);
  function withTitle(content: ReactNode) {
    return <><h1 className="page-title mb-6">{title}</h1>{content}</>;
  }

  if (!valid) return withTitle(
    <section className="rounded-xl border border-clay/25 bg-white/50 p-5 sm:p-6">
      <h2 className="text-xl font-semibold">Choose a valid Florida location</h2>
      <p className="mt-3">The link needs latitude 24.3–31.1 and longitude −87.7–−79.9, and optional acreage from 0.1 to 10,000.</p>
      <Link href="/" className="mt-2 inline-flex min-h-11 items-center text-field underline underline-offset-4">Back home to pick a spot</Link>
    </section>
  );
  if (state?.key !== key || state.attempt !== attempt) return withTitle(<ResultsSkeleton slow={slow} />);
  if (state.error) return withTitle(
    <section className="rounded-xl border border-clay/25 bg-white/50 p-5 sm:p-6" role="alert">
      <h2 className="text-xl font-semibold">We couldn’t check your land</h2>
      <p className="mt-3">{state.error}</p>
      <div className="mt-5 flex flex-wrap items-center gap-5">
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="rounded-lg bg-field px-5 py-3 font-semibold text-white">Try again</button>
        <Link href="/" className="inline-flex min-h-11 items-center text-field underline underline-offset-4">Pick another spot</Link>
      </div>
    </section>
  );
  if (!state.data) return withTitle(<ResultsSkeleton slow={slow} />);
  const response = state.data;
  const crops = [...(response.crops ?? [])].sort((a, b) => (b.score ?? -1) - (a.score ?? -1) || (a.name ?? "").localeCompare(b.name ?? ""));
  const ranked = crops.map((crop, i) => ({ crop, rank: i + 1 }));
  const matching = ranked.filter(({ crop }) => {
    const coolSeason = /fall|winter|spring/i.test(crop.season_label ?? "");
    switch (filter) {
      case "Fits my land size": return crop.scale?.fit === "good";
      case "Strong fit (75+)": return crop.score !== null && crop.score >= 75;
      case "Summer crops": return crop.season_label !== null && !coolSeason;
      case "Fall/Winter crops": return coolSeason;
      case "Needs irrigation": return crop.flags?.some((flag) => /irrigation/i.test(flag)) ?? false;
      default: return true;
    }
  });
  const bestFits = matching.filter(({ rank }) => rank <= 3);
  const otherCrops = matching.filter(({ rank }) => rank > 3);
  return withTitle(
    <div>
      {ranked[0] ? <div className="mb-6"><CropCard crop={ranked[0].crop} rank={1} lat={lat} lon={lon} acres={acres} place={place} featured provenance={response.provenance} confidence={response.confidence} /></div> : <p className="mb-6">No crop recommendations are available for this location.</p>}
      <p className="mb-5 text-lg leading-relaxed">{resultsSummary(crops)}</p>
      <DataStatusChips provenance={response.provenance} confidence={response.confidence} />
      <p className="mb-5 text-sm leading-relaxed">{acres === undefined ? "Land size was not provided. Rankings reflect local growing conditions; acreage affects practical suitability and recommendation confidence." : "Land size influences these rankings: field commodities on undersized lots are capped at 40; smaller commercial plantings at 74. Garden-bed crops can fit small lots. These planning rules do not guarantee profitability."}</p>
      <LandSummary response={state.data} place={params.get("place")?.trim() || undefined} />
      <p className="mt-3 text-xs leading-relaxed text-soil">Climate: NASA POWER 2016–2025 · Soil: USDA NRCS SSURGO · Harvests: USDA NASS</p>
      <div className="mt-8 flex flex-wrap items-center gap-2" role="group" aria-label="Filter crops">
        {filters.map((label) => (
          <button key={label} type="button" aria-pressed={filter === label} disabled={label === "Fits my land size" && acres === undefined} onClick={() => setFilter(label)}
            className={`disabled:cursor-not-allowed disabled:opacity-50 min-h-11 rounded-full border px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field ${filter === label ? "border-field bg-field text-white" : "border-field/25 bg-white/60 hover:bg-leaf/15"}`}>
            {label}
          </button>
        ))}
        <p className="flex flex-wrap gap-2 text-xs" aria-label="Score legend">
          <span className="rounded-full bg-field px-3 py-2 text-white">75+ strong</span><span aria-hidden="true">·</span>
          <span className="rounded-full bg-sun px-3 py-2 text-ink">50–74 fair</span><span aria-hidden="true">·</span>
          <span className="rounded-full bg-clay px-3 py-2 text-white">under 50 weak</span>
        </p>
      </div>
      {matching.length === 0 ? (
        <p className="mt-8 text-soil">No crops match this filter</p>
      ) : (
        <>
          {bestFits.length > 0 && <section className="mt-10" aria-labelledby="best-fits-title">
            <h2 id="best-fits-title" className="mb-5 text-2xl font-semibold">Best fits for this spot</h2>
            <div className="grid gap-4 lg:grid-cols-3">
              {bestFits.map(({ crop, rank }) => <CropCard key={crop.id ?? rank} crop={crop} rank={rank} lat={lat} lon={lon} place={place} acres={acres} provenance={response.provenance} confidence={response.confidence} />)}
            </div>
          </section>}
          {otherCrops.length > 0 && (
            <section className="mt-10" aria-labelledby="other-crops-title">
              <h2 id="other-crops-title" className="mb-5 text-2xl font-semibold">Other crops</h2>
              <div className="space-y-3">
                {otherCrops.map(({ crop, rank }) => <CropCard key={crop.id ?? rank} crop={crop} rank={rank} lat={lat} lon={lon} place={place} acres={acres} compact provenance={response.provenance} confidence={response.confidence} />)}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
