import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AgriSense — Find the crops your Florida land is built for",
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
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
