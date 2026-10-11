import type { Metadata } from "next";
import { placeLabel } from "@/lib/presentation";
import { Suspense } from "react";
import ResultsSkeleton from "@/components/ResultsSkeleton";
import ResultsClient from "./ResultsClient";

export async function generateMetadata({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }): Promise<Metadata> {
  const query = await searchParams;
  const place = placeLabel(typeof query.place === "string" ? query.place : null);
  return { title: `${place} results · AgriSense` };
}

export default function ResultsPage() {
  return (
    <main className="theme-page mx-auto max-w-6xl px-5 py-8 sm:px-8">
      <Suspense fallback={<ResultsSkeleton />}>
        <ResultsClient />
      </Suspense>
    </main>
  );
}
