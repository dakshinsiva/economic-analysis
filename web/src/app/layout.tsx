import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const sans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const mono = Geist_Mono({ variable: "--font-mono", subsets: ["latin"] });

const SITE = "https://econ-agent.vercel.app";
const TITLE = "econ-agent";
const DESCRIPTION =
  "An agentic research desk over FRED. A LangGraph agent that plans its data retrieval, pauses for your approval, " +
  "fetches deterministically, cites every figure with series and date, and fact-checks its own draft.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: { default: TITLE, template: `%s · ${TITLE}` },
  description: DESCRIPTION,
  applicationName: TITLE,
  keywords: ["FRED", "macroeconomics", "LangGraph", "agent", "JOLTS", "yield curve", "inflation", "economic research"],
  authors: [{ name: "Dakshin Siva", url: "https://github.com/dakshinsiva" }],
  creator: "Dakshin Siva",
  openGraph: {
    type: "website",
    url: SITE,
    siteName: TITLE,
    title: `${TITLE} — an agentic research desk over FRED`,
    description: DESCRIPTION,
    locale: "en_US",
  },
  twitter: {
    card: "summary_large_image",
    title: `${TITLE} — an agentic research desk over FRED`,
    description: DESCRIPTION,
  },
  robots: { index: true, follow: true },
  alternates: { canonical: SITE },
};

export const viewport = { themeColor: [{ media: "(prefers-color-scheme: dark)", color: "#1a1a19" }, { media: "(prefers-color-scheme: light)", color: "#fcfcfb" }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable} h-full antialiased`}>
      <body className="min-h-full bg-surface text-fg">{children}</body>
    </html>
  );
}
