import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Navbar } from "@/components/navbar";
import { UserProvider } from "@/context/UserContext";
import { Noto_Serif_SC } from "next/font/google";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "AIGlucose Wellness Assistant",
  description:
    "Manage personal metrics, explore AI-powered recipes, and visualise glucose forecasts in a calm, modern interface.",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    title: "AIGlucose",
    statusBarStyle: "black-translucent"
  }
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  viewportFit: "cover",
  themeColor: "#16a34a"
};

const notoSerif = Noto_Serif_SC({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-serif"
});

export default function RootLayout({
  children
}: {
  children: ReactNode;
}) {
  return (
    <html lang="en">
      <body
        className={cn(
          "relative min-h-screen overflow-x-hidden bg-[#e6ecf5] text-slate-900 antialiased",
          notoSerif.className,
          notoSerif.variable
        )}
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 flex justify-center blur-3xl">
          <div className="h-64 w-64 rounded-full bg-gradient-to-br from-sky-200 via-emerald-100 to-white opacity-60" />
        </div>
        <UserProvider>
          <Navbar />
          <main className="mx-auto my-6 w-full max-w-6xl bg-transparent px-2 pb-10 sm:my-8 sm:px-4 lg:pb-14">
            <div className="neu-surface rounded-[24px] px-4 py-6 sm:rounded-[32px] sm:px-8 sm:py-10">
              {children}
            </div>
          </main>
        </UserProvider>
      </body>
    </html>
  );
}
