"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import CropCard from "@/components/CropCard";
import LandSummary, { LandSummarySkeleton } from "@/components/LandSummary";
import { ApiError, getRecommendations } from "@/lib/api";
import type { RecommendResponse } from "@/lib/types";

type RequestState = {
  key: string;
  attempt: number;
  data?: RecommendResponse;
  error?: string;
};

// Render free-plan servers can take about a minute to wake after being idle.
const SLOW_AFTER_MS = 5_000;

const filters = ["All", "Strong fit (75+)", "Summer crops", "Fall/Winter crops", "Needs irrigation"] as const;
type CropFilter = typeof filters[number];

export default function ResultsClient() {
  const params = useSearchParams();
  const rawLat = params.get("lat");
  const rawLon = params.get("lon");
  const lat = Number(rawLat);
  const lon = Number(rawLon);
  const valid = rawLat !== null && rawLon !== null && rawLat.trim() !== "" && rawLon.trim() !== ""
    && Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const key = `${lat},${lon}`;
  const [filter, setFilter] = useState<CropFilter>("All");
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<RequestState | null>(null);
  const [slowFor, setSlowFor] = useState<string | null>(null);
  const slow = slowFor === `${key}:${attempt}`;

  useEffect(() => {
    if (!valid) return;
    let active = true;
    const slowTimer = setTimeout(() => setSlowFor(`${key}:${attempt}`), SLOW_AFTER_MS);
    getRecommendations(lat, lon).then(
      (data) => { if (active) setState({ key, attempt, data }); },
      (error: unknown) => {
        if (active) setState({ key, attempt, error: error instanceof ApiError
          ? error.message : "Something went wrong while checking your land. Please try again." });
      },
    );
    return () => { active = false; clearTimeout(slowTimer); };
  }, [lat, lon, valid, key, attempt]);

  if (!valid) return (
    <section className="rounded-xl border border-clay/25 bg-white/50 p-5 sm:p-6">
      <h2 className="text-xl font-semibold">Choose a valid Florida location</h2>
      <p className="mt-3">The link needs latitude 24.3–31.1 and longitude −87.7–−79.9.</p>
      <Link href="/" className="mt-2 inline-flex min-h-11 items-center text-field underline underline-offset-4">Back home to pick a spot</Link>
    </section>
  );
  if (state?.key !== key || state.attempt !== attempt) return <LandSummarySkeleton slow={slow} />;
  if (state.error) return (
    <section className="rounded-xl border border-clay/25 bg-white/50 p-5 sm:p-6" role="alert">
      <h2 className="text-xl font-semibold">We couldn’t check your land</h2>
      <p className="mt-3">{state.error}</p>
      <div className="mt-5 flex flex-wrap items-center gap-5">
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="rounded-lg bg-field px-5 py-3 font-semibold text-white">Try again</button>
        <Link href="/" className="inline-flex min-h-11 items-center text-field underline underline-offset-4">Pick another spot</Link>
      </div>
    </section>
  );
  if (!state.data) return <LandSummarySkeleton slow={slow} />;
  const crops = [...(state.data.crops ?? [])].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  const ranked = crops.map((crop, i) => ({ crop, rank: i + 1 }));
  const matching = ranked.filter(({ crop }) => {
    const coolSeason = /fall|winter|spring/i.test(crop.season_label ?? "");
    switch (filter) {
      case "Strong fit (75+)": return crop.score !== null && crop.score >= 75;
      case "Summer crops": return crop.season_label !== null && !coolSeason;
      case "Fall/Winter crops": return coolSeason;
      case "Needs irrigation": return crop.flags?.some((flag) => /irrigation/i.test(flag)) ?? false;
      default: return true;
    }
  });
  const bestFits = matching.filter(({ rank }) => rank <= 3);
  const otherCrops = matching.filter(({ rank }) => rank > 3);
  return (
    <div>
      <LandSummary response={state.data} place={params.get("place")?.trim() || undefined} />
      <div className="mt-8 flex flex-wrap gap-2" role="group" aria-label="Filter crops">
        {filters.map((label) => (
          <button key={label} type="button" aria-pressed={filter === label} onClick={() => setFilter(label)}
            className={`min-h-11 rounded-full border px-4 py-2 text-sm font-medium focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field ${filter === label ? "border-field bg-field text-white" : "border-field/25 bg-white/60 hover:bg-leaf/15"}`}>
            {label}
          </button>
        ))}
      </div>
      {matching.length === 0 ? (
        <p className="mt-8 text-soil">No crops match this filter</p>
      ) : (
        <>
          {bestFits.length > 0 && <section className="mt-10" aria-labelledby="best-fits-title">
            <h2 id="best-fits-title" className="mb-5 text-2xl font-semibold">Best fits for this spot</h2>
            <div className="grid gap-4 lg:grid-cols-3">
              {bestFits.map(({ crop, rank }) => <CropCard key={crop.id ?? rank} crop={crop} rank={rank} lat={lat} lon={lon} />)}
            </div>
          </section>}
          {otherCrops.length > 0 && (
            <section className="mt-10" aria-labelledby="other-crops-title">
              <h2 id="other-crops-title" className="mb-5 text-2xl font-semibold">Other crops</h2>
              <div className="space-y-3">
                {otherCrops.map(({ crop, rank }) => <CropCard key={crop.id ?? rank} crop={crop} rank={rank} lat={lat} lon={lon} compact />)}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
