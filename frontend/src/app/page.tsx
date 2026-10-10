"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import MapLoader from "@/components/MapLoader";

const demos = [
  { name: "Marianna", caption: "Panhandle row crops", lat: 30.80, lon: -85.25 },
  { name: "Hastings", caption: "Potato country", lat: 29.71, lon: -81.50 },
  { name: "Plant City", caption: "Strawberry capital", lat: 28.03, lon: -82.15 },
  { name: "Belle Glade", caption: "Everglades muck", lat: 26.68, lon: -80.68 },
];

export default function Home() {
  const router = useRouter();
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const lat = Number(latitude);
  const lon = Number(longitude);
  const complete = latitude.trim() !== "" && longitude.trim() !== "";
  const finite = complete && Number.isFinite(lat) && Number.isFinite(lon);
  const valid = finite && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const value = finite ? { lat, lon } : null;

  function selectPoint(lat: number, lon: number) {
    setLatitude(lat.toFixed(4));
    setLongitude(lon.toFixed(4));
  }

  function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (valid) router.push(`/results?lat=${lat.toFixed(4)}&lon=${lon.toFixed(4)}`);
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-field/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <Link href="/" className="text-2xl font-bold tracking-tight text-field">AgriSense</Link>
          <Link href="/about" className="text-sm font-medium underline decoration-field/30 underline-offset-4 hover:text-field">About the data</Link>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 lg:py-14">
        <section className="mb-9 max-w-3xl">
          <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-soil">Florida land. Local possibilities.</p>
          <h1 className="text-4xl leading-tight font-semibold tracking-tight sm:text-5xl">Find the crops your Florida land is built for</h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-ink/75 sm:text-lg">Pick a spot on the map. We check soil, climate and local harvest history, then rank 13 Florida crops by how well they fit.</p>
        </section>
        <div className="grid min-w-0 gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
          <section className="min-w-0" aria-label="Farm location map">
            <div className="overflow-hidden rounded-xl border border-field/20">
              <MapLoader value={value} onChange={selectPoint} demoPins={demos} />
            </div>
            <p className="mt-3 text-sm text-soil">Click the map or choose a demo farm to get started.</p>
          </section>
          <form onSubmit={analyze} className="rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6">
            <h2 className="text-xl font-semibold">Try a demo farm</h2>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {demos.map((demo) => {
                const selected = latitude === demo.lat.toFixed(4) && longitude === demo.lon.toFixed(4);
                return (
                  <button key={demo.name} type="button" onClick={() => selectPoint(demo.lat, demo.lon)} aria-pressed={selected}
                    className={`rounded-lg border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field ${selected ? "border-field bg-field text-white" : "border-field/20 bg-sand/50 hover:border-field hover:bg-leaf/15"}`}>
                    <span className="block text-sm font-semibold">{demo.name}</span>
                    <span className={`mt-1 block whitespace-nowrap text-[11px] sm:text-xs ${selected ? "text-white/85" : "text-soil"}`}>{demo.caption}</span>
                  </button>
                );
              })}
            </div>
            <fieldset className="mt-6">
              <legend className="text-sm font-semibold">Or enter coordinates</legend>
              <div className="mt-3 grid grid-cols-2 gap-3">
                {([['Latitude', latitude, setLatitude], ['Longitude', longitude, setLongitude]] as const).map(([label, input, update]) => (
                  <label key={label} className="block text-sm">
                    {label}
                    <input type="number" step="any" inputMode="decimal" value={input} onChange={(event) => update(event.target.value)}
                      placeholder={label === 'Latitude' ? '27.8000' : '-83.0000'} aria-describedby="location-message" aria-invalid={complete && !valid}
                      className="mt-2 w-full min-w-0 rounded-lg border border-field/25 bg-white px-3 py-2.5 focus:border-field focus:outline-2 focus:outline-field/25" />
                  </label>
                ))}
              </div>
            </fieldset>
            <p id="location-message" aria-live="polite" className={`mt-3 text-sm ${complete && !valid ? 'text-clay' : 'text-soil'}`}>
              {complete && !valid ? 'Location must be in Florida: latitude 24.3–31.1, longitude −87.7–−79.9.' : 'Choose a location in Florida to analyze your land.'}
            </p>
            <button type="submit" disabled={!valid} className="mt-5 w-full rounded-lg bg-field px-5 py-3 font-semibold text-white transition-colors hover:bg-field/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field disabled:cursor-not-allowed disabled:opacity-40">Analyze my land</button>
          </form>
        </div>
      </main>
      <footer className="mx-auto w-full max-w-6xl px-5 pb-8 text-xs leading-relaxed text-soil sm:px-8">Data: USDA NRCS, NASA POWER, USDA NASS. General guidance only.</footer>
    </div>
  );
}
