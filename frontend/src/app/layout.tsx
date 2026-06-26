import type { Metadata } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";
import { AnimatedBackground } from "@/components/animated-background";
import { BackgroundThemeSync } from "@/components/background-theme";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});
const body = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
  display: "swap",
});
const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Job Agent — application command center",
  description:
    "Scout, match, write, and track job applications. You keep the final click.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="en"
      className={`dark ${display.variable} ${body.variable} ${mono.variable}`}
      suppressHydrationWarning
    >
      <body className="mesh-atmosphere grain-overlay font-sans antialiased">
        <AnimatedBackground />
        <BackgroundThemeSync />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
