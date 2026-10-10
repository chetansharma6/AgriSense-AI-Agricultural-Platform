"use client";

import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { factorLabel, formatFactorDetail, formatDisplayText, formatWhole } from "@/lib/format";
import type { CropResult, FactorKey } from "@/lib/types";

const keys: FactorKey[] = ["soil_ph", "drainage", "season_temp", "frost_risk", "rainfall", "local_history"];

function color(score: number | null): string {
  if (score === null) return "#7a5c3e";
  if (score < 50) return "#a8432b";
  if (score < 75) return "#e9a23b";
  return "#2f6b3a";
}

interface FactorChartProps {
  factors: CropResult["factors"];
  details: CropResult["factor_details"];
  weights: Record<FactorKey, number>;
  explanation: string;
}

export default function FactorChart({ factors, details, weights, explanation }: FactorChartProps) {
  const data = keys.map((key) => ({
    key, label: factorLabel(key), score: factors?.[key] ?? null,
    detail: formatFactorDetail(key, details?.[key]), weight: weights[key],
  })).sort((a, b) => (b.score ?? -1) - (a.score ?? -1));
  return (
    <section id="factor-chart" className="card rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="factor-chart-title">
      <h2 id="factor-chart-title" className="section-title mb-5">Why it ranked here</h2>
      <div className="screen-only">
      <div className="space-y-4 lg:hidden">
        {data.map((row) => (
          <div key={row.key}>
            <p className="text-sm font-semibold">{row.label} <span className="font-normal">({formatWhole(row.score)})</span></p>
            <ResponsiveContainer width="100%" height={44} minWidth={0}>
              <BarChart data={[row]} layout="vertical" margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                <XAxis type="number" domain={[0, 100]} ticks={[0, 50, 100]} tick={{ fontSize: 14 }} height={20} />
                <YAxis type="category" dataKey="label" hide />
                <Tooltip formatter={() => [`${row.detail} · weight ${row.weight}%`, row.label]} />
                <Bar dataKey="score" fill={color(row.score)} barSize={10} isAnimationActive={false} />
              </BarChart>
            </ResponsiveContainer>
            <p className="mt-1 text-sm leading-relaxed text-soil">{row.detail}</p>
          </div>
        ))}
      </div>
      <div className="hidden h-[300px] grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-5 lg:grid">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 0, left: 0 }}>
            <XAxis type="number" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} height={26} tick={{ fontSize: 14 }} />
            <YAxis type="category" dataKey="label" width={145} tick={{ fontSize: 14 }} />
            <Tooltip content={({ active, label }) => {
              const row = data.find((item) => item.label === label);
              return active && row ? <div className="max-w-xs rounded-lg border border-field/20 bg-sand p-3 text-sm shadow-md"><p className="font-semibold">{row.label}: {formatWhole(row.score)}</p><p>{row.detail}</p><p>Weight: {row.weight}%</p></div> : null;
            }} />
            <Bar dataKey="score" barSize={18} isAnimationActive={false}>
              {data.map((row) => <Cell key={row.key} fill={color(row.score)} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
        <div className="grid grid-rows-6 pt-1 pb-[26px]">
          {data.map((row) => <p key={row.key} className="flex items-center text-sm leading-relaxed text-soil">{row.score === null ? `${row.label}: No data · ` : ""}{row.detail}</p>)}
        </div>
      </div>
      </div>
      <div className="print-only print-factors">
        {data.map((row) => <div key={row.key} className="print-factor-row">
          <div><strong>{row.label}: {formatWhole(row.score)}</strong><div className="print-bar-track"><div style={{ width: `${row.score ?? 0}%`, background: color(row.score) }} /></div></div>
          <p>{row.detail}</p>
        </div>)}
      </div>
      <p className="mt-5 text-sm leading-relaxed text-soil">{formatDisplayText(explanation)}</p>
    </section>
  );
}
