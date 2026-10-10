import Link from "next/link";
import { Suspense } from "react";
import CropDetailClient, { CropDetailSkeleton } from "./CropDetailClient";

export default function CropDetailPage() {
  return (
    <main className="mx-auto w-full min-w-0 max-w-6xl px-5 py-8 sm:px-8">
      <Link href="/" className="mb-5 inline-flex min-h-11 items-center text-2xl font-bold tracking-tight text-field">AgriSense</Link>
      <Suspense fallback={<CropDetailSkeleton />}>
        <CropDetailClient />
      </Suspense>
    </main>
  );
}
