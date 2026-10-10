import { Suspense } from "react";
import CropDetailClient, { CropDetailSkeleton } from "./CropDetailClient";

export default function CropDetailPage() {
  return (
    <main className="mx-auto w-full min-w-0 max-w-6xl px-5 py-8 sm:px-8">
      <Suspense fallback={<CropDetailSkeleton />}>
        <CropDetailClient />
      </Suspense>
    </main>
  );
}
