import Link from "next/link";
import Image from "next/image";

export default function SiteHeader() {
  return (
    <header className="site-header border-b border-field/15 bg-sand">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-5 gap-y-3 px-5 py-4 sm:px-8">
        <Link href="/" className="inline-flex min-h-11 shrink-0 items-center rounded-lg">
          <Image src="/logo-reference.png" alt="AgriSense" width={2172} height={724} sizes="(max-width: 640px) 168px, 192px" className="h-12 w-auto sm:h-14" priority />
        </Link>
        <nav aria-label="Main navigation" className="flex flex-wrap gap-2 text-sm font-medium">
          <Link href="/" className="inline-flex min-h-11 items-center hover:underline underline-offset-4">New search</Link>
          <Link href="/about" className="inline-flex min-h-11 items-center hover:underline underline-offset-4">About the data</Link>
        </nav>
      </div>
    </header>
  );
}
