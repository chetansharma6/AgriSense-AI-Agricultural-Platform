import { formatDisplayText } from "@/lib/format";
import type { Confidence, Provenance } from "@/lib/types";

export default function DataStatusChips({ provenance, confidence }: { provenance?: Provenance | null; confidence?: Confidence | null }) {
  const sources = provenance?.sources ?? [];
  const statuses = new Set(sources.map((source) => source.data_status ?? source.status));
  const partial = confidence?.partial || (confidence != null && confidence.available_factors < confidence.total_factors) || sources.some((source) => source.status === "failed");
  const labels = [
    provenance?.mode === "demo" ? "Demo data" : null,
    statuses.has("cached") ? "Cached data" : null,
    statuses.has("live") && provenance?.mode !== "demo" ? "Live data" : null,
    partial ? "Partial data" : null,
  ].filter((label): label is string => Boolean(label));
  const demo = provenance?.mode === "demo";
  const explanation = demo ? "Saved demo recommendations; these are not live measurements for your property."
    : partial ? "Some evidence is missing; this score uses the available data."
    : statuses.has("cached") ? "Includes saved source data; these are not current property measurements."
    : statuses.has("live") ? "Retrieved source data; suitability is an estimate, not a property measurement."
    : "Data availability is unreported; live measurements are not verified.";
  return <div aria-label="Data status"><div className="flex flex-wrap gap-2">
    {labels.map((label) => <span key={label} className="rounded-full border border-field/20 bg-mint px-3 py-1 text-xs font-semibold text-field">{formatDisplayText(label)}</span>)}
    </div><p className="mt-2 text-xs leading-relaxed text-soil">{explanation}</p>
  </div>;
}
