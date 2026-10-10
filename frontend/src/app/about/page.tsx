import Link from "next/link";
import type { Metadata } from "next";
import type { FactorKey } from "@/lib/types";
import { FACTOR_WEIGHTS } from "@/lib/weights";

export const metadata: Metadata = {
  title: "How AgriSense works | AgriSense",
  description: "Explore the public data, six scoring factors, and limitations behind AgriSense crop suitability reports.",
};

const steps = [
  { title: "Public data", description: "Soil, weather and harvest records describe conditions at your Florida location." },
  { title: "Calculated score", description: "Python compares those conditions with crop requirements to calculate an explainable suitability score from 0 to 100." },
  { title: "AI explanation", description: "AI turns the calculated results into plain-language guidance. It never invents scores, yields or prices." },
];

const sources = [
  { name: "USDA NRCS Soil Data Access (SSURGO)", use: "Soil pH, organic matter, sand and clay content, and drainage class.", url: "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest" },
  { name: "NASA POWER", use: "Daily temperature, precipitation and solar data for local climate conditions.", url: "https://power.larc.nasa.gov/api/temporal/daily/point" },
  { name: "USDA NASS Quick Stats", use: "County yield history and statewide crop prices.", url: "https://quickstats.nass.usda.gov/api/api_GET/" },
  { name: "FCC Census Area API", use: "Match latitude and longitude to a county name and FIPS code.", url: "https://geo.fcc.gov/api/census/area" },
  { name: "UF/IFAS Extension", use: "Crop requirements, Florida growing windows and Extension guidance.", url: "https://edis.ifas.ufl.edu/" },
];

const factors: { key: FactorKey; name: string; measure: string }[] = [
  { key: "soil_ph", name: "Soil pH", measure: "How closely soil acidity matches the crop’s preferred range." },
  { key: "drainage", name: "Drainage", measure: "How well the soil’s drainage class suits the crop." },
  { key: "season_temp", name: "Season temperature", measure: "How temperatures during a Florida growing window match the crop’s needs." },
  { key: "frost_risk", name: "Frost risk", measure: "Freeze days during the growing window compared with the crop’s cold tolerance." },
  { key: "rainfall", name: "Rainfall", measure: "Rainfall during the growing window compared with the crop’s water needs." },
  { key: "local_history", name: "Local history", measure: "Evidence that the crop has been grown in the county or elsewhere in Florida." },
];

const limitations = [
  "Climate data uses a roughly 50 km grid, so conditions on an individual farm may differ.",
  "Soil data represents map-unit averages and may miss variation within a field.",
  "Some vegetables only have statewide data; local yield records may be unavailable.",
  "Results provide general guidance only. Consult UF/IFAS Extension and assess your field before making planting decisions.",
];

export default function About() {
  return (
    <main className="mx-auto w-full max-w-5xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-field underline underline-offset-4">Back to AgriSense</Link>
      <h1 className="mt-8 text-4xl font-semibold tracking-tight sm:text-5xl">How AgriSense works</h1>
      <p className="mt-5 max-w-3xl leading-relaxed text-ink/75 sm:text-lg">AgriSense combines public soil, climate and harvest data to rank 13 crops for your Florida location. Deterministic calculations produce the suitability scores, and AI explains those results in plain language.</p>

      <section aria-labelledby="process-heading" className="mt-10">
        <h2 id="process-heading" className="text-2xl font-semibold">From data to guidance</h2>
        <ol className="mt-5 flex flex-col gap-3 md:flex-row md:items-stretch">
          {steps.map((step, index) => (
            <li key={step.title} className="flex min-w-0 flex-1 flex-col gap-3 md:flex-row">
              {index > 0 && <span aria-hidden="true" className="self-center text-2xl text-field"><span className="md:hidden">↓</span><span className="hidden md:inline">→</span></span>}
              <div className="w-full flex-1 rounded-xl border border-field/20 bg-white/50 p-5">
                <span className="text-xs font-semibold uppercase tracking-widest text-soil">Step {index + 1}</span>
                <h3 className="mt-2 text-xl font-semibold text-field">{step.title}</h3>
                <p className="mt-3 text-sm leading-relaxed text-ink/75">{step.description}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section aria-labelledby="sources-heading" className="mt-12">
        <h2 id="sources-heading" className="text-2xl font-semibold">Data sources</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {sources.map((source) => (
            <article key={source.name} className="rounded-xl border border-field/20 bg-white/50 p-5">
              <h3 className="font-semibold">{source.name}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink/75">{source.use}</p>
              <a href={source.url} className="mt-4 inline-block text-sm font-medium text-field underline underline-offset-4">Visit {source.name}</a>
            </article>
          ))}
        </div>
      </section>

      <section aria-labelledby="factors-heading" className="mt-12">
        <h2 id="factors-heading" className="text-2xl font-semibold">The six factors</h2>
        <p className="mt-3 leading-relaxed text-ink/75">Each factor scores from 0 to 100. Missing factors are excluded and the remaining weights are normalized; climate factors are evaluated for each Florida growing window, and the best window wins. If soil pH, drainage, season temperature or frost risk scores below 25, the total is capped at 45.</p>
        <div className="mt-5 overflow-x-auto rounded-xl border border-field/20">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Suitability factors, their default weights and what they measure</caption>
            <thead className="bg-field text-white">
              <tr><th scope="col" className="px-4 py-3">Factor</th><th scope="col" className="px-4 py-3">Weight</th><th scope="col" className="px-4 py-3">What it measures</th></tr>
            </thead>
            <tbody className="bg-white/50">
              {factors.map((factor) => (
                <tr key={factor.key} className="border-t border-field/15">
                  <th scope="row" className="px-4 py-4 align-top font-medium">{factor.name}</th>
                  <td className="px-4 py-4 align-top tabular-nums">{FACTOR_WEIGHTS[factor.key]}%</td>
                  <td className="px-4 py-4 leading-relaxed text-ink/75">{factor.measure}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="limitations-heading" className="mt-12 rounded-xl border border-soil/25 bg-sun/10 p-5 sm:p-6">
        <h2 id="limitations-heading" className="text-2xl font-semibold">Limitations</h2>
        <ul className="mt-4 list-disc space-y-3 pl-5 text-sm leading-relaxed text-ink/75">
          {limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
        </ul>
      </section>
    </main>
  );
}
