"use client";

import Link from "next/link";
import Image from "next/image";
import { stats } from "@/content/stats";
import styles from "./home.module.css";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import LocationSearch from "@/components/LocationSearch";
import MapLoader from "@/components/MapLoader";

const demos = [
  { name: "Marianna", caption: "Panhandle row crops", lat: 30.80, lon: -85.25 },
  { name: "Hastings", caption: "Potato country", lat: 29.71, lon: -81.50 },
  { name: "Plant City", caption: "Strawberry capital", lat: 28.03, lon: -82.15 },
  { name: "Belle Glade", caption: "Everglades muck", lat: 26.68, lon: -80.68 },
];

export default function Home() {
  const router = useRouter();
  const [photoReady, setPhotoReady] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [place, setPlace] = useState("");
  const lat = Number(latitude);
  const lon = Number(longitude);
  const complete = latitude.trim() !== "" && longitude.trim() !== "";
  const finite = complete && Number.isFinite(lat) && Number.isFinite(lon);
  const valid = finite && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const value = finite ? { lat, lon } : null;

  function selectPoint(lat: number, lon: number) {
    setPlace("");
    setLatitude(lat.toFixed(4));
    setLongitude(lon.toFixed(4));
  }

  function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (valid) {
      const query = new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4) });
      if (place) query.set("place", place);
      router.push(`/results?${query}`);
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-field/15">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
          <Link href="/" className="inline-flex min-h-11 items-center text-2xl font-bold tracking-tight text-field">AgriSense</Link>
          <Link href="/about" className="inline-flex min-h-11 items-center text-sm font-medium underline decoration-field/30 underline-offset-4 hover:text-field">About the data</Link>
        </div>
      </header>
      <main className="mb-8">
        <section className={styles.hero} aria-labelledby="hero-title">
          <Image src="/hero-farm.jpg" fill sizes="100vw" priority
            alt="Rows of crops on a Florida farm" className="object-cover"
            style={{ opacity: photoReady ? 1 : 0 }}
            onLoad={() => setPhotoReady(true)} onError={() => setPhotoReady(false)} />
          <div className={styles.overlay} aria-hidden="true" />
          <div className="relative mx-auto max-w-6xl px-4 py-8 sm:px-8 sm:py-10 lg:py-14">
            <div className={`${styles.glass} rounded-2xl p-5 sm:p-8`}>
              <div className="grid min-w-0 items-center gap-8 lg:grid-cols-2 lg:gap-10">
                <div className="min-w-0">
                  <p className="mb-3 text-sm font-semibold uppercase tracking-widest">Florida land. Local possibilities.</p>
                  <h1 id="hero-title" className="text-4xl leading-tight font-semibold tracking-tight sm:text-5xl">Know what your Florida land is built to grow.</h1>
                  <p className="mt-5 text-base leading-relaxed sm:text-lg">Pick a spot on the map. We check soil, climate and local harvest history, then rank 13 Florida crops by how well they fit.</p>
                  <div className="mt-6">
                    <LocationSearch selectedLabel={place} onSelect={(result) => {
                      selectPoint(result.lat, result.lon);
                      setPlace(result.label);
                    }} />
                  </div>
                  <form onSubmit={analyze} className="mt-5">
                    <h2 className="text-xl font-semibold">Try a demo farm</h2>
                    <div className="mt-4 grid grid-cols-2 gap-3">
                      {demos.map((demo) => {
                        const selected = latitude === demo.lat.toFixed(4) && longitude === demo.lon.toFixed(4);
                        return (
                          <button key={demo.name} type="button" onClick={() => selectPoint(demo.lat, demo.lon)} aria-pressed={selected}
                            className={`rounded-lg border p-3 min-h-11 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field ${selected ? "border-field bg-field text-white" : "border-field/20 bg-sand/50 hover:border-field hover:bg-leaf/15"}`}>
                            <span className="block text-sm font-semibold">{demo.name}</span>
                            <span className={`mt-1 block text-sm ${selected ? "text-white/85" : "text-ink"}`}>{demo.caption}</span>
                          </button>
                        );
                      })}
                    </div>
                    <details className="mt-6">
                      <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">Enter coordinates instead</summary>
                      <fieldset className="mt-2">
                        <legend className="text-sm font-semibold">Or enter coordinates</legend>
                        <div className="mt-3 grid grid-cols-2 gap-3">
                          {([['Latitude', latitude, setLatitude], ['Longitude', longitude, setLongitude]] as const).map(([label, input, update]) => (
                            <label key={label} className="block text-sm">
                              {label}
                              <input type="number" step="any" inputMode="decimal" value={input} onChange={(event) => { update(event.target.value); setPlace(""); }}
                                placeholder={label === 'Latitude' ? '27.8000' : '-83.0000'} aria-describedby="location-message" aria-invalid={complete && !valid}
                                className="mt-2 w-full min-w-0 rounded-lg border border-field/25 bg-white px-3 min-h-11 py-2.5 focus:border-field focus:outline-2 focus:outline-field" />
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    </details>
                    <p id="location-message" aria-live="polite" className={`mt-3 text-sm ${complete && !valid ? 'font-semibold text-ink' : 'text-ink'}`}>
                      {complete && !valid ? 'Location must be in Florida: latitude 24.3–31.1, longitude −87.7–−79.9.' : 'Choose a location in Florida to analyze your land.'}
                    </p>
                    <button type="submit" disabled={!valid} className="mt-5 min-h-11 w-full rounded-lg bg-field px-5 py-3 font-semibold text-white transition-colors hover:bg-field/90 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-field disabled:cursor-not-allowed disabled:opacity-40">Analyze my land</button>
                  </form>
                </div>
                <section className="min-w-0" aria-label="Farm location map">
                  <div className="overflow-hidden rounded-xl border border-field/20">
                    <MapLoader value={value} onChange={selectPoint} demoPins={demos} />
                  </div>
                  <p className="mt-3 text-sm">Click the map or choose a demo farm to get started.</p>
                </section>
              </div>
            </div>
            <div className="mt-5 grid gap-4 md:grid-cols-3" aria-label="Florida farm statistics">
              {stats.map((stat) => (
                <article key={stat.value} className={`${styles.glass} flex min-w-0 flex-col rounded-2xl p-5 sm:p-6`}>
                  <p className="text-4xl font-bold tracking-tight">{stat.value}</p>
                  <h2 className="mt-2 text-base font-medium leading-relaxed">{stat.label}</h2>
                  <a href={stat.sourceUrl} target="_blank" rel="noopener"
                    className="mt-3 inline-flex min-h-11 items-center text-xs leading-relaxed underline underline-offset-4 hover:decoration-2">
                    {stat.source}
                  </a>
                </article>
              ))}
            </div>
            <p className={`${styles.glass} mt-5 rounded-2xl px-5 py-4 text-base leading-relaxed sm:px-8`}>AgriSense helps small farms pick crops that fit their soil, season and local market.</p>
          </div>
        </section>
      </main>
      <footer className="mx-auto w-full max-w-6xl px-5 pb-8 text-sm leading-relaxed text-soil sm:px-8">Data: USDA NRCS, NASA POWER, USDA NASS. General guidance only.</footer>
    </div>
  );
}
