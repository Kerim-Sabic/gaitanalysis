"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PlayCircle } from "lucide-react";
import type { DemoPreset } from "@horalix/shared";
import { api, ApiError } from "@/lib/api";
import { Spinner } from "@/components/ui/states";
import { cn } from "@/lib/utils";

const PRESETS: { id: DemoPreset; label: string; desc: string }[] = [
  { id: "normal", label: "Healthy reference", desc: "Symmetric, steady walk" },
  { id: "asymmetric", label: "Asymmetric gait", desc: "Left–right step imbalance" },
  { id: "tug", label: "Timed Up and Go", desc: "Slower, reduced cadence" },
  { id: "poor_quality", label: "Low-quality capture", desc: "Limited interpretation" },
];

export function DemoLauncher({ variant = "grid" }: { variant?: "grid" | "row" }) {
  const router = useRouter();
  const [loading, setLoading] = useState<DemoPreset | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function run(preset: DemoPreset) {
    setLoading(preset);
    setError(null);
    try {
      const progress = await api.startDemo(preset);
      router.push(`/analysis/${progress.analysis_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start demo. Is the API running?");
      setLoading(null);
    }
  }

  return (
    <div>
      <div
        className={cn(
          "grid gap-3",
          variant === "grid" ? "sm:grid-cols-2" : "sm:grid-cols-4",
        )}
      >
        {PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => run(p.id)}
            disabled={loading !== null}
            className="group flex items-center gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-left transition hover:border-primary/40 hover:bg-surface-2 disabled:opacity-60"
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              {loading === p.id ? <Spinner /> : <PlayCircle className="h-5 w-5" />}
            </span>
            <span className="min-w-0">
              <span className="block text-sm font-medium text-fg">{p.label}</span>
              <span className="block truncate text-[11px] text-fg-subtle">{p.desc}</span>
            </span>
          </button>
        ))}
      </div>
      {error ? <p className="mt-3 text-xs text-danger">{error}</p> : null}
    </div>
  );
}
