import Link from "next/link";
import LogoMark from "./LogoMark";

export default function SiteHeader() {
  return (
    <header className="site-header border-b border-field/15 bg-sand">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-5 gap-y-2 px-5 py-4 sm:px-8">
        <Link href="/" className="inline-flex min-h-11 items-center gap-2 text-2xl font-bold tracking-tight text-field">
          <LogoMark size={32} />AgriSense
        </Link>
        <nav aria-label="Main navigation" className="flex gap-5 text-sm font-medium">
          <Link href="/" className="inline-flex min-h-11 items-center hover:underline underline-offset-4">New search</Link>
          <Link href="/about" className="inline-flex min-h-11 items-center hover:underline underline-offset-4">About the data</Link>
        </nav>
      </div>
    </header>
  );
}
