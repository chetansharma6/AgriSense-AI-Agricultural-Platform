import { describePh, formatTemperature } from "@/lib/format";
import type { RecommendResponse } from "@/lib/types";

export function LandSummarySkeleton() {
  return (
    <section className="rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" role="status" aria-label="Loading land conditions">
      <h2 className="text-2xl font-semibold">Your land at a glance</h2>
      <p className="mt-2 text-sm text-soil">Checking soil, climate and local harvest history…</p>
      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => (
          <div key={i} className="animate-pulse rounded-lg bg-sand p-4 motion-reduce:animate-none">
            <div className="h-3 w-20 rounded bg-soil/15" />
            <div className="mt-4 h-7 w-3/4 rounded bg-soil/15" />
            <div className="mt-3 h-3 w-full rounded bg-soil/15" />
          </div>
        ))}
      </div>
    </section>
  );
}

export default function LandSummary({ response }: { response: RecommendResponse }) {
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
    { label: "Drainage", value: drainage ?? "No data", meaning: drainageMeaning },
    { label: "Frost-free days", value: frost == null ? "No data" : `${frost} days`, extra: c?.last_spring_frost ? `Last spring frost: ${c.last_spring_frost}` : undefined, meaning: frost == null ? "Freeze information is unavailable." : "Time available for frost-sensitive crops." },
    { label: "Rainfall per year", value: rain == null ? "No data" : `${rain.toLocaleString("en-US")} mm`, extra: rain == null ? undefined : `${(rain / 25.4).toFixed(1)} inches`, meaning: rain == null ? "Rainfall information is unavailable." : "Seasonal dry spells may still need irrigation." },
    { label: "Summer highs", value: formatTemperature(c?.avg_summer_high_c ?? null), meaning: c?.avg_summer_high_c == null ? "Summer temperatures are unavailable." : "Summer heat can stress cool-season crops." },
    { label: "Winter lows", value: formatTemperature(c?.avg_winter_low_c ?? null), meaning: c?.avg_winter_low_c == null ? "Winter temperatures are unavailable." : "Average lows do not rule out occasional freezes." },
  ];
  const cached = response.warnings?.find((warning) => warning.startsWith("Showing cached data"));
  const otherWarnings = response.warnings?.filter((warning) => warning !== cached) ?? [];
  return (
    <div>
      {cached && <p role="status" className="mb-4 rounded-lg border border-sun/60 bg-sun/20 p-4 font-semibold">{cached}</p>}
      <section className="rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="land-summary-title">
        <h2 id="land-summary-title" className="text-2xl font-semibold">Your land at a glance</h2>
        <p className="mt-2 text-soil">{response.location?.county ? `${response.location.county} County, Florida` : "County: No data"}</p>
        <dl className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tiles.map((tile) => (
            <div key={tile.label} className="min-w-0 rounded-lg bg-sand p-4">
              <dt className="text-xs font-semibold uppercase tracking-wide text-soil">{tile.label}</dt>
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
            {otherWarnings.map((warning, index) => <li key={index}>{warning}</li>)}
          </ul>
        </aside>
      )}
    </div>
  );
}
