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
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<RequestState | null>(null);

  useEffect(() => {
    if (!valid) return;
    let active = true;
    getRecommendations(lat, lon).then(
      (data) => { if (active) setState({ key, attempt, data }); },
      (error: unknown) => {
        if (active) setState({ key, attempt, error: error instanceof ApiError
          ? error.message : "Something went wrong while checking your land. Please try again." });
      },
    );
    return () => { active = false; };
  }, [lat, lon, valid, key, attempt]);

  if (!valid) return (
    <section className="rounded-xl border border-clay/25 bg-white/50 p-6">
      <h2 className="text-xl font-semibold">Choose a valid Florida location</h2>
      <p className="mt-3">The link needs latitude 24.3–31.1 and longitude −87.7–−79.9.</p>
      <Link href="/" className="mt-4 inline-block text-field underline underline-offset-4">Back home to pick a spot</Link>
    </section>
  );
  if (state?.key !== key || state.attempt !== attempt) return <LandSummarySkeleton />;
  if (state.error) return (
    <section className="rounded-xl border border-clay/25 bg-white/50 p-6" role="alert">
      <h2 className="text-xl font-semibold">We couldn’t check your land</h2>
      <p className="mt-3">{state.error}</p>
      <div className="mt-5 flex flex-wrap items-center gap-5">
        <button type="button" onClick={() => setAttempt((n) => n + 1)} className="rounded-lg bg-field px-5 py-3 font-semibold text-white">Try again</button>
        <Link href="/" className="text-field underline underline-offset-4">Pick another spot</Link>
      </div>
    </section>
  );
  if (!state.data) return <LandSummarySkeleton />;
  const crops = [...(state.data.crops ?? [])].sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  return (
    <div>
      <LandSummary response={state.data} />
      {crops.length === 0 ? (
        <p className="mt-8 text-soil">No crop recommendations are available for this spot.</p>
      ) : (
        <>
          <section className="mt-10" aria-labelledby="best-fits-title">
            <h2 id="best-fits-title" className="mb-5 text-2xl font-semibold">Best fits for this spot</h2>
            <div className="grid gap-4 lg:grid-cols-3">
              {crops.slice(0, 3).map((crop, i) => <CropCard key={crop.id ?? i} crop={crop} rank={i + 1} lat={lat} lon={lon} />)}
            </div>
          </section>
          {crops.length > 3 && (
            <section className="mt-10" aria-labelledby="other-crops-title">
              <h2 id="other-crops-title" className="mb-5 text-2xl font-semibold">Other crops</h2>
              <div className="space-y-3">
                {crops.slice(3).map((crop, i) => <CropCard key={crop.id ?? i} crop={crop} rank={i + 4} lat={lat} lon={lon} compact />)}
              </div>
            </section>
          )}
        </>
      )}
    </div>
  );
}
