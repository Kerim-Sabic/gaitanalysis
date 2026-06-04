"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Camera, CircleDot, Upload, Video } from "lucide-react";
import { confidenceColor } from "@horalix/shared";
import {
  api,
  ApiError,
  isApiConfigured,
  type LiveFrameResult,
  type LiveStatus,
} from "@/lib/api";
import { ApiStatusIndicator } from "@/components/layout/api-status";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DisclaimerBar } from "@/components/ui/disclaimer";
import { Spinner } from "@/components/ui/states";
import { cn } from "@/lib/utils";

// Name-based skeleton edges (works for the 21-point COCO-17 + feet live payload).
const EDGES: [string, string][] = [
  ["left_shoulder", "right_shoulder"], ["left_shoulder", "left_elbow"], ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"], ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"], ["right_shoulder", "right_hip"], ["left_hip", "right_hip"],
  ["left_hip", "left_knee"], ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"], ["right_knee", "right_ankle"],
  ["nose", "left_shoulder"], ["nose", "right_shoulder"],
  ["left_ankle", "left_heel"], ["left_heel", "left_foot_index"], ["left_ankle", "left_foot_index"],
  ["right_ankle", "right_heel"], ["right_heel", "right_foot_index"], ["right_ankle", "right_foot_index"],
];
const RECORD_SECONDS = 10;

type Phase = "loading" | "ready" | "denied" | "unavailable" | "recording" | "uploading";

export default function LiveAnalysisPage() {
  const router = useRouter();
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const grabRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const busyRef = useRef(false);
  const stopRef = useRef(false);
  const frameTimes = useRef<number[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [phase, setPhase] = useState<Phase>("loading");
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [result, setResult] = useState<LiveFrameResult | null>(null);
  const [fps, setFps] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(RECORD_SECONDS);

  const draw = useCallback((r: LiveFrameResult) => {
    const canvas = overlayRef.current;
    if (!canvas) return;
    if (canvas.width !== r.width || canvas.height !== r.height) {
      canvas.width = r.width;
      canvas.height = r.height;
    }
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!r.valid_pose) return;
    const idx: Record<string, number> = {};
    r.keypoint_names.forEach((n, i) => (idx[n] = i));
    ctx.lineWidth = Math.max(2, r.width * 0.004);
    ctx.lineCap = "round";
    for (const [a, b] of EDGES) {
      const pa = r.keypoints[idx[a]];
      const pb = r.keypoints[idx[b]];
      if (!pa || !pb || pa[2] < 0.3 || pb[2] < 0.3) continue;
      ctx.strokeStyle = a.startsWith("left_") ? "#f2a93b" : "#5aa0f7";
      ctx.beginPath();
      ctx.moveTo(pa[0], pa[1]);
      ctx.lineTo(pb[0], pb[1]);
      ctx.stroke();
    }
    for (const [x, y, s] of r.keypoints) {
      if (s < 0.3) continue;
      ctx.fillStyle = confidenceColor(s);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(3, r.width * 0.006), 0, Math.PI * 2);
      ctx.fill();
    }
  }, []);

  // Capture loop: grab a frame, send to backend, draw the returned skeleton.
  useEffect(() => {
    const id = setInterval(async () => {
      const video = videoRef.current;
      const grab = grabRef.current;
      if (!video || !grab || busyRef.current || stopRef.current) return;
      if (video.readyState < 2 || !video.videoWidth) return;
      busyRef.current = true;
      try {
        const scale = Math.min(1, 640 / video.videoWidth);
        grab.width = Math.round(video.videoWidth * scale);
        grab.height = Math.round(video.videoHeight * scale);
        const gctx = grab.getContext("2d");
        if (!gctx) return;
        gctx.drawImage(video, 0, 0, grab.width, grab.height);
        const blob: Blob | null = await new Promise((res) => grab.toBlob(res, "image/jpeg", 0.6));
        if (!blob) return;
        const r = await api.liveFrame(blob, Date.now());
        setResult(r);
        draw(r);
        const now = performance.now();
        frameTimes.current.push(now);
        frameTimes.current = frameTimes.current.filter((t) => now - t < 2000);
        if (frameTimes.current.length > 1) {
          const span = (now - frameTimes.current[0]) / 1000;
          setFps(Math.round((frameTimes.current.length - 1) / Math.max(span, 0.001)));
        }
      } catch (e) {
        if (
          e instanceof ApiError &&
          (e.code === "api_not_configured" || e.code === "api_unreachable")
        ) {
          setError(e.message);
        }
      } finally {
        busyRef.current = false;
      }
    }, 90);
    return () => clearInterval(id);
  }, [draw]);

  // Init: check live availability, then open the camera.
  useEffect(() => {
    stopRef.current = false;
    grabRef.current = document.createElement("canvas");
    (async () => {
      if (!isApiConfigured()) {
        setPhase("unavailable");
        setError("API not configured. Set NEXT_PUBLIC_API_URL to enable live analysis.");
        return;
      }
      try {
        const s = await api.liveStatus();
        setStatus(s);
        if (!s.available) {
          setPhase("unavailable");
          setError(s.error || "Live preview model unavailable.");
          return;
        }
      } catch (e) {
        setPhase("unavailable");
        setError(
          e instanceof ApiError
            ? e.message
            : "Backend is offline or unreachable. Backend CORS must allow this Netlify domain.",
        );
        return;
      }
      if (!window.isSecureContext) {
        setPhase("denied");
        setError("Camera access requires HTTPS. Netlify provides HTTPS automatically.");
        return;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
          audio: false,
        });
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
        setPhase("ready");
      } catch {
        setPhase("denied");
        setError("Camera access was denied or unavailable.");
      }
    })();
    return () => {
      stopRef.current = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);

  function pickMime(): string {
    const cands = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4"];
    return cands.find((c) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(c)) || "video/webm";
  }

  async function startRecording() {
    const stream = streamRef.current;
    if (!stream) return;
    chunksRef.current = [];
    const mime = pickMime();
    const rec = new MediaRecorder(stream, { mimeType: mime });
    recorderRef.current = rec;
    rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
    rec.onstop = () => void uploadRecording(mime);
    rec.start();
    setPhase("recording");
    setCountdown(RECORD_SECONDS);
    const started = Date.now();
    const tick = setInterval(() => {
      const left = Math.max(0, RECORD_SECONDS - Math.floor((Date.now() - started) / 1000));
      setCountdown(left);
      if (left <= 0) {
        clearInterval(tick);
        if (rec.state !== "inactive") rec.stop();
      }
    }, 250);
  }

  async function uploadRecording(mime: string) {
    setPhase("uploading");
    try {
      const ext = mime.includes("mp4") ? "mp4" : "webm";
      const blob = new Blob(chunksRef.current, { type: mime });
      const pc = await api.createCase({
        patient_code: `LIVE-${Math.random().toString(36).slice(2, 6).toUpperCase()}`,
        indication: "Live camera capture",
      });
      const fd = new FormData();
      fd.append("case_id", pc.id);
      fd.append("test_type", "standard_walk");
      fd.append("camera_view", "sagittal");
      fd.append("file", blob, `live_capture.${ext}`);
      const video = await api.uploadVideo(fd);
      const prog = await api.startAnalysis({ video_id: video.id });
      router.push(`/analysis/${prog.analysis_id}`);
    } catch (e) {
      setPhase("ready");
      setError(
        e instanceof ApiError
          ? `${e.message}${e.code ? ` (${e.code})` : ""}`
          : "Upload of the recorded clip failed.",
      );
    }
  }

  const detected = result?.valid_pose ?? false;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Live camera analysis</h1>
          <p className="mt-1 max-w-2xl text-sm text-fg-subtle">
            Real-time pose preview for capture guidance. Final gait metrics are generated
            after the recorded clip is processed by the verified backend
            {status ? ` (${status.final_backend})` : ""}.
          </p>
        </div>
        <Badge tone={detected ? "good" : "warn"}>
          {status?.available
            ? `Live AI Preview — ${status.backend}`
            : "Live preview unavailable"}
        </Badge>
      </div>
      <ApiStatusIndicator />

      {phase === "unavailable" || phase === "denied" ? (
        <Card>
          <CardContent className="space-y-3 pt-6">
            <p className="text-sm text-danger">{error}</p>
            <p className="text-xs text-fg-subtle">
              Configure a reachable FastAPI backend before using live preview or upload analysis.
            </p>
            <Link href="/analyze">
              <Button variant="secondary">
                <Upload className="h-4 w-4" /> Go to upload analysis
              </Button>
            </Link>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Live preview</CardTitle>
              <span className="text-[11px] text-fg-subtle">
                Left = amber · Right = blue · point colour = tracking confidence
              </span>
            </CardHeader>
            <CardContent>
              <div className="relative overflow-hidden rounded-2xl border border-border bg-black/60">
                <video ref={videoRef} className="block w-full" muted playsInline />
                <canvas ref={overlayRef} className="absolute inset-0 h-full w-full" />
                {phase === "loading" ? (
                  <div className="absolute inset-0 flex items-center justify-center text-white/80">
                    <Spinner /> <span className="ml-2 text-sm">Starting camera…</span>
                  </div>
                ) : null}
                <div className="pointer-events-none absolute left-3 top-3 flex flex-wrap gap-2">
                  <span className="rounded-md bg-black/55 px-2 py-1 text-[10px] font-medium text-white/90">
                    {detected ? "Pose detected" : "No pose"} · {fps} FPS · {result?.inference_ms ?? 0}ms
                  </span>
                  <span className="rounded-md bg-black/55 px-2 py-1 text-[10px] font-medium text-white/90">
                    conf {(result?.mean_confidence ?? 0).toFixed(2)}
                  </span>
                </div>
                {phase === "recording" ? (
                  <div className="absolute right-3 top-3 flex items-center gap-1.5 rounded-md bg-danger/80 px-2 py-1 text-[11px] font-semibold text-white">
                    <CircleDot className="h-3.5 w-3.5 animate-pulse" /> REC {countdown}s
                  </div>
                ) : null}
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-3">
                <Button
                  onClick={startRecording}
                  disabled={phase !== "ready" || !detected}
                  aria-label="Record gait test"
                >
                  {phase === "uploading" ? <Spinner /> : <Video className="h-4 w-4" />}
                  {phase === "recording"
                    ? `Recording… ${countdown}s`
                    : phase === "uploading"
                      ? "Processing…"
                      : `Record ${RECORD_SECONDS}s gait test`}
                </Button>
                <Link href="/analyze">
                  <Button variant="outline" aria-label="Upload a video instead">
                    <Upload className="h-4 w-4" /> Upload instead
                  </Button>
                </Link>
                {!detected && phase === "ready" ? (
                  <span className="text-xs text-warn">Recording enables once a pose is detected.</span>
                ) : null}
              </div>
              {error && phase === "ready" ? (
                <p className="mt-2 text-xs text-danger">{error}</p>
              ) : null}
            </CardContent>
          </Card>

          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Capture coach</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 pt-0">
                <Coach label="Pose detected" ok={detected} />
                <Coach label="Left leg visible" ok={!!result?.left_leg_visible} />
                <Coach label="Right leg visible" ok={!!result?.right_leg_visible} />
                <Coach label="Feet visible" ok={!!result?.feet_visible} />
                <Coach label="Good capture" ok={!!result?.good_capture} />
                {result?.warnings?.length ? (
                  <ul className="mt-2 space-y-1 text-[11px] text-warn">
                    {result.warnings.map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2 text-[11px] text-good">
                    Good capture — walk sideways across the frame, then record.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Live model</CardTitle>
              </CardHeader>
              <CardContent className="pt-0 text-xs text-fg-subtle">
                <Row label="Backend" value={status?.backend ?? "—"} />
                <Row label="Keypoint source" value={result?.keypoint_source ?? status?.keypoint_source ?? "—"} />
                <Row label="Simulated data" value={(result?.simulated_data_used ?? false) ? "Yes" : "No"} />
                <Row label="Live FPS" value={String(fps)} />
                <Row label="Final backend" value={status?.final_backend ?? "—"} />
                <p className="mt-2 leading-snug">
                  Live preview guides capture only. The recorded clip is analysed by the
                  verified backend for the report.
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      <DisclaimerBar />
    </div>
  );
}

function Coach({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-fg-subtle">{label}</span>
      <span className={ok ? "text-good" : "text-warn"}>{ok ? "✓" : "—"}</span>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/50 py-1.5 last:border-0">
      <span className="text-fg-subtle">{label}</span>
      <span className="font-medium text-fg">{value}</span>
    </div>
  );
}
