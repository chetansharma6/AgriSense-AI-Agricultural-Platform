"use client";

import dynamic from "next/dynamic";
import type { FloridaMapProps } from "./FloridaMap";

const FloridaMap = dynamic(() => import("./FloridaMap"), {
  ssr: false,
  loading: () => (
    <div
      className="flex h-[320px] lg:h-[420px] w-full items-center justify-center rounded-lg bg-sand text-ink"
      role="status"
    >
      Loading Florida map…
    </div>
  ),
});

export default function MapLoader(props: FloridaMapProps) {
  return <FloridaMap {...props} />;
}
