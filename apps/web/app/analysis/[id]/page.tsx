"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import type {
  AnalysisProgress,
  GaitAnalysisResult,
  PoseTrack,
} from "@horalix/shared";
import { api, ApiError } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ProgressTimeline } from "@/components/analysis/progress-timeline";
import { ResultsView } from "@/components/analysis/results-view";
import { CenteredSpinner } from "@/components/ui/states";

export default function AnalysisPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const [progress, setProgress] = useState<AnalysisProgress | null>(null);
  const [result, setResult] = useState<GaitAnalysisResult | null>(null);
  const [pose, setPose] = useState<PoseTrack | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      try {
        const p = await api.getStatus(id);
        if (cancelled) return;
        setProgress(p);
        if (p.status === "completed") {
          const [r, ps] = await Promise.all([api.getResult(id), api.getPose(id)]);
          if (cancelled) return;
          setResult(r);
          setPose(ps);
          return; // stop polling
        }
        if (p.status === "failed") return; // stop polling
        timer.current = setTimeout(poll, 1200);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Could not reach the API.");
      }
    }
    poll();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [id]);

  if (error) {
    return (
      <Card className="mx-auto max-w-lg p-6 text-center">
        <AlertTriangle className="mx-auto h-6 w-6 text-danger" />
        <p className="mt-2 text-sm text-danger">{error}</p>
        <Link href="/analyze" className="mt-4 inline-block">
          <Button variant="secondary">Back to new analysis</Button>
        </Link>
      </Card>
    );
  }

  if (result && pose) {
    return <ResultsView result={result} pose={pose} />;
  }

  if (progress?.status === "failed") {
    return (
      <Card className="mx-auto max-w-lg">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-danger">
            <AlertTriangle className="h-4 w-4" /> Analysis failed
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ProgressTimeline progress={progress} />
          <Link href="/analyze" className="mt-4 inline-block">
            <Button variant="secondary">Try again with a different video</Button>
          </Link>
        </CardContent>
      </Card>
    );
  }

  if (progress) {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <div className="text-center">
          <h1 className="text-lg font-semibold tracking-tight">Running gait analysis</h1>
          <p className="text-sm text-fg-subtle">
            Video → pose → smoothing → events → metrics → report.
          </p>
        </div>
        <Card>
          <CardContent className="pt-6">
            <ProgressTimeline progress={progress} />
          </CardContent>
        </Card>
      </div>
    );
  }

  return <CenteredSpinner label="Loading analysis…" />;
}
