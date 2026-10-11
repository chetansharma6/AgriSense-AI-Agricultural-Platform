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
        <h2 id="data-confidence-title" className="section-title">Data confidence and sources</h2>
        {confidence && <div className="mt-4 text-sm leading-relaxed">
          <p><span className="font-semibold">Confidence:</span> {formatDisplayText(confidence.level)} · {confidence.available_factors} of {confidence.total_factors} factors available{confidence.partial ? " · partial result" : ""}</p>
          {confidence.data_status && <p className="mt-1"><span className="font-semibold">Data:</span> {formatDisplayText(confidence.data_status)}</p>}
          {confidence.county_history_status && <p className="mt-1"><span className="font-semibold">County history:</span> {formatDisplayText(confidence.county_history_status)}</p>}
          {!!confidence.available_factor_names?.length && <p className="mt-1"><span className="font-semibold">Available:</span> {confidence.available_factor_names.map(formatDisplayText).join(", ")}</p>}
          {!!confidence.missing_factor_names?.length && <p className="mt-1"><span className="font-semibold">Missing:</span> {confidence.missing_factor_names.map(formatDisplayText).join(", ")}</p>}
        </div>}
        {sources.length > 0 && <details className="mt-4 rounded-xl bg-sand p-4">
          <summary className="min-h-11 cursor-pointer py-2 text-sm font-semibold text-field">View detailed source provenance</summary>
          <ul className="mt-2 grid gap-3 sm:grid-cols-2" aria-label="Data sources">{sources.map((source) => {
          const safeUrl = extensionUrl(source.url ?? null);
          return <li key={source.name} className="rounded-lg bg-sand p-4 text-sm">
            <p className="font-semibold">{safeUrl ? <a href={safeUrl} target="_blank" rel="noopener noreferrer" className="text-field underline underline-offset-4">{source.name}</a> : source.name}</p>
            <p className="mt-1">{formatDisplayText(source.data_status ?? source.status)} · {formatDisplayText(source.status)}</p>
            {source.data_period && <p className="mt-1">Period: {formatDisplayText(source.data_period)}</p>}
            {source.geographic_level && <p className="mt-1">Area: {formatDisplayText(source.geographic_level)}</p>}
            {source.detail && <p className="mt-1 text-ink/75">{formatDisplayText(source.detail)}</p>}
            {!!source.limitations?.length && <p className="mt-1 text-ink/75">Limits: {source.limitations.map(formatDisplayText).join("; ")}</p>}
          </li>;
        })}</ul>
        </details>}
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
