import Link from "next/link";

export default function SiteHeader() {
  return (
    <header className="site-header border-b border-field/15 bg-sand">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-5 gap-y-3 px-5 py-4 sm:px-8">
        <Link href="/" className="inline-flex min-h-11 shrink-0 items-center rounded-lg">
          <span className="font-editorial text-4xl font-normal tracking-tight text-field">AgriSense</span>
        </Link>
        <nav aria-label="Main navigation" className="flex flex-wrap gap-2 text-sm font-medium">
          <Link href="/about" className="inline-flex min-h-11 items-center hover:underline underline-offset-4">About the data</Link>
        </nav>
      </div>
    </header>
  );
}
