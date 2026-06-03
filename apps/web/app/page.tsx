import Link from "next/link";
import {
  Activity,
  ArrowRight,
  Brain,
  HeartPulse,
  LineChart,
  Stethoscope,
  Timer,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { DisclaimerBar } from "@/components/ui/disclaimer";
import { DemoLauncher } from "@/components/demo-launcher";

const FEATURES = [
  { icon: LineChart, title: "Gait quantification", desc: "Cadence, step & stride timing, joint ROM and symmetry from a single camera." },
  { icon: HeartPulse, title: "Fall-risk screening support", desc: "A cautious Mobility Risk Support Score — a screening aid, never a diagnosis." },
  { icon: Activity, title: "Rehab progress monitoring", desc: "Repeatable, objective metrics designed for visit-over-visit comparison." },
  { icon: Brain, title: "Neurological mobility assessment", desc: "Variability, asymmetry and festination patterns flagged for clinician review." },
  { icon: Stethoscope, title: "Orthopedic recovery tracking", desc: "Post-operative mobility checks with conservative thresholds." },
];

const PIPELINE = [
  "Quality check",
  "Person tracking",
  "Pose estimation",
  "Temporal smoothing",
  "Gait events",
  "Metrics",
  "Confidence",
  "Report",
];

export default function HomePage() {
  return (
    <div className="space-y-16">
      {/* Hero */}
      <section className="animate-fade-up">
        <div className="flex flex-col items-start gap-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-border bg-surface px-3 py-1 text-xs text-fg-subtle">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Markerless · single-camera · model-agnostic
          </span>
          <h1 className="max-w-3xl text-4xl font-semibold tracking-tight sm:text-5xl">
            Horalix <span className="text-primary">Gait AI</span>
          </h1>
          <p className="max-w-2xl text-lg text-fg-subtle">
            Markerless AI gait analysis from ordinary walking video. Turn a
            smartphone clip into structured gait metrics, skeleton overlays,
            confidence scoring and a clinician-ready report.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Link href="/analyze">
              <Button size="lg">
                Start analysis <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link href="/cases">
              <Button size="lg" variant="secondary">
                View cases
              </Button>
            </Link>
          </div>

          {/* Pipeline strip */}
          <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-fg-subtle">
            {PIPELINE.map((p, i) => (
              <span key={p} className="flex items-center gap-2">
                <span className="rounded-md bg-surface-2 px-2 py-1">{p}</span>
                {i < PIPELINE.length - 1 ? <span className="text-fg-subtle/50">→</span> : null}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Demo */}
      <section className="space-y-4">
        <div className="flex items-end justify-between">
          <div>
            <h2 className="text-lg font-semibold tracking-tight">See it work — instant demo</h2>
            <p className="text-sm text-fg-subtle">
              Runs the real pipeline on simulated keypoints. Clearly labelled and
              not clinical-grade.
            </p>
          </div>
        </div>
        <DemoLauncher />
      </section>

      {/* Features */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold tracking-tight">Built for clinical movement teams</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, desc }) => (
            <Card key={title} className="transition hover:border-primary/30">
              <CardContent className="pt-5">
                <span className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="text-sm font-semibold">{title}</h3>
                <p className="mt-1 text-xs leading-relaxed text-fg-subtle">{desc}</p>
              </CardContent>
            </Card>
          ))}
          <Card className="flex items-center justify-center bg-surface-2/40">
            <CardContent className="flex items-center gap-2 py-8 text-sm text-fg-subtle">
              <Timer className="h-4 w-4" /> Multi-camera & calibrated capture on the roadmap
            </CardContent>
          </Card>
        </div>
      </section>

      <DisclaimerBar />
    </div>
  );
}
