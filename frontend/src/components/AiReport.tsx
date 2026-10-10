"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { formatDisplayText } from "@/lib/format";
import type { CropDetail } from "@/lib/types";

interface Report {
  verdict: string;
  summary: string;
  pros: string[];
  cons: string[];
  first_steps: string[];
}
interface ReportResponse { report: Report; source: "ai" | "fallback" }

function isReportResponse(value: unknown): value is ReportResponse {
  if (typeof value !== "object" || value === null) return false;
  const response = value as Partial<ReportResponse>;
  const report = response.report;
  return (response.source === "ai" || response.source === "fallback") && !!report
    && typeof report.verdict === "string" && typeof report.summary === "string"
    && [report.pros, report.cons, report.first_steps].every((list) => Array.isArray(list) && list.every((item) => typeof item === "string"));
}

function Shimmer({ className }: { className: string }) {
  return <div aria-hidden="true" className={`report-shimmer rounded bg-gradient-to-r from-soil/10 via-sand to-soil/10 ${className}`} />;
}

export default function AiReport({ crop, verdictSlot }: { crop: CropDetail; verdictSlot: HTMLElement | null }) {
  const [result, setResult] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch("/api/report", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ crop }), signal: controller.signal,
        });
        if (!response.ok) throw new Error("The summary is unavailable. Your crop scores are still shown above.");
        const body: unknown = await response.json();
        if (!isReportResponse(body)) throw new Error("The summary could not be read. Please try again.");
        if (!controller.signal.aborted) setResult(body);
      } catch (error) {
        if (!controller.signal.aborted) setError(error instanceof Error ? error.message : "The summary is unavailable. Please try again.");
      }
    }
    void load();
    return () => controller.abort();
  }, [crop, attempt]);

  const verdict = result ? (
    <p className="mt-3 truncate text-sm italic text-ink/80" title={formatDisplayText(result.report.verdict)}>{formatDisplayText(result.report.verdict)}</p>
  ) : !error ? <Shimmer className="mt-3 h-5 w-full max-w-md" /> : null;

  return (
    <>
      {verdictSlot && createPortal(verdict, verdictSlot)}
      <section className="rounded-xl border border-field/15 bg-white/50 p-5 sm:p-6" aria-labelledby="ai-summary-title" aria-busy={!result && !error}>
        <h2 id="ai-summary-title" className="text-2xl font-semibold">AI summary of the data above</h2>
        {error ? (
          <div role="alert" className="mt-4">
            <p className="text-sm text-soil">{error}</p>
            <button type="button" onClick={() => { setError(null); setResult(null); setAttempt((n) => n + 1); }} className="mt-3 rounded-lg bg-field px-4 py-2 text-sm font-semibold text-white">Try again</button>
          </div>
        ) : !result ? (
          <div className="mt-5 space-y-5" role="status" aria-live="polite" aria-label="Loading crop summary">
            <Shimmer className="h-5 w-full" /><Shimmer className="h-5 w-4/5" />
            <div className="grid gap-5 sm:grid-cols-2"><Shimmer className="h-28 w-full" /><Shimmer className="h-28 w-full" /></div>
            <Shimmer className="h-20 w-full" />
          </div>
        ) : (
          <div aria-live="polite">
            <p className="mt-4 leading-relaxed">{formatDisplayText(result.report.summary)}</p>
            <div className="mt-6 grid gap-6 sm:grid-cols-2">
              {(["pros", "cons"] as const).map((kind) => (
                <div key={kind}><h3 className="font-semibold">{kind === "pros" ? "Pros" : "Cons"}</h3>
                  <ul className="mt-3 list-disc space-y-2 pl-5 text-sm leading-relaxed">{result.report[kind].map((item, i) => <li key={i}>{formatDisplayText(item)}</li>)}</ul>
                </div>
              ))}
            </div>
            <h3 className="mt-6 font-semibold">First steps</h3>
            <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm leading-relaxed">{result.report.first_steps.map((step, i) => <li key={i}>{formatDisplayText(step)}</li>)}</ol>
            {result.source === "fallback" && <p className="mt-5 text-sm text-soil">Summary generated from the scores (AI unavailable)</p>}
          </div>
        )}
        <p className="mt-5 text-sm leading-relaxed text-soil">Written by AI from the numbers on this page. Scores are calculated, not generated.</p>
      </section>
    </>
  );
}
