import type { Metadata } from "next";
import { placeLabel } from "@/lib/presentation";
import { Suspense } from "react";
import CropDetailClient, { CropDetailSkeleton } from "./CropDetailClient";

export async function generateMetadata({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}): Promise<Metadata> {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  const name = typeof query.crop === "string" ? query.crop.slice(0, 100)
    : id.replace(/_/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
  const place = placeLabel(typeof query.place === "string" ? query.place : null);
  return { title: `${name} at ${place} · AgriSense` };
}

export default function CropDetailPage() {
  return (
    <main className="theme-page analysis-page crop-detail-page crop-report mx-auto w-full min-w-0 max-w-6xl px-5 py-8 sm:px-8">
      <Suspense fallback={<CropDetailSkeleton />}>
        <CropDetailClient />
      </Suspense>
    </main>
  );
}
