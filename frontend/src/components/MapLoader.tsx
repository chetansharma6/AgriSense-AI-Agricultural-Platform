"use client";

import dynamic from "next/dynamic";
import type { FloridaMapProps } from "./FloridaMap";

const FloridaMap = dynamic(() => import("./FloridaMap"), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-full w-full items-center justify-center rounded-lg bg-sand text-ink"
      role="status" aria-live="polite"
    >
      Loading Florida map…
    </div>
  ),
});

export default function MapLoader(props: FloridaMapProps) {
  return (
    <div className="h-[320px] w-full lg:h-[420px]">
      <FloridaMap {...props} />
    </div>
  );
}
