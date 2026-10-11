import { formatDisplayText } from "@/lib/format";
import type { Confidence, Provenance } from "@/lib/types";

export default function DataStatusChips({ provenance, confidence }: { provenance?: Provenance | null; confidence?: Confidence | null }) {
  const sources = provenance?.sources ?? [];
  const statuses = new Set(sources.map((source) => source.data_status ?? source.status));
  const partial = confidence?.partial || sources.some((source) => source.status === "failed");
  const labels = [
    provenance?.mode === "demo" ? "Demo data" : null,
    statuses.has("cached") ? "Cached data" : null,
    statuses.has("live") && provenance?.mode !== "demo" ? "Live data" : null,
    partial ? "Partial data" : null,
  ].filter((label): label is string => Boolean(label));
  if (!labels.length) return null;
  return <div className="flex flex-wrap gap-2" aria-label="Data status">
    {labels.map((label) => <span key={label} className="rounded-full border border-field/20 bg-mint px-3 py-1 text-xs font-semibold text-field">{formatDisplayText(label)}</span>)}
  </div>;
}
