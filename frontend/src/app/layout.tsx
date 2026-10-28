import type { Metadata, Viewport } from "next";
import { Fraunces, Inter } from "next/font/google";
import { AppShell } from "@/components/AppShell";
import { HealthProvider } from "@/components/health";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap", weight: ["500", "600"] });

export const metadata: Metadata = {
  title: "YatraAI — Intelligent Travel Companion",
  description: "Ask grounded travel questions with sources, discover places, compare destinations and plan itineraries.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf7f2" },
    { media: "(prefers-color-scheme: dark)", color: "#11161d" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${inter.variable} ${fraunces.variable} antialiased`}>
        <HealthProvider>
          <AppShell>{children}</AppShell>
        </HealthProvider>
      </body>
    </html>
  );
}
