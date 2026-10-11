"use client";

import Image from "next/image";
import plantCityExample from "@/mocks/plant_city.json";
import { stats } from "@/content/stats";
import styles from "./home.module.css";
import { useRouter } from "next/navigation";
import { useState, useEffect, type FormEvent } from "react";
import LocationSearch from "@/components/LocationSearch";
import MapLoader from "@/components/MapLoader";

const exampleCrop = plantCityExample.recommend.crops.find((crop) => crop.id === "strawberry")!;

const demos = [
  { name: "Marianna", caption: "Panhandle row crops", lat: 30.80, lon: -85.25 },
  { name: "Hastings", caption: "Potato country", lat: 29.71, lon: -81.50 },
  { name: "Plant City", caption: "Strawberry capital", lat: 28.03, lon: -82.15 },
  { name: "Belle Glade", caption: "Everglades muck", lat: 26.68, lon: -80.68 },
];

export default function Home() {
  const router = useRouter();
  useEffect(() => { document.title = "AgriSense · Find the crops your Florida land is built for"; }, []);
  const [photoReady, setPhotoReady] = useState(false);
  const [latitude, setLatitude] = useState("");
  const [longitude, setLongitude] = useState("");
  const [acreage, setAcreage] = useState("");
  const acres = acreage.trim() === "" ? undefined : Number(acreage);
  const validAcres = acres === undefined || Number.isFinite(acres) && acres >= 0.1 && acres <= 10000;
  const [place, setPlace] = useState("");
  const lat = Number(latitude);
  const lon = Number(longitude);
  const complete = latitude.trim() !== "" && longitude.trim() !== "";
  const finite = complete && Number.isFinite(lat) && Number.isFinite(lon);
  const valid = finite && lat >= 24.3 && lat <= 31.1 && lon >= -87.7 && lon <= -79.9;
  const value = finite ? { lat, lon } : null;

  function selectPoint(lat: number, lon: number, label = "") {
    setPlace(label || demos.find((demo) => demo.lat.toFixed(4) === lat.toFixed(4) && demo.lon.toFixed(4) === lon.toFixed(4))?.name || "");
    setLatitude(lat.toFixed(4));
    setLongitude(lon.toFixed(4));
  }

  const selectedLocation = valid ? (place || `${lat.toFixed(4)}, ${lon.toFixed(4)}`) : "";

  function analyze(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (valid && validAcres) {
      const query = new URLSearchParams({ lat: lat.toFixed(4), lon: lon.toFixed(4) });
      if (acres !== undefined) query.set("acres", String(acres));
      if (place) query.set("place", place);
      router.push(`/results?${query}`);
    }
  }

  return (
    <div className="min-h-screen">

      <main className="mb-8">
        <section className={styles.hero} aria-labelledby="hero-title">
          <div className={styles.meadow} aria-hidden="true" />
          <div className="relative mx-auto max-w-6xl px-4 py-8 sm:px-8 sm:py-10 lg:py-14">
            <div className={styles.intro}>
              <div className={styles.heroCopy}>
                <p className={styles.eyebrow}><span aria-hidden="true">✳</span> Florida land. Local possibilities.</p>
                <h1 id="hero-title" className={styles.headline}>Know what your Florida land is built to <em>grow.</em></h1>
                <p className={styles.description}>AgriSense helps small farms pick crops that fit their soil, season and local market.</p>
                <a href="#land-analysis" className={styles.cta}>Explore your land <span aria-hidden="true">↗</span></a>
                <p className={styles.heroNote}>Florida focused · 13 crops · Explainable scores</p>
              </div>
              <div className={styles.farmVisual}>
                <Image src="/hero-farm.jpg" fill sizes="(max-width: 1024px) 90vw, 480px" priority
                  alt="Rows of crops on a Florida farm" className="object-cover"
                  style={{ opacity: photoReady ? 1 : 0 }}
                  onLoad={() => setPhotoReady(true)} onError={() => setPhotoReady(false)} />
                <div className={styles.photoCaption}><span aria-hidden="true">↗</span><div>Rooted in your location<small>Soil, climate & local harvest history</small></div></div>
              </div>
            </div>
            <section id="land-analysis" aria-labelledby="analysis-title" className={styles.analysis}>
              <div className={styles.analysisGrid}>
                <div className="min-w-0">
                  <p className={styles.eyebrow}>Your next harvest starts here</p>
                  <h2 id="analysis-title" className={styles.analysisTitle}>Start with your land.</h2>
                  <p className={styles.analysisDescription}>Enter your Florida location and acreage to discover crops suited to your land.</p>
                  <ul className={styles.factorLabels} aria-label="What AgriSense considers">{["Soil", "Climate", "Local history", "Land size"].map((label) => <li key={label}>{label}</li>)}</ul>
                  <div className={styles.landControls}>
                    <div className={styles.locationSearch}><LocationSearch selectedLabel={selectedLocation ? `Selected: ${selectedLocation}` : ""} onSelect={(result) => {
                      selectPoint(result.lat, result.lon, result.label);
                    }} /></div>
                    <label className="block text-sm font-semibold" htmlFor="acreage">How much land? (acres)
                      <input id="acreage" type="number" min="0.1" max="10000" step="any" inputMode="decimal" placeholder="Optional" value={acreage}
                        onChange={(event) => setAcreage(event.target.value)} aria-invalid={!validAcres} aria-describedby="acreage-help"
                        className={styles.landInput} />
                    </label>
                  </div>
                  <p id="acreage-help" className={`${styles.acreageHelp} mt-2 text-sm`} aria-live="polite">{validAcres ? 'Optional: type 0.1–10,000 usable growing acres. Land size adjusts rankings and advice.' : 'Enter a number from 0.1 to 10,000 acres, or leave blank.'}</p>
                  {acres !== undefined && validAcres && acres < 1 && <p className="mt-3 text-sm leading-relaxed">Small lots favor crops suited to garden beds. Check spacing and usable growing area with <a href="https://gardeningsolutions.ifas.ufl.edu/" target="_blank" rel="noopener noreferrer" className="underline underline-offset-4">UF/IFAS gardening guides.</a></p>}
                  <form onSubmit={analyze} className="mt-5">
                    <h2 className="text-xl font-semibold">Try a demo farm</h2>
                    <div className="mt-4 grid grid-cols-2 gap-3">
                      {demos.map((demo) => {
                        const selected = latitude === demo.lat.toFixed(4) && longitude === demo.lon.toFixed(4);
                        return (
                          <button key={demo.name} type="button" onClick={() => selectPoint(demo.lat, demo.lon, demo.name)} aria-pressed={selected}
                            className={styles.demoCard}>
                            <span className="block text-sm font-semibold">{demo.name}</span>
                            <span className={styles.demoCaption}>{demo.caption}</span>
                          </button>
                        );
                      })}
                    </div>
                    <details className={styles.coordinates}>
                      <summary className="min-h-11 cursor-pointer py-3 text-sm font-semibold">Enter coordinates instead</summary>
                      <fieldset className="mt-2">
                        <legend className="sr-only">Florida latitude and longitude</legend>
                        <div className="mt-3 grid grid-cols-2 gap-3">
                          {([['Latitude', latitude, setLatitude], ['Longitude', longitude, setLongitude]] as const).map(([label, input, update]) => (
                            <label key={label} className="block text-sm">
                              {label}
                              <input type="number" step="any" inputMode="decimal" value={input} onChange={(event) => { update(event.target.value); setPlace(""); }}
                                placeholder={label === 'Latitude' ? '27.8000' : '-83.0000'} aria-describedby="location-message" aria-invalid={complete && !valid}
                                className={styles.landInput} />
                            </label>
                          ))}
                        </div>
                      </fieldset>
                    </details>
                    <div className={styles.selectionConfirmation} aria-live="polite">{valid && <p><span aria-hidden="true">✓ </span><strong>{selectedLocation}</strong><br />Location selected · {validAcres ? "Ready to analyze" : "Check acreage to continue"}</p>}</div>
                    <p id="location-message" aria-live="polite" className={styles.locationMessage}>
                      {complete && !valid ? 'Location must be in Florida: latitude 24.3–31.1, longitude −87.7–−79.9.' : valid ? validAcres ? `Ready to analyze: ${selectedLocation}.` : `Selected: ${selectedLocation}. Check acreage to continue.` : 'Choose a location in Florida to analyze your land.'}
                    </p>
                    <button type="submit" disabled={!valid || !validAcres} className={styles.analyzeButton}>{valid && place ? `Analyze ${place}` : valid ? "Analyze selected location" : "Analyze my land"} <span aria-hidden="true">↗</span></button>
                  </form>
                </div>
                <section className={`${styles.mapPanel} min-w-0`} aria-label="Farm location map">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-2"><h3 className={styles.mapTitle}>Your Florida starting point</h3><span className={styles.mapBadge}>{valid ? `✓ ${selectedLocation}` : "Select a spot"}</span></div>
                  <div className={styles.mapFrame}>
                    <MapLoader value={value} onChange={selectPoint} demoPins={demos} />
                  </div>
                  <p className="mt-3 text-sm">{valid ? `Selected: ${selectedLocation}. Click the map to change your location.` : "Click the map or choose a demo farm to get started."}</p>
                </section>
              </div>
            </section>
            <section className={styles.examplePreview} aria-labelledby="example-heading">
              <div>
                <p className={styles.eyebrow}>See what AgriSense can discover</p>
                <h2 id="example-heading">An example from Plant City, Florida</h2>
                <p className="mt-3 text-sm text-soil">Saved demo data · An illustration of the report you can explore, not live measurements for your land.</p>
              </div>
              <article className={styles.exampleCard}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <h3>{exampleCrop.name}</h3>
                  <p className={styles.exampleScore}><strong>{exampleCrop.score}</strong> / 100 <span>saved suitability score</span></p>
                </div>
                <p className="mt-3 text-sm leading-relaxed">The saved winter climate and local growing history are strong matches for strawberries.</p>
                <p className="mt-2 text-sm text-soil">{exampleCrop.season_label}</p>
                <p className="mt-2 text-sm text-soil">Check before planting: {exampleCrop.flags[0]}</p>
                <a href="/results?lat=28.0300&lon=-82.1500&place=Plant+City" className="mt-4 inline-flex min-h-11 items-center gap-3 font-semibold text-field underline underline-offset-4">Explore this example <span aria-hidden="true">↗</span></a>
                <p className="mt-2 text-xs text-soil">Results use the existing demo workflow; current data may differ from this saved example.</p>
              </article>
            </section>
            <div className={styles.statsIntro}><p className={styles.eyebrow}>A state of possibility</p><h2>Small farms. A growing future.</h2></div>
            <div className="mt-5 grid gap-4 md:grid-cols-3" aria-label="Florida farm statistics">
              {stats.map((stat) => (
                <article key={stat.value} className={`${styles.statCard} flex min-w-0 flex-col rounded-2xl p-5 sm:p-6`}>
                  <p className="text-4xl font-bold tracking-tight">{stat.value}</p>
                  <p className="mt-2 text-base font-medium leading-relaxed">{stat.label}</p>
                  <a href={stat.sourceUrl} target="_blank" rel="noopener"
                    className="mt-3 inline-flex min-h-11 items-center text-xs leading-relaxed underline underline-offset-4 hover:decoration-2">
                    {stat.source}
                  </a>
                </article>
              ))}
            </div>
          </div>
        </section>
      </main>

    </div>
  );
}
