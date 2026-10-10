import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import SiteHeader from "@/components/SiteHeader";
import SiteFooter from "@/components/SiteFooter";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  metadataBase: new URL("https://agrisense-ai-cyan.vercel.app"),
  icons: { icon: "/favicon.svg", shortcut: "/favicon.svg" },
  title: "AgriSense · Find the crops your Florida land is built for",
  description: "Find the crops your Florida land is built for with explainable suitability scores and local growing guidance.",
  openGraph: {
    title: "AgriSense — Find the crops your Florida land is built for",
    description: "Pick a spot in Florida and see 13 crops ranked by explainable suitability scores, local yields and UF/IFAS guidance.",
    type: "website",
    siteName: "AgriSense",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col"><a href="#main-content" className="skip-link no-print">Skip to content</a><SiteHeader /><div id="main-content" className="flex-1 min-w-0">{children}</div><SiteFooter /></body>
    </html>
  );
}
