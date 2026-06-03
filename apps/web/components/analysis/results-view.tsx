"use client";

import { useState } from "react";
import Link from "next/link";
import { Activity, Download, FileText, ScanLine, Stethoscope } from "lucide-react";
import type { GaitAnalysisResult, PoseTrack } from "@horalix/shared";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DemoBadge, DisclaimerBar } from "@/components/ui/disclaimer";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { TEST_TYPE_LABELS, fmt, pct, statusTone } from "@/lib/format";
import { SkeletonCanvas } from "@/components/viewer/skeleton-canvas";
import { AsymmetryChart, JointCurveChart } from "./charts";
import { FlagsList } from "./flags-list";
import { KeypointAnalysis } from "./keypoint-analysis";
import { MetricCard, StatCard } from "./metric-card";
import { QualityPanel } from "./quality-panel";
import { RiskGauge } from "./risk-gauge";
import { ModelTransparency } from "./transparency";
import { cn } from "@/lib/utils";

export function ResultsView({
  result,
  pose,
}: {
  result: GaitAnalysisResult;
  pose: PoseTrack;
}) {
  const [tab, setTab] = useState<"overview" | "keypoints">("overview");
  const isDemo = result.simulated_data_used;
  const metric = (k: string) => result.metrics.find((m) => m.key === k);
  const stepAsym = result.asymmetry.find((a) => a.key === "step_time_asymmetry");
  const cadence = metric("cadence_steps_per_min");
  const speed = metric("walking_speed_m_per_s");
  const qualityTone =
    result.quality.overall_score >= 75
      ? "good"
      : result.quality.overall_score >= 55
        ? "warn"
        : "danger";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold tracking-tight">
              {TEST_TYPE_LABELS[result.test_type]}
            </h1>
            <Badge tone="primary">{result.model_info.pose_model}</Badge>
          </div>
          <p className="mt-1 text-xs text-fg-subtle">
            Analysis {result.analysis_id} · {new Date(result.created_at).toLocaleString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link href={`/report/${result.analysis_id}`}>
            <Button variant="secondary" size="sm">
              <Stethoscope className="h-4 w-4" /> Report
            </Button>
          </Link>
          <a href={api.reportPdfUrl(result.analysis_id)} target="_blank" rel="noreferrer">
            <Button variant="secondary" size="sm">
              <FileText className="h-4 w-4" /> PDF
            </Button>
          </a>
          <a href={api.reportJsonUrl(result.analysis_id)} target="_blank" rel="noreferrer">
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" /> JSON
            </Button>
          </a>
        </div>
      </div>

      {isDemo ? (
        <DemoBadge />
      ) : (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-good/40 bg-good/10 px-2.5 py-0.5 text-[11px] font-medium text-good">
          <span className="h-1.5 w-1.5 rounded-full bg-good" />
          Real AI keypoint analysis · {result.model_info.pose_model}
        </span>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-1 border-b border-border">
        {(
          [
            ["overview", "Overview", Activity],
            ["keypoints", "Keypoint Analysis", ScanLine],
          ] as const
        ).map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={cn(
              "flex items-center gap-2 border-b-2 px-4 py-2 text-sm transition -mb-px",
              tab === id
                ? "border-primary text-fg"
                : "border-transparent text-fg-subtle hover:text-fg",
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      {tab === "keypoints" ? (
        <KeypointAnalysis result={result} pose={pose} />
      ) : (
        <div className="space-y-6">
          {/* Viewer + risk/summary */}
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle>Skeleton overlay</CardTitle>
                <span className="text-[11px] text-fg-subtle">
                  Left = amber · Right = blue · events on timeline
                </span>
              </CardHeader>
              <CardContent>
                <SkeletonCanvas
                  pose={pose}
                  events={result.events}
                  videoUrl={isDemo ? null : api.rawVideoUrl(result.video_id)}
                  isDemo={isDemo}
                />
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Mobility Risk Support Score</CardTitle>
                </CardHeader>
                <CardContent>
                  <RiskGauge
                    score={result.mobility_risk_support_score}
                    band={result.mobility_risk_band}
                    confidence={result.overall_confidence}
                  />
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Interpretation</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-xs leading-relaxed text-fg-subtle">{result.report_summary}</p>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Headline stats */}
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
            <StatCard
              label="Cadence"
              value={fmt(cadence?.value, 0)}
              unit="steps/min"
              tone={cadence ? statusTone(cadence.status) : "muted"}
            />
            <StatCard
              label="Walking speed"
              value={fmt(speed?.value, 2)}
              unit="m/s"
              tone={speed ? statusTone(speed.status) : "muted"}
              sub={result.model_info.calibration_status}
            />
            <StatCard
              label="Step-time symmetry"
              value={stepAsym?.asymmetry_percent != null ? `${fmt(stepAsym.asymmetry_percent, 1)}%` : "—"}
              unit="asymmetry"
              tone={stepAsym ? statusTone(stepAsym.status) : "muted"}
            />
            <StatCard
              label="Video quality"
              value={fmt(result.quality.overall_score, 0)}
              unit="/ 100"
              tone={qualityTone}
            />
            <StatCard
              label="Analysis confidence"
              value={pct(result.overall_confidence)}
              tone={result.overall_confidence >= 0.6 ? "good" : "warn"}
            />
          </div>

          {/* Charts */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Joint motion</CardTitle>
              </CardHeader>
              <CardContent>
                <JointCurveChart curves={result.joint_curves} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Left–right asymmetry</CardTitle>
              </CardHeader>
              <CardContent>
                <AsymmetryChart items={result.asymmetry} />
              </CardContent>
            </Card>
          </div>

          {/* All metrics */}
          <div>
            <h2 className="mb-3 text-sm font-semibold text-fg-subtle">All metrics</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {result.metrics.map((m) => (
                <MetricCard key={m.key} metric={m} />
              ))}
            </div>
          </div>

          {/* Flags + quality + transparency */}
          <div className="grid gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-1">
              <CardHeader>
                <CardTitle>Clinical flags for review</CardTitle>
              </CardHeader>
              <CardContent>
                <FlagsList flags={result.clinical_flags} />
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Video quality</CardTitle>
              </CardHeader>
              <CardContent>
                <QualityPanel quality={result.quality} />
              </CardContent>
            </Card>
            <ModelTransparency model={result.model_info} quality={result.quality} />
          </div>

          {/* Limitations + recommendations */}
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Limitations</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5 text-xs text-fg-subtle">
                  {result.limitations.map((l, i) => (
                    <li key={i}>• {l}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Suggested clinician review points</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1.5 text-xs text-fg-subtle">
                  {result.recommendations.map((r, i) => (
                    <li key={i}>• {r}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <DisclaimerBar />
    </div>
  );
}
