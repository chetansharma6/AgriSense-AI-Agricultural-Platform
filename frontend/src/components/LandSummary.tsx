"use client";

import { useId, useState } from "react";
import { describePh, formatTemperature, formatDays, formatMillimeters, formatFrostDate, formatDisplayText } from "@/lib/format";
import type { RecommendResponse } from "@/lib/types";

export function LandSummarySkeleton({ slow = false }: { slow?: boolean }) {
  return (
    <section className="card rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" role="status" aria-live="polite" aria-label="Loading land conditions">
      <h2 className="section-title">Your land at a glance</h2>
      <p className="mt-2 text-sm text-soil">Checking soil, climate and local harvest history…</p>
      {slow && <p className="mt-3 rounded-lg border border-sun/50 bg-sun/15 p-3 text-sm" role="status" aria-live="polite">Waking up the server… the first request after a quiet spell can take up to a minute. Thanks for waiting.</p>}
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="card animate-pulse rounded-lg bg-sand p-4 motion-reduce:animate-none">
            <div className="h-3 w-20 rounded bg-soil/15" />
            <div className="mt-4 h-7 w-3/4 rounded bg-soil/15" />
            <div className="mt-3 h-3 w-full rounded bg-soil/15" />
          </div>
        ))}
      </div>
    </section>
  );
}

export default function LandSummary({ response, place }: { response: RecommendResponse; place?: string }) {
  const [expanded, setExpanded] = useState(false);
  const detailsId = useId();
  const c = response.conditions;
  const frost = c?.frost_free_days;
  const rain = c?.annual_precip_mm;
  const drainage = c?.drainage;
  const drainageMeaning = drainage == null ? "Drainage information is unavailable."
    : /poorly drained/i.test(drainage) ? "Water can sit after heavy rain."
    : /well drained/i.test(drainage) ? "Water moves through the soil readily."
    : "Drainage affects how long soil stays wet.";
  const tiles = [
    { label: "Soil", value: c?.texture ?? "No data", extra: c?.soil_ph == null ? "pH: No data" : `pH ${describePh(c.soil_ph)}`, meaning: c?.texture == null ? "Soil texture information is unavailable." : "Texture and acidity affect crop fit." },
    { label: "Drainage", value: drainage?.toLowerCase() ?? "No data", meaning: drainageMeaning },
    { label: "Frost-free days", value: formatDays(frost ?? null), extra: c?.last_spring_frost ? `Last spring frost: ${formatFrostDate(c.last_spring_frost)}` : undefined, meaning: frost == null ? "Freeze information is unavailable." : "Time available for frost-sensitive crops." },
    { label: "Rainfall per year", value: formatMillimeters(rain ?? null), extra: rain == null ? undefined : `${(rain / 25.4).toFixed(1)} inches`, meaning: rain == null ? "Rainfall information is unavailable." : "Seasonal dry spells may still need irrigation." },
    { label: "Summer highs", value: formatTemperature(c?.avg_summer_high_c ?? null), meaning: c?.avg_summer_high_c == null ? "Summer temperatures are unavailable." : "Summer heat can stress cool-season crops." },
    { label: "Winter lows", value: formatTemperature(c?.avg_winter_low_c ?? null), meaning: c?.avg_winter_low_c == null ? "Winter temperatures are unavailable." : "Average lows do not rule out occasional freezes." },
  ];
  const cached = response.warnings?.find((warning) => warning.startsWith("Showing cached data"));
  const otherWarnings = response.warnings?.filter((warning) => warning !== cached) ?? [];
  const confidence = response.confidence;
  const sources = response.provenance?.sources ?? [];
  const sourceCount = new Set(sources.map((source) => source.name)).size;
  const dataStatus = confidence?.data_status ?? response.provenance?.mode;
  return (
    <div>
      {response.provenance?.mode === "demo" && <p className="mb-4 text-sm text-soil">Saved demo recommendations; soil and climate are not live measurements for your property.</p>}
      {cached && <p role="status" aria-live="polite" className="mb-4 rounded-lg border border-sun/60 bg-sun/20 p-4 font-semibold">{formatDisplayText(cached)}</p>}
      <section className="card rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="land-summary-title">
        <h2 id="land-summary-title" className="section-title">Your land at a glance</h2>
        <p className="mt-2 text-soil">{place || (response.location?.county ? `${response.location.county} County, Florida` : "County: No data")}</p>
        <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tiles.map((tile) => (
            <div key={tile.label} className="card min-w-0 rounded-lg bg-sand p-4">
              <dt className="text-sm font-semibold uppercase tracking-wide text-soil">{tile.label}</dt>
              <dd className="mt-2 text-xl font-semibold break-words">{tile.value}</dd>
              {tile.extra && <dd className="mt-1 text-sm">{tile.extra}</dd>}
              <dd className="mt-3 text-sm text-ink/75">{tile.meaning}</dd>
            </div>
          ))}
        </dl>
      </section>
      {otherWarnings.length > 0 && (
        <aside className="mt-4 rounded-lg border border-sun/50 bg-sun/15 p-4" aria-label="Data warnings">
          <p className="font-semibold">A note about the data</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {otherWarnings.map((warning, index) => <li key={index}>{formatDisplayText(warning)}</li>)}
          </ul>
        </aside>
      )}
      {(confidence || sources.length > 0) && <section className="card mt-4 rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="data-confidence-title">
        <h2 id="data-confidence-title" className="section-title">Data confidence &amp; sources</h2>
        <p className="mt-1 text-sm text-soil">See how much data supports these recommendations and where it comes from.</p>
        <ul className="mt-3 flex flex-wrap gap-2 text-sm" aria-label="Data coverage summary">
          <li className="rounded-full bg-mint px-3 py-1 font-semibold text-field">{confidence ? `${readableText(confidence.level)} data coverage` : "Data coverage unavailable"}</li>
          <li className="rounded-full bg-sand px-3 py-1">{confidence ? `${confidence.available_factors} of ${confidence.total_factors} factors available` : "Factor availability unknown"}</li>
          <li className="rounded-full bg-sand px-3 py-1">{statusLabel(dataStatus)}</li>
          <li className="rounded-full bg-sand px-3 py-1">{sourceCount} {sourceCount === 1 ? "source" : "sources"}</li>
          {confidence?.partial && <li className="rounded-full bg-sun/20 px-3 py-1">Partial result · some data is missing or limited</li>}
        </ul>
        <button type="button" aria-expanded={expanded} aria-controls={detailsId}
          onClick={() => setExpanded(!expanded)}
          className="mt-3 flex min-h-11 items-center gap-2 text-sm font-semibold text-field motion-reduce:transition-none">
          {expanded ? "Hide source details" : "View source details"}
          <span aria-hidden="true" className={`inline-block transition-transform duration-200 motion-reduce:transition-none ${expanded ? "rotate-180" : ""}`}>⌄</span>
        </button>
        <div id={detailsId} inert={!expanded} aria-hidden={!expanded}
          className={`grid transition-[grid-template-rows,opacity] duration-200 ease-in-out motion-reduce:transition-none ${expanded ? "grid-rows-[1fr] opacity-100" : "grid-rows-[0fr] opacity-0"}`}>
          <div className="min-h-0 overflow-hidden">
            {confidence && <div className="mt-3 border-t border-field/15 pt-4 text-sm leading-relaxed">
              <p><span className="font-semibold">County history:</span> {confidence.county_history_status ? readableText(confidence.county_history_status) : "Availability unknown"}</p>
              <p className="mt-1"><span className="font-semibold">Available factors:</span> {confidence.available_factor_names?.length ? confidence.available_factor_names.map(readableText).join(", ") : "None reported"}</p>
              <p className="mt-1"><span className="font-semibold">Missing factors:</span> {confidence.missing_factor_names?.length ? confidence.missing_factor_names.map(readableText).join(", ") : "None reported"}</p>
              {!!confidence.notes?.length && <ul className="mt-2 list-disc space-y-1 pl-5" aria-label="Data notes">{confidence.notes.map((note, index) => <li key={index}>{readableText(note)}</li>)}</ul>}
            </div>}
            {sources.length > 0 && <ul className="mt-4 grid gap-3 sm:grid-cols-2" aria-label="Data sources">{sources.map((source, index) => {
              const safeUrl = extensionUrl(source.url ?? null);
              const sourceDataStatus = source.data_status ?? source.status;
              return <li key={`${source.name}-${index}`} className="min-w-0 rounded-lg bg-sand p-4 text-sm break-words">
                <p className="font-semibold">{safeUrl ? <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="text-field underline underline-offset-4">{source.name}</a> : source.name}</p>
                <p className="mt-1">{statusLabel(sourceDataStatus)}{source.status !== sourceDataStatus && !(source.status === "saved" && ["demo", "cached"].includes(sourceDataStatus)) ? ` · Source: ${readableText(source.status)}` : ""}</p>
                {source.data_period && <p className="mt-1">Reporting period: {readableText(source.data_period)}</p>}
                {source.geographic_level && <p className="mt-1">Geographic coverage: {readableText(source.geographic_level)}</p>}
                {source.detail && <p className="mt-1 text-ink/75">{readableText(source.detail)}</p>}
                {!!source.limitations?.length && <p className="mt-1 text-ink/75">Limitations: {source.limitations.map(readableText).join("; ")}</p>}
              </li>;
            })}</ul>}
            {response.provenance?.fawn_station && <p className="mt-3 text-sm text-soil">Weather station: {response.provenance.fawn_station.name} · {response.provenance.fawn_station.distance_km} km away</p>}
          </div>
        </div>
      </section>}
    </div>
  );
}

function extensionUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
  } catch { return null; }
}

/** Presentation only: preserve the original factor and provenance values. */
function readableText(value: string): string {
  const labels: Record<string, string> = {
    soil_ph: "Soil pH", drainage: "Drainage", season_temp: "Season temperature",
    frost_risk: "Freeze risk", rainfall: "Rainfall", local_history: "Local harvest history",
  };
  const text = formatDisplayText(value).replace(/\b(soil_ph|drainage|season_temp|frost_risk|rainfall|local_history)\b/g,
    (key) => labels[key]).replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function statusLabel(value: string | undefined): string {
  const labels: Record<string, string> = {
    live: "Live data", demo: "Saved demo data", cached: "Saved cached data",
    saved: "Saved data", stale: "Older saved data", failed: "Data unavailable (source failed)",
    missing: "Missing data", unavailable: "Data unavailable", estimated: "Estimated data",
    fallback: "Fallback data", withheld: "Withheld data",
  };
  return value ? labels[value] ?? readableText(value) : "Data status unknown";
}
