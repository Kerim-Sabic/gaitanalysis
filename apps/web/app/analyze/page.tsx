"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Upload,
  XCircle,
} from "lucide-react";
import type {
  CameraView,
  PatientCase,
  QualityResult,
  Sex,
  TestType,
  VideoMetadata,
} from "@horalix/shared";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/states";
import { DisclaimerBar } from "@/components/ui/disclaimer";
import { DemoLauncher } from "@/components/demo-launcher";
import { TEST_TYPE_DESCRIPTIONS, TEST_TYPE_LABELS } from "@/lib/format";
import { cn } from "@/lib/utils";

const STEPS = ["Patient case", "Test type", "Upload video", "Quality check"];
const TEST_TYPES = Object.keys(TEST_TYPE_LABELS) as TestType[];

const CAPTURE_TIPS = [
  "Frame the whole body, head to feet, for the entire walk.",
  "Record a clear side (sagittal) view from ~3–4 m away.",
  "Use even lighting; avoid strong backlight and shadows.",
  "Keep the camera steady — a tripod or fixed surface is ideal.",
  "Capture several full strides (≥ 5–6 s of steady walking).",
  "Keep only one person in frame; remove background movement.",
];

export default function AnalyzePage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // form state
  const [form, setForm] = useState({
    patient_code: "",
    age: "",
    sex: "unspecified" as Sex,
    height_cm: "",
    indication: "",
    clinician: "",
  });
  const [testType, setTestType] = useState<TestType>("standard_walk");
  const [cameraView, setCameraView] = useState<CameraView>("sagittal");
  const [calibration, setCalibration] = useState("");

  const [caseObj, setCaseObj] = useState<PatientCase | null>(null);
  const [video, setVideo] = useState<VideoMetadata | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [quality, setQuality] = useState<QualityResult | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);

  function set<K extends keyof typeof form>(k: K, v: string) {
    setForm((f) => ({ ...f, [k]: v }));
  }

  async function ensureCase(): Promise<PatientCase> {
    if (caseObj) return caseObj;
    const created = await api.createCase({
      patient_code: form.patient_code.trim() || "ANON",
      age: form.age ? Number(form.age) : null,
      sex: form.sex,
      height_cm: form.height_cm ? Number(form.height_cm) : null,
      indication: form.indication || null,
      clinician: form.clinician || null,
    });
    setCaseObj(created);
    return created;
  }

  async function onPickFile(f: File) {
    setFile(f);
    setQuality(null);
    setVideo(null);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
  }

  async function uploadAndCheck() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const c = await ensureCase();
      const fd = new FormData();
      fd.append("case_id", c.id);
      fd.append("test_type", testType);
      fd.append("camera_view", cameraView);
      if (calibration) fd.append("calibration_distance_m", calibration);
      fd.append("file", file);
      const uploaded = await api.uploadVideo(fd);
      setVideo(uploaded);
      const q = await api.getQuality(uploaded.id);
      setQuality(q);
      setStep(3);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  async function startAnalysis() {
    if (!video) return;
    setBusy(true);
    setError(null);
    try {
      const progress = await api.startAnalysis({ video_id: video.id, test_type: testType });
      router.push(`/analysis/${progress.analysis_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start analysis.");
      setBusy(false);
    }
  }

  const canNext =
    step === 0 ? form.patient_code.trim().length > 0 : step === 1 ? true : true;

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">New analysis</h1>
        <p className="text-sm text-fg-subtle">
          Create a case, choose a protocol, upload a walking video, and review
          capture quality before analysis.
        </p>
      </div>

      {/* Stepper */}
      <div className="flex items-center gap-2">
        {STEPS.map((label, i) => (
          <div key={label} className="flex flex-1 items-center gap-2">
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-xs font-medium",
                i < step
                  ? "border-good bg-good/15 text-good"
                  : i === step
                    ? "border-primary bg-primary/15 text-primary"
                    : "border-border text-fg-subtle",
              )}
            >
              {i < step ? <CheckCircle2 className="h-4 w-4" /> : i + 1}
            </div>
            <span
              className={cn(
                "hidden text-xs sm:block",
                i === step ? "text-fg" : "text-fg-subtle",
              )}
            >
              {label}
            </span>
            {i < STEPS.length - 1 ? (
              <div className="mx-1 hidden h-px flex-1 bg-border sm:block" />
            ) : null}
          </div>
        ))}
      </div>

      <Card>
        <CardContent className="pt-5">
          {step === 0 ? (
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Patient code / initials *" hint="De-identified. No full names.">
                <Input
                  value={form.patient_code}
                  onChange={(e) => set("patient_code", e.target.value)}
                  placeholder="e.g. JD-204"
                />
              </Field>
              <Field label="Indication">
                <Input
                  value={form.indication}
                  onChange={(e) => set("indication", e.target.value)}
                  placeholder="e.g. post-TKR review"
                />
              </Field>
              <Field label="Age">
                <Input
                  type="number"
                  value={form.age}
                  onChange={(e) => set("age", e.target.value)}
                  placeholder="years"
                />
              </Field>
              <Field label="Sex">
                <Select value={form.sex} onChange={(e) => set("sex", e.target.value)}>
                  <option value="unspecified">Unspecified</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="other">Other</option>
                </Select>
              </Field>
              <Field label="Height (cm)" hint="Enables height-based scale estimation.">
                <Input
                  type="number"
                  value={form.height_cm}
                  onChange={(e) => set("height_cm", e.target.value)}
                  placeholder="e.g. 172"
                />
              </Field>
              <Field label="Clinician">
                <Input
                  value={form.clinician}
                  onChange={(e) => set("clinician", e.target.value)}
                  placeholder="Reviewing clinician"
                />
              </Field>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="grid gap-3 sm:grid-cols-2">
              {TEST_TYPES.map((t) => (
                <button
                  key={t}
                  onClick={() => setTestType(t)}
                  className={cn(
                    "rounded-xl border p-4 text-left transition",
                    testType === t
                      ? "border-primary bg-primary/10"
                      : "border-border bg-surface-2/40 hover:border-primary/40",
                  )}
                >
                  <span className="block text-sm font-medium">{TEST_TYPE_LABELS[t]}</span>
                  <span className="mt-1 block text-[11px] leading-snug text-fg-subtle">
                    {TEST_TYPE_DESCRIPTIONS[t]}
                  </span>
                </button>
              ))}
            </div>
          ) : null}

          {step === 2 ? (
            <div className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Camera view">
                  <Select
                    value={cameraView}
                    onChange={(e) => setCameraView(e.target.value as CameraView)}
                  >
                    <option value="sagittal">Side (sagittal)</option>
                    <option value="coronal">Front/back (coronal)</option>
                    <option value="unknown">Auto-detect</option>
                  </Select>
                </Field>
                <Field
                  label="Calibration distance (m)"
                  hint="Optional: known walked distance for calibrated speed."
                >
                  <Input
                    type="number"
                    value={calibration}
                    onChange={(e) => setCalibration(e.target.value)}
                    placeholder="e.g. 4.0"
                  />
                </Field>
              </div>

              <div
                onClick={() => fileRef.current?.click()}
                className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface-2/30 px-6 py-10 text-center transition hover:border-primary/50"
              >
                <Upload className="mb-2 h-6 w-6 text-primary" />
                <p className="text-sm font-medium">
                  {file ? file.name : "Click to upload a walking video"}
                </p>
                <p className="mt-1 text-[11px] text-fg-subtle">
                  MP4, MOV, WebM, AVI · up to 400 MB
                </p>
                <input
                  ref={fileRef}
                  type="file"
                  accept="video/*"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && onPickFile(e.target.files[0])}
                />
              </div>

              {previewUrl ? (
                <video src={previewUrl} controls className="w-full rounded-xl border border-border" />
              ) : null}

              <div className="rounded-xl border border-border bg-surface-2/40 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium">
                  <Camera className="h-4 w-4 text-primary" /> Capture instructions
                </div>
                <ul className="grid gap-1.5 text-[11px] text-fg-subtle sm:grid-cols-2">
                  {CAPTURE_TIPS.map((tip) => (
                    <li key={tip}>• {tip}</li>
                  ))}
                </ul>
              </div>
            </div>
          ) : null}

          {step === 3 && quality ? (
            <QualityReview quality={quality} />
          ) : null}

          {error ? <p className="mt-4 text-xs text-danger">{error}</p> : null}
        </CardContent>
      </Card>

      {/* Footer nav */}
      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0 || busy}
        >
          <ChevronLeft className="h-4 w-4" /> Back
        </Button>

        {step < 2 ? (
          <Button onClick={() => setStep((s) => s + 1)} disabled={!canNext}>
            Continue <ChevronRight className="h-4 w-4" />
          </Button>
        ) : step === 2 ? (
          <Button onClick={uploadAndCheck} disabled={!file || busy}>
            {busy ? <Spinner /> : null} Upload & check quality
          </Button>
        ) : (
          <Button onClick={startAnalysis} disabled={busy}>
            {busy ? <Spinner /> : null} Run gait analysis
          </Button>
        )}
      </div>

      <div className="rounded-2xl border border-border bg-surface/40 p-4">
        <h2 className="mb-3 text-sm font-semibold text-fg-subtle">
          No video handy? Run an instant demo
        </h2>
        <DemoLauncher variant="row" />
      </div>

      <DisclaimerBar />
    </div>
  );
}

function QualityReview({ quality }: { quality: QualityResult }) {
  const checks: { label: string; ok: boolean; note?: string }[] = [
    { label: "Adequate lighting", ok: quality.lighting_score >= 55 },
    { label: "Sharp / in focus", ok: quality.blur_score >= 55 },
    { label: "Sufficient resolution", ok: quality.resolution_score >= 60 },
    { label: "Camera stable", ok: quality.camera_stability >= 55 },
    { label: "Adequate frame rate", ok: quality.framerate_ok },
    { label: "Long enough clip", ok: quality.duration_ok },
  ];
  const tone =
    quality.overall_score >= 75 ? "good" : quality.overall_score >= 55 ? "warn" : "danger";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <CardTitle>Pre-analysis quality</CardTitle>
        <Badge tone={tone}>{Math.round(quality.overall_score)} / 100</Badge>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        {checks.map((c) => (
          <div
            key={c.label}
            className="flex items-center gap-2 rounded-lg border border-border bg-surface-2/40 px-3 py-2 text-sm"
          >
            {c.ok ? (
              <CheckCircle2 className="h-4 w-4 text-good" />
            ) : (
              <XCircle className="h-4 w-4 text-warn" />
            )}
            <span className={c.ok ? "text-fg" : "text-fg-subtle"}>{c.label}</span>
          </div>
        ))}
      </div>
      {quality.recommendations.length ? (
        <div className="rounded-xl border border-warn/30 bg-warn/10 p-3">
          <p className="mb-1 text-xs font-medium text-warn">To improve results:</p>
          <ul className="space-y-1 text-[11px] text-fg-subtle">
            {quality.recommendations.map((r, i) => (
              <li key={i}>• {r}</li>
            ))}
          </ul>
        </div>
      ) : (
        <p className="text-xs text-good">Capture looks good. You can run the analysis.</p>
      )}
      <p className="text-[11px] text-fg-subtle">
        Full-body and feet visibility are finalised during analysis once pose is
        available.
      </p>
    </div>
  );
}
