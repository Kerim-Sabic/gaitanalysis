"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock,
  Cpu,
  Gauge,
  Ruler,
  ShieldCheck,
  Smartphone,
  Upload,
  Video,
} from "lucide-react";
import type {
  AnalysisOptions,
  AnalysisQualityMode,
  CalibrationMode,
  CameraView,
  CaptureSource,
  ModelCapabilities,
  ModelCapability,
  PreflightResponse,
  TestType,
} from "@horalix/shared";
import { api, ApiError, isApiConfigured } from "@/lib/api";
import { ApiStatusIndicator } from "@/components/layout/api-status";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/states";
import { DisclaimerBar } from "@/components/ui/disclaimer";
import { TEST_TYPE_DESCRIPTIONS, TEST_TYPE_LABELS } from "@/lib/format";
import {
  DEFAULT_OPTIONS,
  saveSetupOptions,
  statusLabel,
  statusTone,
} from "@/lib/setup-options";
import { cn } from "@/lib/utils";

const STEPS = ["Capture", "Protocol", "Quality", "Models", "Calibration", "Review"];
const TEST_TYPES = Object.keys(TEST_TYPE_LABELS) as TestType[];

const CAPTURE_SOURCES: {
  id: CaptureSource;
  label: string;
  desc: string;
  Icon: typeof Upload;
}[] = [
  { id: "upload", label: "Upload a video", desc: "Analyse a walking clip from this device.", Icon: Upload },
  { id: "phone", label: "Capture with phone", desc: "Scan a QR code and record on a phone camera.", Icon: Smartphone },
  { id: "live", label: "Live camera", desc: "Near-real-time pose preview from a webcam.", Icon: Video },
];

export default function AnalysisSetupPage() {
  const router = useRouter();
  const [caps, setCaps] = useState<ModelCapabilities | null>(null);
  const [capsError, setCapsError] = useState<string | null>(null);
  const [step, setStep] = useState(0);
  const [opts, setOpts] = useState<AnalysisOptions>({ ...DEFAULT_OPTIONS });
  const [preflight, setPreflight] = useState<PreflightResponse | null>(null);
  const [pfLoading, setPfLoading] = useState(false);

  // upload-path fields
  const [patientCode, setPatientCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!isApiConfigured()) {
      setCapsError("API not configured. Set NEXT_PUBLIC_API_URL to the FastAPI backend.");
      return;
    }
    api
      .modelCapabilities()
      .then((c) => {
        setCaps(c);
        setCapsError(null);
      })
      .catch((e) => setCapsError(e instanceof ApiError ? e.message : "Could not load model capabilities."));
  }, []);

  function patch(p: Partial<AnalysisOptions>) {
    setOpts((o) => ({ ...o, ...p }));
    setPreflight(null);
  }

  // Quality mode drives helper defaults (explicit toggles still win afterwards).
  function setQualityMode(mode: AnalysisQualityMode) {
    if (mode === "advanced_clinical") {
      patch({ analysis_quality_mode: mode, enable_sam2: true, enable_depth: true });
    } else if (mode === "standard") {
      patch({
        analysis_quality_mode: mode,
        enable_sam2: false,
        enable_depth: false,
        pose_backend: null,
        require_selected_pose_backend: false,
        require_advanced_helpers: false,
      });
    } else {
      patch({ analysis_quality_mode: mode });
    }
  }

  const runPreflight = useCallback(async () => {
    setPfLoading(true);
    try {
      const pf = await api.preflight({ ...opts });
      setPreflight(pf);
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Preflight failed.");
    } finally {
      setPfLoading(false);
    }
  }, [opts]);

  useEffect(() => {
    if (step === 5 && !preflight && !pfLoading && isApiConfigured()) void runPreflight();
  }, [step, preflight, pfLoading, runPreflight]);

  function onPickFile(f: File) {
    setFile(f);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl(URL.createObjectURL(f));
  }

  async function startUpload() {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const c = await api.createCase({
        patient_code: patientCode.trim() || "ANON",
        height_cm: opts.patient_height_cm ?? null,
      });
      const fd = new FormData();
      fd.append("case_id", c.id);
      fd.append("test_type", opts.protocol ?? "standard_walk");
      fd.append("camera_view", opts.camera_view ?? "unknown");
      if (opts.calibration_mode === "known_distance" && opts.known_distance_m)
        fd.append("calibration_distance_m", String(opts.known_distance_m));
      fd.append("file", file);
      const uploaded = await api.uploadVideo(fd);
      const progress = await api.startAnalysis({
        video_id: uploaded.id,
        test_type: opts.protocol,
        options: opts,
      });
      router.push(`/analysis/${progress.analysis_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start analysis.");
      setBusy(false);
    }
  }

  function goCapture() {
    saveSetupOptions(opts);
    router.push(opts.capture_source === "phone" ? "/phone-pairing" : "/live-analysis");
  }

  const canContinue = useMemo(() => {
    if (step === 0) return !!opts.capture_source;
    if (step === 4 && opts.capture_source === "upload")
      return patientCode.trim().length > 0;
    return true;
  }, [step, opts.capture_source, patientCode]);

  const isUpload = opts.capture_source === "upload";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Set up analysis</h1>
        <p className="mt-1 max-w-2xl text-sm text-fg-subtle">
          Choose how you capture, the clinical protocol, and which AI models run —
          no environment variables. Every model status below is read live from the
          backend. For clinician review; not a standalone diagnosis.
        </p>
      </div>
      <ApiStatusIndicator />

      {capsError ? (
        <div className="rounded-xl border border-danger/40 bg-danger/10 px-3 py-2 text-xs text-danger">
          {capsError}
        </div>
      ) : null}

      <Stepper step={step} />

      <Card>
        <CardContent className="pt-5">
          {step === 0 ? (
            <CaptureStep value={opts.capture_source ?? "upload"} onChange={(s) => patch({ capture_source: s })} />
          ) : null}

          {step === 1 ? (
            <ProtocolStep value={opts.protocol ?? "standard_walk"} onChange={(t) => patch({ protocol: t })} />
          ) : null}

          {step === 2 ? (
            <QualityStep caps={caps} value={opts.analysis_quality_mode ?? "standard"} onChange={setQualityMode} />
          ) : null}

          {step === 3 ? (
            <ModelsStep caps={caps} opts={opts} patch={patch} />
          ) : null}

          {step === 4 ? (
            <CalibrationStep
              opts={opts}
              patch={patch}
              isUpload={isUpload}
              patientCode={patientCode}
              setPatientCode={setPatientCode}
            />
          ) : null}

          {step === 5 ? (
            <ReviewStep
              opts={opts}
              preflight={preflight}
              loading={pfLoading}
              isUpload={isUpload}
              file={file}
              previewUrl={previewUrl}
              onPickFile={onPickFile}
              fileRef={fileRef}
            />
          ) : null}

          {error ? <p className="mt-4 text-xs text-danger">{error}</p> : null}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0 || busy}>
          <ChevronLeft className="h-4 w-4" /> Back
        </Button>

        {step < 5 ? (
          <Button onClick={() => setStep((s) => s + 1)} disabled={!canContinue}>
            Continue <ChevronRight className="h-4 w-4" />
          </Button>
        ) : isUpload ? (
          <Button
            onClick={startUpload}
            disabled={busy || !file || !!capsError || (preflight ? !preflight.can_start : false)}
          >
            {busy ? <Spinner /> : null} Run gait analysis
          </Button>
        ) : (
          <Button onClick={goCapture} disabled={!!capsError || (preflight ? !preflight.can_start : false)}>
            {opts.capture_source === "phone" ? "Continue to phone pairing" : "Continue to live camera"}
            <ChevronRight className="h-4 w-4" />
          </Button>
        )}
      </div>

      <DisclaimerBar />
    </div>
  );
}

// --------------------------------------------------------------------------- //
function Stepper({ step }: { step: number }) {
  return (
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
          <span className={cn("hidden text-xs sm:block", i === step ? "text-fg" : "text-fg-subtle")}>{label}</span>
          {i < STEPS.length - 1 ? <div className="mx-1 hidden h-px flex-1 bg-border sm:block" /> : null}
        </div>
      ))}
    </div>
  );
}

function CaptureStep({ value, onChange }: { value: CaptureSource; onChange: (s: CaptureSource) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {CAPTURE_SOURCES.map(({ id, label, desc, Icon }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={cn(
            "rounded-xl border p-4 text-left transition",
            value === id ? "border-primary bg-primary/10" : "border-border bg-surface-2/40 hover:border-primary/40",
          )}
        >
          <Icon className="mb-2 h-5 w-5 text-primary" />
          <span className="block text-sm font-medium">{label}</span>
          <span className="mt-1 block text-[11px] leading-snug text-fg-subtle">{desc}</span>
        </button>
      ))}
    </div>
  );
}

function ProtocolStep({ value, onChange }: { value: TestType; onChange: (t: TestType) => void }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {TEST_TYPES.map((t) => (
        <button
          key={t}
          onClick={() => onChange(t)}
          className={cn(
            "rounded-xl border p-4 text-left transition",
            value === t ? "border-primary bg-primary/10" : "border-border bg-surface-2/40 hover:border-primary/40",
          )}
        >
          <span className="block text-sm font-medium">{TEST_TYPE_LABELS[t]}</span>
          <span className="mt-1 block text-[11px] leading-snug text-fg-subtle">{TEST_TYPE_DESCRIPTIONS[t]}</span>
        </button>
      ))}
    </div>
  );
}

function QualityStep({
  caps,
  value,
  onChange,
}: {
  caps: ModelCapabilities | null;
  value: AnalysisQualityMode;
  onChange: (m: AnalysisQualityMode) => void;
}) {
  const modes = caps?.quality_modes ?? [];
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Gauge className="h-4 w-4 text-primary" /> Analysis quality
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {modes.map((m) => (
          <button
            key={m.id}
            onClick={() => onChange(m.id)}
            className={cn(
              "rounded-xl border p-4 text-left transition",
              value === m.id ? "border-primary bg-primary/10" : "border-border bg-surface-2/40 hover:border-primary/40",
            )}
          >
            <span className="block text-sm font-medium">{m.name}</span>
            <span className="mt-1 block text-[11px] leading-snug text-fg-subtle">{m.summary}</span>
            <span className="mt-2 block text-[10px] text-fg-subtle">Best for: {m.best_for}</span>
            {m.enables_helpers ? (
              <Badge tone="primary" className="mt-2">
                Advanced helpers
              </Badge>
            ) : null}
          </button>
        ))}
        {modes.length === 0 ? <p className="text-xs text-fg-subtle">Loading quality modes…</p> : null}
      </div>
    </div>
  );
}

function ModelsStep({
  caps,
  opts,
  patch,
}: {
  caps: ModelCapabilities | null;
  opts: AnalysisOptions;
  patch: (p: Partial<AnalysisOptions>) => void;
}) {
  if (!caps) return <p className="text-xs text-fg-subtle">Loading model cards…</p>;
  const expert = opts.analysis_quality_mode === "expert";
  const selectedBackend = opts.pose_backend ?? caps.default_pose_backend;

  return (
    <div className="space-y-5">
      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-medium">
          <Cpu className="h-4 w-4 text-primary" /> Pose backend
          {!expert ? (
            <span className="text-[10px] font-normal text-fg-subtle">
              (auto-selected in {opts.analysis_quality_mode} mode — switch to Expert to pin one)
            </span>
          ) : null}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {caps.pose_backends.map((m) => (
            <PoseCard
              key={m.id}
              cap={m}
              selected={expert ? selectedBackend === m.id : m.selected_by_default}
              disabled={!expert || !m.available}
              onSelect={() => expert && m.available && patch({ pose_backend: m.id })}
            />
          ))}
        </div>
        {expert ? (
          <label className="mt-2 flex items-center gap-2 text-[11px] text-fg-subtle">
            <input
              type="checkbox"
              checked={!!opts.require_selected_pose_backend}
              onChange={(e) => patch({ require_selected_pose_backend: e.target.checked })}
            />
            Require this exact backend (fail instead of falling back)
          </label>
        ) : null}
      </div>

      <div>
        <div className="mb-2 text-sm font-medium">Helper models</div>
        <div className="grid gap-3 sm:grid-cols-2">
          {caps.helpers.map((m) => {
            const enabledKey =
              m.id === "sam2" ? "enable_sam2" : m.id === "depth" ? "enable_depth" : "enable_wham";
            const enabled = !!opts[enabledKey as keyof AnalysisOptions];
            return (
              <HelperCard
                key={m.id}
                cap={m}
                enabled={enabled}
                onToggle={(v) => patch({ [enabledKey]: v } as Partial<AnalysisOptions>)}
              />
            );
          })}
        </div>
        {opts.analysis_quality_mode !== "standard" ? (
          <label className="mt-2 flex items-center gap-2 text-[11px] text-fg-subtle">
            <input
              type="checkbox"
              checked={!!opts.require_advanced_helpers}
              onChange={(e) => patch({ require_advanced_helpers: e.target.checked })}
            />
            Require enabled helpers to be active (fail instead of degrading)
          </label>
        ) : null}
      </div>

      {opts.analysis_quality_mode === "expert" ? (
        <Field label="auto_best comparison mode" hint="Only used when the pose backend is Automatic.">
          <Select
            value={opts.auto_best_mode ?? caps.auto_best_mode}
            onChange={(e) => patch({ auto_best_mode: e.target.value })}
          >
            <option value="fast">Fast — run the single preferred backend</option>
            <option value="full">Full — compare all backends, pick the best</option>
          </Select>
        </Field>
      ) : null}
    </div>
  );
}

function PoseCard({
  cap,
  selected,
  disabled,
  onSelect,
}: {
  cap: ModelCapability;
  selected: boolean;
  disabled: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      onClick={onSelect}
      disabled={disabled}
      className={cn(
        "rounded-xl border p-3 text-left transition",
        selected ? "border-primary bg-primary/10" : "border-border bg-surface-2/40",
        disabled ? "cursor-default opacity-90" : "hover:border-primary/40",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{cap.name}</span>
        <Badge tone={statusTone(cap.status)}>{statusLabel(cap.status)}</Badge>
      </div>
      <p className="mt-1 text-[11px] leading-snug text-fg-subtle">{cap.what_it_does}</p>
      {cap.feet_keypoints ? (
        <span className="mt-1 inline-block text-[10px] text-good">✓ heel / foot-index keypoints</span>
      ) : null}
      {cap.limitations.map((l) => (
        <p key={l} className="mt-1 text-[10px] text-fg-subtle">
          • {l}
        </p>
      ))}
      {!cap.available && cap.fix_hint ? (
        <p className="mt-1 text-[10px] text-warn">Fix: {cap.fix_hint}</p>
      ) : null}
    </button>
  );
}

function HelperCard({
  cap,
  enabled,
  onToggle,
}: {
  cap: ModelCapability;
  enabled: boolean;
  onToggle: (v: boolean) => void;
}) {
  const usable = cap.available;
  return (
    <div
      className={cn(
        "rounded-xl border p-3",
        enabled && usable ? "border-primary bg-primary/10" : "border-border bg-surface-2/40",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{cap.name}</span>
        <Badge tone={statusTone(cap.status)}>{statusLabel(cap.status)}</Badge>
      </div>
      <p className="mt-1 text-[11px] leading-snug text-fg-subtle">{cap.what_it_does}</p>
      {cap.limitations.map((l) => (
        <p key={l} className="mt-1 text-[10px] text-fg-subtle">
          • {l}
        </p>
      ))}
      {!usable && cap.fix_hint ? <p className="mt-1 text-[10px] text-warn">Fix: {cap.fix_hint}</p> : null}
      <label
        className={cn(
          "mt-2 flex items-center gap-2 text-[11px]",
          usable ? "text-fg" : "cursor-not-allowed text-fg-subtle",
        )}
      >
        <input type="checkbox" disabled={!usable} checked={enabled && usable} onChange={(e) => onToggle(e.target.checked)} />
        {usable ? "Use in this analysis" : "Unavailable on this server"}
      </label>
    </div>
  );
}

function CalibrationStep({
  opts,
  patch,
  isUpload,
  patientCode,
  setPatientCode,
}: {
  opts: AnalysisOptions;
  patch: (p: Partial<AnalysisOptions>) => void;
  isUpload: boolean;
  patientCode: string;
  setPatientCode: (v: string) => void;
}) {
  return (
    <div className="space-y-4">
      {isUpload ? (
        <Field label="Patient code / initials *" hint="De-identified. No full names.">
          <Input value={patientCode} onChange={(e) => setPatientCode(e.target.value)} placeholder="e.g. JD-204" />
        </Field>
      ) : null}

      <div className="flex items-center gap-2 text-sm font-medium">
        <Ruler className="h-4 w-4 text-primary" /> Calibration
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {(
          [
            { id: "none", label: "None", desc: "Pixel-relative metrics only." },
            { id: "patient_height", label: "Patient height", desc: "Scale from the subject's height." },
            { id: "known_distance", label: "Known distance", desc: "Calibrated speed from a walked distance." },
          ] as { id: CalibrationMode; label: string; desc: string }[]
        ).map((c) => (
          <button
            key={c.id}
            onClick={() => patch({ calibration_mode: c.id })}
            className={cn(
              "rounded-xl border p-3 text-left transition",
              opts.calibration_mode === c.id
                ? "border-primary bg-primary/10"
                : "border-border bg-surface-2/40 hover:border-primary/40",
            )}
          >
            <span className="block text-sm font-medium">{c.label}</span>
            <span className="mt-1 block text-[10px] leading-snug text-fg-subtle">{c.desc}</span>
          </button>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {opts.calibration_mode === "patient_height" ? (
          <Field label="Patient height (cm)">
            <Input
              type="number"
              value={opts.patient_height_cm ?? ""}
              onChange={(e) => patch({ patient_height_cm: e.target.value ? Number(e.target.value) : null })}
              placeholder="e.g. 172"
            />
          </Field>
        ) : null}
        {opts.calibration_mode === "known_distance" ? (
          <Field label="Known walked distance (m)">
            <Input
              type="number"
              value={opts.known_distance_m ?? ""}
              onChange={(e) => patch({ known_distance_m: e.target.value ? Number(e.target.value) : null })}
              placeholder="e.g. 4.0"
            />
          </Field>
        ) : null}
        <Field label="Camera view">
          <Select value={opts.camera_view ?? "unknown"} onChange={(e) => patch({ camera_view: e.target.value as CameraView })}>
            <option value="sagittal">Side (sagittal)</option>
            <option value="coronal">Front/back (coronal)</option>
            <option value="unknown">Auto-detect</option>
          </Select>
        </Field>
      </div>
      <p className="text-[11px] text-fg-subtle">
        Relative depth / segmentation helpers do not provide calibrated clinical distance.
      </p>
    </div>
  );
}

function ReviewStep({
  opts,
  preflight,
  loading,
  isUpload,
  file,
  previewUrl,
  onPickFile,
  fileRef,
}: {
  opts: AnalysisOptions;
  preflight: PreflightResponse | null;
  loading: boolean;
  isUpload: boolean;
  file: File | null;
  previewUrl: string | null;
  onPickFile: (f: File) => void;
  fileRef: React.RefObject<HTMLInputElement>;
}) {
  return (
    <div className="space-y-4">
      {isUpload ? (
        <div>
          <div
            onClick={() => fileRef.current?.click()}
            className="flex cursor-pointer flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-surface-2/30 px-6 py-8 text-center transition hover:border-primary/50"
          >
            <Upload className="mb-2 h-6 w-6 text-primary" />
            <p className="text-sm font-medium">{file ? file.name : "Click to upload a walking video"}</p>
            <p className="mt-1 text-[11px] text-fg-subtle">MP4, MOV, WebM, AVI · up to 400 MB</p>
            <input
              ref={fileRef}
              type="file"
              accept="video/*"
              className="hidden"
              onChange={(e) => e.target.files?.[0] && onPickFile(e.target.files[0])}
            />
          </div>
          {previewUrl ? <video src={previewUrl} controls className="mt-3 w-full rounded-xl border border-border" /> : null}
        </div>
      ) : (
        <div className="flex items-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-3 py-2 text-xs text-fg">
          <Camera className="h-4 w-4 text-primary" />
          {opts.capture_source === "phone"
            ? "This setup will carry over to the phone-pairing screen."
            : "This setup will carry over to the live camera screen."}
        </div>
      )}

      <div className="rounded-xl border border-border bg-surface-2/40 p-4">
        <div className="mb-2 flex items-center justify-between">
          <span className="flex items-center gap-2 text-sm font-medium">
            <ShieldCheck className="h-4 w-4 text-primary" /> Preflight plan
          </span>
          {loading ? (
            <span className="flex items-center gap-1 text-xs text-fg-subtle">
              <Spinner className="h-3 w-3" /> checking…
            </span>
          ) : preflight ? (
            <Badge tone={preflight.can_start ? "good" : "danger"}>
              {preflight.can_start ? "Ready to run" : "Blocked"}
            </Badge>
          ) : null}
        </div>

        {preflight ? (
          <div className="space-y-3 text-xs">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-fg-subtle">
              <span>
                Mode: <span className="text-fg">{preflight.analysis_quality_mode}</span>
              </span>
              <span>
                Pose: <span className="text-fg">{preflight.pose_backend}</span>
                {preflight.pose_backend === "auto_best" ? ` (${preflight.auto_best_mode})` : ""}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" /> ~{preflight.estimated_runtime_sec}s
              </span>
            </div>

            {preflight.will_run.length ? (
              <div>
                <p className="mb-1 font-medium text-fg">Will run</p>
                <ul className="space-y-0.5">
                  {preflight.will_run.map((w) => (
                    <li key={w} className="flex items-center gap-1.5 text-good">
                      <CheckCircle2 className="h-3 w-3" /> {w}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {preflight.warnings.length ? (
              <div>
                <p className="mb-1 flex items-center gap-1 font-medium text-warn">
                  <AlertTriangle className="h-3 w-3" /> Warnings
                </p>
                <ul className="space-y-0.5 text-fg-subtle">
                  {preflight.warnings.map((w) => (
                    <li key={w}>• {w}</li>
                  ))}
                </ul>
              </div>
            ) : null}

            {preflight.blocked_reasons.length ? (
              <div>
                <p className="mb-1 font-medium text-danger">Blocked</p>
                <ul className="space-y-0.5 text-danger">
                  {preflight.blocked_reasons.map((w) => (
                    <li key={w}>• {w}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : !loading ? (
          <p className="text-xs text-fg-subtle">Preflight unavailable.</p>
        ) : null}
      </div>
    </div>
  );
}
