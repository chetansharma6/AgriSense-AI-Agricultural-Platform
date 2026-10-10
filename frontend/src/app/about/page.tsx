import Link from "next/link";

export default function About() {
  return (
    <main className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
      <Link href="/" className="text-field underline underline-offset-4">Back to AgriSense</Link>
      <h1 className="mt-8 text-3xl font-semibold">About the data</h1>
      <p className="mt-4 leading-relaxed">AgriSense combines soil data from USDA NRCS, climate data from NASA POWER, and harvest history from USDA NASS to compare 13 Florida crops.</p>
      <p className="mt-4 leading-relaxed">More information about sources and scoring is coming soon. Demo farms use synthetic fixtures. Results provide general guidance only.</p>
    </main>
  );
}
