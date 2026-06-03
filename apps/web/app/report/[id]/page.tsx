"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Download, FileText } from "lucide-react";
import type { GaitAnalysisResult, PatientCase } from "@horalix/shared";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DemoBadge, DISCLAIMER_TEXT } from "@/components/ui/disclaimer";
import { CenteredSpinner } from "@/components/ui/states";
import { FlagsList } from "@/components/analysis/flags-list";
import { TEST_TYPE_LABELS, fmt, pct, riskBandLabel, riskTone } from "@/lib/format";

export default function ReportPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [result, setResult] = useState<GaitAnalysisResult | null>(null);
  const [patient, setPatient] = useState<PatientCase | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getResult(id)
      .then(async (r) => {
        setResult(r);
        setPatient(await api.getCase(r.case_id).catch(() => null));
      })
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not load report."),
      );
  }, [id]);

  if (error) return <p className="text-sm text-danger">{error}</p>;
  if (!result) return <CenteredSpinner label="Loading report…" />;

  const isDemo = result.analysis_mode === "demo";
  const mi = result.model_info;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link href={`/analysis/${id}`} className="inline-flex items-center gap-1 text-sm text-primary hover:underline">
          <ArrowLeft className="h-4 w-4" /> Back to results
        </Link>
        <div className="flex gap-2">
          <a href={api.reportPdfUrl(id)} target="_blank" rel="noreferrer">
            <Button variant="secondary" size="sm">
              <FileText className="h-4 w-4" /> Download PDF
            </Button>
          </a>
          <a href={api.reportJsonUrl(id)} target="_blank" rel="noreferrer">
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4" /> JSON
            </Button>
          </a>
        </div>
      </div>

      <article className="rounded-2xl border border-border bg-surface p-8 shadow-soft">
        {/* Header */}
        <header className="border-b border-border pb-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight">
                HORALIX <span className="text-primary">GAIT AI</span>
              </h1>
              <p className="text-xs text-fg-subtle">
                AI-assisted gait quantification report · For clinician review
              </p>
            </div>
            <Badge tone={riskTone(result.mobility_risk_band)}>
              Risk: {riskBandLabel(result.mobility_risk_band)}
            </Badge>
          </div>
          {isDemo ? <DemoBadge className="mt-3" /> : null}
        </header>

        <Section title="1 · Patient / case information">
          <KV
            rows={[
              ["Patient code", patient?.patient_code ?? "—"],
              ["Indication", patient?.indication ?? "—"],
              ["Age", patient?.age != null ? String(patient.age) : "—"],
              ["Sex", patient?.sex ?? "—"],
              ["Height (cm)", patient?.height_cm != null ? String(patient.height_cm) : "—"],
              ["Clinician", patient?.clinician ?? "—"],
            ]}
          />
        </Section>

        <Section title="2 · Test protocol & video quality">
          <KV
            rows={[
              ["Test type", TEST_TYPE_LABELS[result.test_type]],
              ["Analysis mode", result.analysis_mode],
              ["Overall quality", `${fmt(result.quality.overall_score, 0)} / 100`],
              ["Detected view", result.quality.detected_view],
              ["Feet visibility", `${fmt(result.quality.feet_visibility, 0)} / 100`],
              ["Camera stability", `${fmt(result.quality.camera_stability, 0)} / 100`],
            ]}
          />
        </Section>

        <Section title="3 · Key gait metrics">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-fg-subtle">
              <tr>
                <th className="py-2">Metric</th>
                <th className="py-2">Value</th>
                <th className="py-2">Conf.</th>
                <th className="py-2">Interpretation</th>
              </tr>
            </thead>
            <tbody>
              {result.metrics.map((m) => (
                <tr key={m.key} className="border-t border-border/60 align-top">
                  <td className="py-2 pr-3 font-medium">{m.label}</td>
                  <td className="tabular py-2 pr-3 whitespace-nowrap">
                    {fmt(m.value, 2)} {m.unit}
                  </td>
                  <td className="tabular py-2 pr-3">{pct(m.confidence)}</td>
                  <td className="py-2 text-xs text-fg-subtle">
                    {m.interpretation || m.normal_reference || "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section title="4 · Left–right comparison">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-fg-subtle">
              <tr>
                <th className="py-2">Parameter</th>
                <th className="py-2">Left</th>
                <th className="py-2">Right</th>
                <th className="py-2">Asymmetry</th>
              </tr>
            </thead>
            <tbody>
              {result.asymmetry.map((a) => (
                <tr key={a.key} className="border-t border-border/60">
                  <td className="py-2 font-medium">{a.label}</td>
                  <td className="tabular py-2">{fmt(a.left, 2)}</td>
                  <td className="tabular py-2">{fmt(a.right, 2)}</td>
                  <td className="py-2 text-xs text-fg-subtle">
                    {a.asymmetry_percent != null ? `${fmt(a.asymmetry_percent, 1)}% — ` : ""}
                    {a.interpretation}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>

        <Section title="5 · Joint motion summary">
          <KV
            rows={result.joint_curves.map((c) => [
              c.label,
              `min ${fmt(c.min, 0)}° · max ${fmt(c.max, 0)}° · ROM ${fmt(c.rom, 0)}°`,
            ])}
          />
        </Section>

        <Section title="6 · Clinical flags for review">
          <FlagsList flags={result.clinical_flags} />
        </Section>

        <Section title="7 · Interpretation">
          <p className="text-sm leading-relaxed text-fg-subtle">{result.report_summary}</p>
          <p className="mt-3 text-sm leading-relaxed text-fg-subtle">
            <span className="font-medium text-fg">Patient-friendly: </span>
            {result.patient_summary}
          </p>
        </Section>

        <Section title="8 · Limitations">
          <ul className="space-y-1 text-xs text-fg-subtle">
            {result.limitations.map((l, i) => (
              <li key={i}>• {l}</li>
            ))}
          </ul>
        </Section>

        <Section title="9 · Suggested clinician review points">
          <ul className="space-y-1 text-xs text-fg-subtle">
            {result.recommendations.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </Section>

        <Section title="10 · Model / version metadata">
          <KV
            rows={[
              ["Pose model", `${mi.pose_model} ${mi.pose_model_version}`],
              ["Keypoint format", mi.keypoint_format],
              ["Pipeline", `v${mi.pipeline_version}`],
              ["Frames", String(mi.frame_count)],
              ["FPS", fmt(mi.fps, 1)],
              ["Mean keypoint confidence", pct(mi.mean_keypoint_confidence)],
              ["Calibration", mi.calibration_status],
            ]}
          />
        </Section>

        <footer className="mt-6 border-t border-border pt-4">
          <p className="text-xs font-medium text-fg">Disclaimer</p>
          <p className="mt-1 text-[11px] leading-snug text-fg-subtle">{DISCLAIMER_TEXT}</p>
          <p className="mt-2 text-[11px] text-fg-subtle">
            Generated {new Date(result.created_at).toLocaleString()} · Analysis {result.analysis_id}
          </p>
        </footer>
      </article>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-b border-border py-5 last:border-0">
      <h2 className="mb-3 text-sm font-semibold text-fg">{title}</h2>
      {children}
    </section>
  );
}

function KV({ rows }: { rows: [string, string][] }) {
  return (
    <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
      {rows.map(([k, v], i) => (
        <div key={i} className="flex items-center justify-between gap-3 border-b border-border/40 py-1.5">
          <span className="text-xs text-fg-subtle">{k}</span>
          <span className="tabular text-xs font-medium text-fg">{v}</span>
        </div>
      ))}
    </div>
  );
}
