"use client";

import { useMemo, useState } from "react";
import { acreBand, applyFilters, contextFromCrop, FILTERS, phNote, recommendFertilizers, type FilterId } from "@/lib/fertilizer";
import type { CropDetail } from "@/lib/types";

type Explain = { state: "idle" | "loading" | "done" | "unavailable"; text: Record<string, string> };

function safeUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "https:" ? url.href : null;
  } catch { return null; }
}

export default function FertilizerRecommendations({ crop, acres }: { crop: CropDetail; acres?: number }) {
  const [selected, setSelected] = useState<FilterId[]>([]);
  const [explain, setExplain] = useState<Explain>({ state: "idle", text: {} });
  const ctx = useMemo(() => contextFromCrop(crop, acres), [crop, acres]);
  const all = useMemo(() => recommendFertilizers(ctx), [ctx]);
  const shown = useMemo(() => applyFilters(all, selected), [all, selected]);
  const note = phNote(ctx);
  const cropName = crop.name ?? "this crop";

  const toggle = (id: FilterId) => setSelected((cur) => cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]);

  async function loadExplanations() {
    setExplain({ state: "loading", text: {} });
    try {
      const response = await fetch("/api/fertilizer-explain", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ crop: { id: crop.id, nutrient_plan: { n_lb_per_acre: crop.nutrient_plan?.n_lb_per_acre ?? null }, conditions: crop.conditions, county: crop.location?.county ?? null }, acres }),
      });
      const body: unknown = response.ok ? await response.json() : null;
      const text = (body as { explanations?: Record<string, string> } | null)?.explanations;
      const ok = !!text && Object.keys(text).length > 0;
      setExplain({ state: ok ? "done" : "unavailable", text: ok ? text : {} });
    } catch { setExplain({ state: "unavailable", text: {} }); }
  }

  return (
    <section className="card rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="fertilizers">
      <h2 id="fertilizers" className="section-title">Recommended Fertilizers</h2>
      <p className="mt-2 text-soil">Explore fertilizer options suited to your crop, land size, and available soil information.</p>
      <p className="mt-2 rounded-lg bg-mint px-3 py-2 text-sm" data-testid="soil-data-status">
        No soil-test results (nitrogen, phosphorus, potassium) are available for your property, so AgriSense does not estimate deficiencies or amounts.
        {acres === undefined ? " Acreage was not provided, so land-size practicality is not factored in." : ` Ranking considers your ${acres}-acre (${acreBand(acres)}) land size.`}
      </p>
      {note && <p className="mt-2 text-sm text-clay">{note}</p>}

      <div role="group" aria-label="Fertilizer filters" className="mt-5 flex flex-wrap gap-2">
        <button type="button" aria-pressed={selected.length === 0} onClick={() => setSelected([])}
          className={`min-h-11 rounded-full border px-4 text-sm font-semibold transition-colors motion-reduce:transition-none ${selected.length === 0 ? "border-field bg-field text-white" : "border-field/30 bg-white/60 text-field hover:bg-leaf/15"}`}>All</button>
        {FILTERS.map((f) => {
          const on = selected.includes(f.id);
          return <button key={f.id} type="button" aria-pressed={on} title={f.hint} onClick={() => toggle(f.id)}
            className={`min-h-11 rounded-full border px-4 text-sm font-semibold transition-colors motion-reduce:transition-none ${on ? "border-field bg-field text-white" : "border-field/30 bg-white/60 text-field hover:bg-leaf/15"}`}>{f.label}</button>;
        })}
      </div>
      {selected.length > 0 && <ul className="mt-3 space-y-1 text-sm text-soil" aria-label="How the selected filters work">
        {FILTERS.filter((f) => selected.includes(f.id)).map((f) => <li key={f.id}><span className="font-semibold">{f.label}:</span> {f.basis}</li>)}
      </ul>}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-soil" role="status" aria-live="polite">Showing {shown.length} of {all.length} options for {cropName}{selected.length > 1 ? " matching all selected filters" : ""}.</p>
        {explain.state === "idle" && <button type="button" onClick={loadExplanations} aria-describedby="fert-ai-note" className="no-print min-h-11 rounded-lg border border-field px-4 text-sm font-semibold text-field hover:bg-leaf/15">Explain with AI</button>}
        {explain.state === "loading" && <span className="text-sm text-soil" role="status">Writing explanations…</span>}
        {explain.state === "done" && <span className="text-sm text-soil" role="status">AI explanations added. Rankings are unchanged.</span>}
      </div>
      {explain.state === "unavailable" && <p className="mt-2 text-sm text-soil" role="alert">AI explanations are unavailable right now. The recommendations below are unaffected.</p>}

      {shown.length === 0 ? (
        <p className="mt-5 rounded-xl border border-sun/40 bg-sun/15 p-4 text-sm">No fertilizer category matches every selected filter for {cropName}. Try removing a filter.</p>
      ) : (
        <ul className="mt-5 grid gap-4 lg:grid-cols-2">
          {shown.map((f) => (
            <li key={f.id} className="min-w-0">
              <article className="card h-full rounded-xl border border-field/15 bg-sand p-5 transition-shadow motion-reduce:transition-none" aria-labelledby={`fert-${f.id}`}>
                <div className="flex items-start justify-between gap-3">
                  <h3 id={`fert-${f.id}`} className="text-lg font-semibold">{f.name}</h3>
                  <span className="shrink-0 rounded-full bg-sun/40 px-3 py-1 text-sm font-semibold" title="AgriSense estimate of relative cost, not a retail price">{f.cost} <span className="sr-only">approximate relative cost category (estimate, not a price)</span></span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs font-semibold">
                  {FILTERS.filter((x) => f.traits[x.id]).map((x) => <span key={x.id} className="rounded-full bg-mint px-2.5 py-1 text-field">{x.label}</span>)}
                </div>
                <p className="mt-3 text-sm leading-relaxed">{f.whyRecommended}</p>
                {f.conditional && <p className="mt-2 rounded-lg bg-sun/20 px-3 py-2 text-sm"><span className="font-semibold">Conditional: </span>{f.conditional}</p>}
                <dl className="mt-3 space-y-3 text-sm leading-relaxed">
                  <div><dt className="font-semibold">Best for</dt><dd><ul className="list-disc pl-5">{f.bestFor.map((b) => <li key={b}>{b}</li>)}</ul></dd></div>
                  <div><dt className="font-semibold">Potential drawbacks</dt><dd><ul className="list-disc pl-5">{f.drawbacks.map((d) => <li key={d}>{d}</li>)}</ul></dd></div>
                  <div><dt className="font-semibold">Why AgriSense recommends this</dt><dd><ul className="list-disc pl-5">{f.whyAgriSense.map((r) => <li key={r}>{r}</li>)}</ul></dd></div>
                </dl>
                <details className="mt-3 rounded-lg border border-field/15 bg-white/50 px-3">
                  <summary className="flex min-h-11 cursor-pointer items-center text-sm font-semibold text-field">Nutrients, cost, environment and sources</summary>
                  <dl className="space-y-3 pb-3 text-sm leading-relaxed">
                    <div><dt className="font-semibold">Nutrient information</dt><dd>{f.npk}</dd></div>
                    <div><dt className="font-semibold">Relative cost ({f.cost}, estimate)</dt><dd>{f.costBasis} Not a retail price; actual cost varies by product, store and season.</dd></div>
                    <div><dt className="font-semibold">Environmental considerations</dt><dd>{f.environment}</dd></div>
                  </dl>
                  {f.sources.length > 0 && <ul className="mt-3 space-y-1 text-sm" aria-label={`Sources for ${f.name}`}>{f.sources.map((src) => {
                  const url = safeUrl(src.url);
                  return url ? <li key={src.url}><a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-11 items-center break-words text-field underline underline-offset-4">{src.title}</a><span className="block text-soil">Supports: {src.supports}.</span></li> : null;
                })}</ul>}
                </details>
                {explain.text[f.id] && <p className="mt-3 rounded-lg bg-mint px-3 py-2 text-sm leading-relaxed"><span className="font-semibold">AI explanation:</span> {explain.text[f.id]}</p>}
                </article>
            </li>
          ))}
        </ul>
      )}
      <p id="fert-ai-note" className="sr-only">AI only explains the listed options in plain language. It does not change the ranking.</p>
      <p className="mt-5 text-sm leading-relaxed text-soil">Recommendations are based on available agricultural data. A soil test is recommended before selecting fertilizer quantities or application rates. Cost categories ($ to $$$) are AgriSense&apos;s qualitative estimates of relative cost per unit of nutrient, not retail prices or quotes. No brands, sponsorships or paid placement are involved.</p>
    </section>
  );
}
