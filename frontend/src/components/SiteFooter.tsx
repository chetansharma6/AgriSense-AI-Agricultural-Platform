import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="site-footer mt-auto border-t border-field/15 bg-sand">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-6 text-sm leading-relaxed text-soil sm:px-8">
        <div><p className="font-editorial text-xl text-field">AgriSense</p><p>Helping Florida growers make better-informed decisions.</p><p className="mt-1 text-xs">General guidance only.</p></div>
        <Link href="/about" className="inline-flex min-h-11 items-center underline underline-offset-4">About the Data</Link>
      </div>
    </footer>
  );
}
