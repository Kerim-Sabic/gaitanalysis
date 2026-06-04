"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, LayoutDashboard, PlusCircle, Video } from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "./theme-toggle";
import { ApiStatusIndicator } from "./api-status";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/cases", label: "Cases", icon: Activity },
  { href: "/analyze", label: "New analysis", icon: PlusCircle },
  { href: "/live-analysis", label: "Live camera", icon: Video },
];

export function Topbar() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-40 border-b border-border glass">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="relative flex h-8 w-8 items-center justify-center rounded-xl bg-primary/15">
            <span className="absolute h-2.5 w-2.5 rounded-full bg-primary" />
            <span className="absolute h-5 w-5 rounded-full border border-primary/40" />
          </span>
          <span className="leading-none">
            <span className="block text-sm font-semibold tracking-tight">
              Horalix <span className="text-primary">Gait AI</span>
            </span>
            <span className="block text-[10px] uppercase tracking-[0.18em] text-fg-subtle">
              Movement intelligence
            </span>
          </span>
        </Link>

        <nav className="ml-2 hidden items-center gap-1 md:flex">
          {NAV.map(({ href, label, icon: Icon }) => {
            const active =
              href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition",
                  active
                    ? "bg-surface-2 text-fg"
                    : "text-fg-subtle hover:bg-surface-2 hover:text-fg",
                )}
              >
                <Icon className="h-4 w-4" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <ApiStatusIndicator compact />
          <span className="hidden text-[11px] text-fg-subtle sm:inline">
            For clinician review · Not a diagnosis
          </span>
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
