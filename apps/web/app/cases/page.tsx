"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, PlusCircle } from "lucide-react";
import type { CaseSummary } from "@horalix/shared";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CenteredSpinner, EmptyState } from "@/components/ui/states";
import { DemoLauncher } from "@/components/demo-launcher";
import { relativeDate, riskBandLabel, riskTone } from "@/lib/format";

export default function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listCases()
      .then(setCases)
      .catch((e) =>
        setError(e instanceof ApiError ? e.message : "Could not reach the API."),
      );
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Cases</h1>
          <p className="text-sm text-fg-subtle">
            De-identified patient cases and their latest gait analysis.
          </p>
        </div>
        <Link href="/analyze">
          <Button>
            <PlusCircle className="h-4 w-4" /> New analysis
          </Button>
        </Link>
      </div>

      {error ? (
        <Card className="p-4 text-sm text-danger">{error}</Card>
      ) : cases === null ? (
        <CenteredSpinner label="Loading cases…" />
      ) : cases.length === 0 ? (
        <div className="space-y-6">
          <EmptyState
            title="No cases yet"
            description="Create a case and upload a walking video, or launch a demo to see a full analysis."
            action={
              <Link href="/analyze">
                <Button>
                  <PlusCircle className="h-4 w-4" /> New analysis
                </Button>
              </Link>
            }
          />
          <div>
            <h2 className="mb-3 text-sm font-semibold text-fg-subtle">Or try a demo</h2>
            <DemoLauncher variant="row" />
          </div>
        </div>
      ) : (
        <Card className="overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface-2/60 text-left text-xs text-fg-subtle">
              <tr>
                <th className="px-4 py-3 font-medium">Patient</th>
                <th className="px-4 py-3 font-medium">Age / Sex</th>
                <th className="hidden px-4 py-3 font-medium md:table-cell">Indication</th>
                <th className="px-4 py-3 font-medium">Last analysis</th>
                <th className="px-4 py-3 font-medium">Risk</th>
                <th className="hidden px-4 py-3 font-medium sm:table-cell">Quality</th>
                <th className="px-4 py-3 font-medium">Review</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {cases.map(({ case: c, last_risk_band, last_quality, last_mode }) => (
                <tr key={c.id} className="border-t border-border/60 hover:bg-surface-2/40">
                  <td className="px-4 py-3 font-medium">{c.patient_code}</td>
                  <td className="px-4 py-3 text-fg-subtle">
                    {c.age ?? "—"} / {c.sex}
                  </td>
                  <td className="hidden px-4 py-3 text-fg-subtle md:table-cell">
                    {c.indication ?? "—"}
                  </td>
                  <td className="px-4 py-3 text-fg-subtle">
                    {relativeDate(c.last_analysis_at)}
                    {last_mode === "demo_simulated" ? (
                      <Badge tone="warn" className="ml-2">demo</Badge>
                    ) : null}
                  </td>
                  <td className="px-4 py-3">
                    {last_risk_band ? (
                      <Badge tone={riskTone(last_risk_band)}>{riskBandLabel(last_risk_band)}</Badge>
                    ) : (
                      <span className="text-fg-subtle">—</span>
                    )}
                  </td>
                  <td className="hidden px-4 py-3 sm:table-cell">
                    {last_quality != null ? (
                      <span className="tabular">{Math.round(last_quality)}</span>
                    ) : (
                      <span className="text-fg-subtle">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={c.review_status === "reviewed" ? "good" : "muted"}>
                      {c.review_status.replace("_", " ")}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-right">
                    {c.last_analysis_id ? (
                      <Link
                        href={`/analysis/${c.last_analysis_id}`}
                        className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        Open <ArrowRight className="h-3 w-3" />
                      </Link>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
