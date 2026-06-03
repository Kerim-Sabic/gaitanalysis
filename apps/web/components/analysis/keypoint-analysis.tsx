"use client";

import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  BAND_COLORS,
  BAND_LABELS,
  KEYPOINT_COLOR_DISCLAIMER,
  KEYPOINT_LEGEND,
  confidenceBand,
  type GaitAnalysisResult,
  type KeypointStat,
  type PoseTrack,
} from "@horalix/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { SkeletonCanvas, type ColorMode } from "@/components/viewer/skeleton-canvas";
import { cn } from "@/lib/utils";

const METRIC_REVIEW = "#f59e0b";
const METRIC_LOWCONF = "#ef4444";
const METRIC_GOOD = "#22c55e";
const METRIC_NEUTRAL = "#64748b";

const COLOR_MODES: { id: ColorMode; label: string }[] = [
  { id: "tracking", label: "Tracking confidence" },
  { id: "movement", label: "Movement flags" },
  { id: "both", label: "Both" },
  { id: "none", label: "Hide colors" },
];

function bandBadgeTone(band: string): "good" | "warn" | "danger" | "muted" {
  if (band === "good") return "good";
  if (band === "moderate") return "warn";
  if (band === "limited") return "warn";
  return "danger";
}

export function KeypointAnalysis({
  result,
  pose,
}: {
  result: GaitAnalysisResult;
  pose: PoseTrack;
}) {
  const stats = result.keypoint_stats;
  const [mode, setMode] = useState<ColorMode>("tracking");
  const [selected, setSelected] = useState<number | null>(null);

  // Movement-flag colors: worst related-metric status per keypoint.
  const movementColors = useMemo(() => {
    const statusByKey = new Map(result.metrics.map((m) => [m.key, m.status]));
    const rank = { low_confidence: 3, review: 2, limited: 1, good: 0 } as Record<string, number>;
    const colors: Record<number, string> = {};
    stats.forEach((s) => {
      let worst = "good";
      for (const mk of s.related_metrics) {
        const st = statusByKey.get(mk);
        if (st && (rank[st] ?? 0) > (rank[worst] ?? 0)) worst = st;
      }
      colors[s.index] = s.related_metrics.length
        ? worst === "low_confidence"
          ? METRIC_LOWCONF
          : worst === "review"
            ? METRIC_REVIEW
            : worst === "limited"
              ? METRIC_NEUTRAL
              : METRIC_GOOD
        : METRIC_NEUTRAL;
    });
    return colors;
  }, [stats, result.metrics]);

  const selectedStat: KeypointStat | undefined =
    selected != null ? stats.find((s) => s.index === selected) : undefined;

  const lowConfidence = useMemo(
    () =>
      stats
        .filter((s) => s.quality_band === "limited" || s.quality_band === "unreliable")
        .sort((a, b) => a.mean_confidence - b.mean_confidence),
    [stats],
  );

  const legQuality = useMemo(() => {
    const leg = (side: "left" | "right") => {
      const names = [`${side}_hip`, `${side}_knee`, `${side}_ankle`, `${side}_heel`, `${side}_foot_index`];
      const vals = stats.filter((s) => names.includes(s.name));
      if (!vals.length) return null;
      return vals.reduce((a, s) => a + s.mean_confidence, 0) / vals.length;
    };
    return { left: leg("left"), right: leg("right") };
  }, [stats]);

  const confSeries = useMemo(() => {
    if (selected == null) return [];
    const step = Math.max(1, Math.floor(pose.frames.length / 160));
    const out: { t: number; c: number }[] = [];
    for (let i = 0; i < pose.frames.length; i += step) {
      const f = pose.frames[i];
      const kp = f.keypoints[selected];
      if (kp) out.push({ t: Number(f.t.toFixed(2)), c: Number(kp[2].toFixed(3)) });
    }
    return out;
  }, [selected, pose.frames]);

  const missingOverall =
    stats.length > 0
      ? stats.reduce((a, s) => a + s.missing_frame_percent, 0) / stats.length
      : 0;

  return (
    <div className="space-y-6">
      {/* Patient explanation */}
      <Card>
        <CardContent className="pt-5">
          <p className="text-xs leading-relaxed text-fg-subtle">{KEYPOINT_COLOR_DISCLAIMER}</p>
        </CardContent>
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Viewer + controls */}
        <div className="lg:col-span-2 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            {COLOR_MODES.map((m) => (
              <button
                key={m.id}
                onClick={() => setMode(m.id)}
                className={cn(
                  "rounded-full border px-3 py-1 text-xs transition",
                  mode === m.id
                    ? "border-primary/40 bg-primary/15 text-primary"
                    : "border-border bg-surface-2 text-fg-subtle hover:text-fg",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>
          <SkeletonCanvas
            pose={pose}
            events={result.events}
            videoUrl={result.simulated_data_used ? null : `/api/videos/${result.video_id}/raw`}
            isDemo={result.simulated_data_used}
            colorMode={mode}
            movementColors={movementColors}
            selectedKeypoint={selected}
            onSelectKeypoint={(i) => setSelected(i)}
          />
          {/* Legend */}
          <div className="flex flex-wrap gap-x-4 gap-y-1 rounded-xl border border-border bg-surface-2/40 px-3 py-2">
            {(mode === "movement"
              ? [
                  { color: METRIC_GOOD, label: "Metric within range" },
                  { color: METRIC_REVIEW, label: "Metric: review recommended" },
                  { color: METRIC_LOWCONF, label: "Metric: low confidence" },
                  { color: METRIC_NEUTRAL, label: "No linked movement metric" },
                ]
              : KEYPOINT_LEGEND
            ).map((item, i) => (
              <span key={i} className="flex items-center gap-1.5 text-[11px] text-fg-subtle">
                <span
                  className="inline-block h-2.5 w-2.5 rounded-full"
                  style={{ background: item.color, border: item.label.includes("Dashed") ? "1px dashed #cbd5e1" : undefined }}
                />
                {item.label}
              </span>
            ))}
          </div>
          {mode === "movement" || mode === "both" ? (
            <p className="text-[11px] text-fg-subtle">
              Tracking confidence shows how well the model <em>sees</em> a joint. Movement
              flags show whether a <em>metric</em> derived from it needs review — a joint can
              be tracked well (green) while its movement metric is flagged (amber).
            </p>
          ) : null}
        </div>

        {/* Selected keypoint details */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Keypoint details</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {selectedStat ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-semibold capitalize">
                      {selectedStat.name.replace(/_/g, " ")}
                    </span>
                    <Badge tone={bandBadgeTone(selectedStat.quality_band)}>
                      {BAND_LABELS[selectedStat.quality_band as keyof typeof BAND_LABELS] ??
                        selectedStat.quality_band}
                    </Badge>
                  </div>
                  <Row label="Side" value={selectedStat.side} />
                  <Row
                    label="Average confidence"
                    value={`${Math.round(selectedStat.mean_confidence * 100)}%`}
                  />
                  <Row label="Valid frames" value={`${selectedStat.valid_frame_percent}%`} />
                  <Row label="Missing frames" value={`${selectedStat.missing_frame_percent}%`} />
                  <Row label="Interpolated" value={`${selectedStat.interpolated_percent}%`} />
                  <Row
                    label="Related metrics"
                    value={selectedStat.related_metrics.join(", ") || "—"}
                  />
                  <p className="pt-1 text-[11px] leading-snug text-fg-subtle">
                    {selectedStat.note}
                  </p>
                  {confSeries.length ? (
                    <div className="pt-2">
                      <p className="mb-1 text-[11px] text-fg-subtle">Confidence over time</p>
                      <ResponsiveContainer width="100%" height={110}>
                        <AreaChart data={confSeries} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
                          <defs>
                            <linearGradient id="cfill" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.5} />
                              <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                            </linearGradient>
                          </defs>
                          <CartesianGrid stroke="hsl(var(--border))" strokeDasharray="3 3" vertical={false} />
                          <XAxis dataKey="t" hide />
                          <YAxis domain={[0, 1]} width={28} fontSize={10} stroke="hsl(var(--fg-subtle))" />
                          <ReferenceLine y={0.8} stroke={BAND_COLORS.good} strokeDasharray="3 3" />
                          <ReferenceLine y={0.4} stroke={BAND_COLORS.unreliable} strokeDasharray="3 3" />
                          <Tooltip
                            contentStyle={{
                              background: "hsl(var(--surface))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: 10,
                              fontSize: 11,
                            }}
                            formatter={(v) => [`${Math.round(Number(v) * 100)}%`, "confidence"]}
                          />
                          <Area type="monotone" dataKey="c" stroke="hsl(var(--primary))" fill="url(#cfill)" strokeWidth={2} />
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  ) : null}
                </div>
              ) : (
                <p className="text-xs text-fg-subtle">
                  Click a keypoint on the figure to inspect its tracking quality,
                  missing-frame rate and the gait metrics it affects.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Leg tracking quality */}
          <Card>
            <CardHeader>
              <CardTitle>Left / right tracking</CardTitle>
            </CardHeader>
            <CardContent className="pt-0 space-y-3">
              {(["left", "right"] as const).map((side) => {
                const v = legQuality[side];
                if (v == null) return <Row key={side} label={`${side} leg`} value="—" />;
                const band = confidenceBand(v);
                return (
                  <div key={side}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="capitalize text-fg-subtle">{side} leg</span>
                      <span className="tabular font-medium">{Math.round(v * 100)}%</span>
                    </div>
                    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                      <div
                        className="h-full rounded-full"
                        style={{ width: `${v * 100}%`, background: BAND_COLORS[band] }}
                      />
                    </div>
                  </div>
                );
              })}
              <Row label="Overall missing frames" value={`${missingOverall.toFixed(1)}%`} />
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Low-confidence joints */}
      <Card>
        <CardHeader>
          <CardTitle>Low-confidence keypoints</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          {lowConfidence.length ? (
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {lowConfidence.map((s) => (
                <button
                  key={s.index}
                  onClick={() => setSelected(s.index)}
                  className="flex items-center justify-between rounded-xl border border-border bg-surface-2/40 px-3 py-2 text-left transition hover:border-primary/40"
                >
                  <span className="text-xs capitalize">{s.name.replace(/_/g, " ")}</span>
                  <Badge tone={bandBadgeTone(s.quality_band)}>
                    {Math.round(s.mean_confidence * 100)}%
                  </Badge>
                </button>
              ))}
            </div>
          ) : (
            <p className="text-xs text-good">
              All tracked keypoints were within acceptable confidence. Absence of low-confidence
              keypoints does not by itself confirm clinical accuracy.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/50 py-1.5 last:border-0">
      <span className="text-xs text-fg-subtle">{label}</span>
      <span className="text-xs font-medium text-fg">{value}</span>
    </div>
  );
}
