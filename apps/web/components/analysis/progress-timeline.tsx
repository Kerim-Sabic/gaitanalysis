"use client";

import { motion } from "framer-motion";
import { Check, Loader2, X } from "lucide-react";
import type { AnalysisProgress } from "@horalix/shared";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export function ProgressTimeline({ progress }: { progress: AnalysisProgress }) {
  return (
    <div className="space-y-5">
      <div>
        <div className="mb-1.5 flex items-center justify-between text-xs">
          <span className="text-fg-subtle">
            {progress.status === "failed"
              ? "Analysis failed"
              : progress.status === "completed"
                ? "Analysis complete"
                : "Analysing walking video…"}
          </span>
          <span className="tabular font-medium">{Math.round(progress.progress * 100)}%</span>
        </div>
        <Progress
          value={progress.progress}
          tone={progress.status === "failed" ? "danger" : "primary"}
        />
      </div>

      <ol className="space-y-1">
        {progress.stages.map((s, i) => (
          <motion.li
            key={s.key}
            initial={{ opacity: 0, x: -6 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.04 }}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 transition",
              s.status === "active" && "bg-primary/10",
            )}
          >
            <span
              className={cn(
                "flex h-6 w-6 items-center justify-center rounded-full border",
                s.status === "done" && "border-good bg-good/15 text-good",
                s.status === "active" && "border-primary bg-primary/15 text-primary",
                s.status === "error" && "border-danger bg-danger/15 text-danger",
                s.status === "pending" && "border-border text-fg-subtle",
              )}
            >
              {s.status === "done" ? (
                <Check className="h-3.5 w-3.5" />
              ) : s.status === "active" ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : s.status === "error" ? (
                <X className="h-3.5 w-3.5" />
              ) : (
                <span className="h-1.5 w-1.5 rounded-full bg-current" />
              )}
            </span>
            <span
              className={cn(
                "text-sm",
                s.status === "pending" ? "text-fg-subtle" : "text-fg",
              )}
            >
              {s.label}
            </span>
          </motion.li>
        ))}
      </ol>

      {progress.error ? (
        <div className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
          {progress.error}
        </div>
      ) : null}
    </div>
  );
}
