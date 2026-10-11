import { formatDisplayText } from "@/lib/format";
import type { CropDetail } from "@/lib/types";

export default function DecisionSnapshot({ crop }: { crop: CropDetail }) {
  const firstAction = crop.action_plan?.first_test ?? crop.action_plan?.check_before_planting ?? "Review the available soil and climate information before planting.";
  const risk = crop.risk_notes?.[0] ?? crop.action_plan?.major_risk ?? crop.flags?.[0] ?? "No specific risk note is available.";
  const water = crop.water_plan ? `${crop.water_plan.season_status}: ${crop.water_plan.note}` : "Water status is unavailable; confirm irrigation capacity before planting.";
  const fit = crop.scale?.fit ? ({ good: "Fits your land size", small: "Tight for your land size", too_small: "Usually needs more land" }[crop.scale.fit]) : "Land size not provided";
  const tiles = [["First action", firstAction], ["Main risk", risk], ["Water status", water], ["Land-size fit", crop.scale?.note ? `${fit}: ${crop.scale.note}` : fit]];
  return <section className="card rounded-xl border border-field/20 bg-mint p-5 sm:p-6" aria-labelledby="decision-snapshot-title">
    <h2 id="decision-snapshot-title" className="section-title">Start here</h2>
    <p className="mt-2 text-sm text-soil">These next steps come directly from the crop data and local conditions.</p>
    <dl className="mt-4 grid gap-3 sm:grid-cols-2">
      {tiles.map(([label, value]) => <div key={label} className="rounded-xl bg-white/80 p-4"><dt className="text-xs font-semibold uppercase tracking-wide text-soil">{label}</dt><dd className="mt-2 text-sm leading-relaxed">{formatDisplayText(value)}</dd></div>)}
    </dl>
  </section>;
}
