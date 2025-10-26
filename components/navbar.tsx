'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const navItems = [
  { href: "/profile", label: "Profile" },
  { href: "/chat", label: "AI Recipes" },
  { href: "/dashboard", label: "Forecast" }
];

export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="px-4 pt-6 sm:px-6 sm:pt-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-4 rounded-[32px] px-4 py-4 text-sm font-medium text-slate-600 sm:flex-row sm:items-center sm:justify-between sm:gap-6 sm:px-8">
        <Link
          href="/"
          className="flex items-center gap-2 text-lg font-semibold text-slate-900"
        >
          <span className="text-gradient">AIGlucose</span>
        </Link>
        <nav className="flex flex-wrap items-center gap-2 rounded-full bg-transparent px-1 py-1 sm:gap-4">
          {navItems.map((item) => {
            const active = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "relative rounded-full px-4 py-2 transition-all sm:px-5",
                  active
                    ? "bg-white text-slate-900 shadow-[8px_8px_16px_rgba(209,217,230,0.7),_-8px_-8px_16px_rgba(255,255,255,0.9)]"
                    : "text-slate-600 hover:text-slate-900"
                )}
              >
                {item.label}
                {active ? (
                  <span className="absolute inset-x-6 -bottom-1 h-1 rounded-full bg-gradient-to-r from-sky-400 to-emerald-400" />
                ) : null}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
