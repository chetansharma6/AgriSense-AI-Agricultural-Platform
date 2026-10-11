import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Page not found · AgriSense" };

export default function NotFound() {
  return (
    <main className="theme-page mx-auto w-full max-w-6xl px-5 py-16 sm:px-8">
      <p className="mb-3 text-sm font-semibold uppercase tracking-widest text-soil">404 · A little off the beaten path</p>
      <h1 className="page-title">That page isn&apos;t in our field</h1>
      <p className="mt-5 leading-relaxed">Let&apos;s head back and find a Florida location to explore.</p>
      <Link href="/" className="mt-6 inline-flex min-h-11 items-center rounded-lg bg-field px-5 py-3 font-semibold text-white">Back home</Link>
    </main>
  );
}
