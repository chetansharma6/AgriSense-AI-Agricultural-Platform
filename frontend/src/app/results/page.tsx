import Link from "next/link";
import { Suspense } from "react";
import { LandSummarySkeleton } from "@/components/LandSummary";
import ResultsClient from "./ResultsClient";

export default function ResultsPage() {
  return (
    <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <Link href="/" className="text-2xl font-bold tracking-tight text-field">AgriSense</Link>
      <h1 className="mt-8 mb-6 text-3xl font-semibold">Your Florida land</h1>
      <Suspense fallback={<LandSummarySkeleton />}>
        <ResultsClient />
      </Suspense>
      <p className="mt-6 text-sm text-soil">Data: USDA NRCS, NASA POWER, USDA NASS. General guidance only.</p>
    </main>
  );
}
