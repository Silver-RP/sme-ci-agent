import type { Metadata } from "next";
import { Be_Vietnam_Pro } from "next/font/google";
import { AppShell } from "@/components/shell/AppShell";import "./globals.css";

// Vietnamese-first typeface with full diacritics; exposed as --font-app (see globals.css).
const appFont = Be_Vietnam_Pro({
  subsets: ["latin", "vietnamese"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-app",
  display: "swap",
});

export const metadata: Metadata = {
  title: "SME CI Agent",
  description: "Agent cải tiến liên tục: phát hiện, điều tra, đề xuất, người duyệt, đo và học",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="vi" className={appFont.variable} suppressHydrationWarning>
      {/* browser extensions (e.g. ColorZilla) add attributes to <body> before React loads */}
      <body suppressHydrationWarning>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
