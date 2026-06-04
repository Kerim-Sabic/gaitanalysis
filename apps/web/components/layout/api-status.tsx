"use client";

import { useEffect, useState } from "react";
import type { ModelStatus } from "@horalix/shared";
import {
  api,
  ApiError,
  getApiHealth,
  getApiHostname,
  getLiveStatus,
  isApiConfigured,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type ConnectionState = "checking" | "connected" | "offline" | "not_configured";

export function ApiStatusIndicator({
  compact = false,
  className,
}: {
  compact?: boolean;
  className?: string;
}) {
  const [state, setState] = useState<ConnectionState>("checking");
  const [model, setModel] = useState<ModelStatus | null>(null);
  const [liveAvailable, setLiveAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const hostname = getApiHostname();

  useEffect(() => {
    if (!isApiConfigured()) {
      setState("not_configured");
      setError("Set NEXT_PUBLIC_API_URL to enable backend analysis.");
      return;
    }

    let cancelled = false;
    void Promise.allSettled([getApiHealth(), api.modelStatus(), getLiveStatus()]).then(
      ([healthResult, modelResult, liveResult]) => {
        if (cancelled) return;
        if (healthResult.status === "rejected") {
          const reason = healthResult.reason;
          setState("offline");
          setError(
            reason instanceof ApiError
              ? reason.message
              : "Backend is offline or unreachable.",
          );
          return;
        }
        setState("connected");
        setError(null);
        if (modelResult.status === "fulfilled") setModel(modelResult.value);
        setLiveAvailable(
          liveResult.status === "fulfilled" ? liveResult.value.available : false,
        );
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const label =
    state === "connected"
      ? "API connected"
      : state === "offline"
        ? "API offline"
        : state === "not_configured"
          ? "API not configured"
          : "Checking API";
  const tone =
    state === "connected"
      ? "bg-good"
      : state === "checking"
        ? "bg-warn"
        : "bg-danger";
  const details = [
    hostname,
    model ? `model: ${model.model_name || model.active_backend}` : null,
    state === "connected" && liveAvailable !== null
      ? `live preview: ${liveAvailable ? "available" : "unavailable"}`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");

  if (compact) {
    return (
      <span
        className={cn(
          "inline-flex items-center gap-1.5 text-[11px] text-fg-subtle",
          className,
        )}
        title={error || details || label}
      >
        <span className={cn("h-1.5 w-1.5 rounded-full", tone)} />
        <span className="hidden lg:inline">{label}</span>
      </span>
    );
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-2 border-y border-border/70 py-2 text-xs",
        className,
      )}
    >
      <span className="inline-flex items-center gap-2 font-medium">
        <span className={cn("h-2 w-2 rounded-full", tone)} />
        {label}
      </span>
      <span className={state === "connected" ? "text-fg-subtle" : "text-danger"}>
        {state === "connected" ? details : error}
      </span>
    </div>
  );
}
