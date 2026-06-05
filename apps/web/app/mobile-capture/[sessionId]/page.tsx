"use client";

import { useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleDot, RotateCcw, Upload, Video } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/states";

type Phase = "loading" | "ready" | "recording" | "preview" | "uploading" | "done" | "error";
const MAX_SECONDS = 15;

const TIPS = [
  "Place the phone stable (lean it on something or use a stand).",
  "Frame the whole body and feet, head to toe.",
  "Walk sideways across the frame.",
  "Use good, even lighting.",
  "Record 5–15 seconds of steady walking.",
];

function pickMime(): string {
  const cands = ["video/mp4", "video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm"];
  return (
    cands.find((c) => typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(c)) ||
    "video/webm"
  );
}

export default function MobileCapturePage({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId;
  const tokenRef = useRef<string>("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const [phase, setPhase] = useState<Phase>("loading");
  const [error, setError] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(MAX_SECONDS);
  const [clip, setClip] = useState<{ blob: Blob; url: string; name: string } | null>(null);
  const [cameraOk, setCameraOk] = useState(false);

  useEffect(() => {
    tokenRef.current = new URLSearchParams(window.location.search).get("token") || "";
    let cancelled = false;
    (async () => {
      if (!tokenRef.current) {
        setPhase("error");
        setError("Missing pairing token. Re-scan the QR code on the desktop.");
        return;
      }
      // Mark the session connected (best-effort).
      try {
        await api.connectMobileSession(sessionId, tokenRef.current);
      } catch (e) {
        if (!cancelled) {
          setPhase("error");
          setError(e instanceof ApiError ? e.message : "This pairing session is no longer valid.");
        }
        return;
      }
      // Open the rear camera (fallback to any camera).
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
          audio: false,
        });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        setCameraOk(true);
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play().catch(() => {});
        }
        setPhase("ready");
      } catch {
        // Camera unavailable/denied — still allow gallery upload.
        setCameraOk(false);
        setPhase("ready");
      }
    })();
    return () => {
      cancelled = true;
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [sessionId]);

  function startRecording() {
    const stream = streamRef.current;
    if (!stream || typeof MediaRecorder === "undefined") {
      setError("Recording is not supported in this browser — use 'Choose from gallery'.");
      return;
    }
    chunksRef.current = [];
    const mime = pickMime();
    const rec = new MediaRecorder(stream, { mimeType: mime });
    recorderRef.current = rec;
    rec.ondataavailable = (e) => e.data.size && chunksRef.current.push(e.data);
    rec.onstop = () => {
      const ext = mime.includes("mp4") ? "mp4" : "webm";
      const blob = new Blob(chunksRef.current, { type: mime });
      setClip({ blob, url: URL.createObjectURL(blob), name: `phone_capture.${ext}` });
      setPhase("preview");
    };
    rec.start();
    setPhase("recording");
    setCountdown(MAX_SECONDS);
    const started = Date.now();
    const tick = setInterval(() => {
      const left = Math.max(0, MAX_SECONDS - Math.floor((Date.now() - started) / 1000));
      setCountdown(left);
      if (left <= 0) {
        clearInterval(tick);
        if (rec.state !== "inactive") rec.stop();
      }
    }, 250);
  }

  function stopRecording() {
    const rec = recorderRef.current;
    if (rec && rec.state !== "inactive") rec.stop();
  }

  function onGallery(file: File) {
    setClip({ blob: file, url: URL.createObjectURL(file), name: file.name || "phone_capture.mp4" });
    setPhase("preview");
  }

  async function upload() {
    if (!clip) return;
    setPhase("uploading");
    setError(null);
    try {
      await api.uploadFromPhone(sessionId, tokenRef.current, clip.blob, clip.name);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      setPhase("done");
    } catch (e) {
      setPhase("preview");
      setError(e instanceof ApiError ? e.message : "Upload failed. Check your connection and retry.");
    }
  }

  return (
    <div className="mx-auto min-h-[70vh] max-w-md space-y-4 pb-[env(safe-area-inset-bottom)]">
      <div className="text-center">
        <h1 className="text-lg font-semibold tracking-tight">Horalix — phone capture</h1>
        <p className="text-xs text-fg-subtle">Record a short walking clip. Results open on your desktop.</p>
      </div>

      {phase === "loading" ? (
        <Card><CardContent className="py-10"><Spinner /> <span className="ml-2 text-sm">Connecting…</span></CardContent></Card>
      ) : phase === "error" ? (
        <Card><CardContent className="py-8 text-center text-sm text-danger">{error}</CardContent></Card>
      ) : phase === "done" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <CheckCircle2 className="h-10 w-10 text-good" />
            <p className="text-base font-semibold">Upload complete</p>
            <p className="text-sm text-fg-subtle">
              You can return to your desktop — the analysis is running and the report will open there.
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Camera / preview surface */}
          <div className="relative overflow-hidden rounded-2xl border border-border bg-black/70">
            {clip ? (
              <video src={clip.url} controls playsInline className="block w-full" />
            ) : (
              <video ref={videoRef} muted playsInline className="block w-full" style={{ aspectRatio: "9 / 16", maxHeight: "60vh", objectFit: "cover", width: "100%" }} />
            )}
            {phase === "recording" ? (
              <div className="absolute left-3 top-3 flex items-center gap-1.5 rounded-md bg-danger/85 px-2 py-1 text-xs font-semibold text-white">
                <CircleDot className="h-3.5 w-3.5 animate-pulse" /> REC {countdown}s
              </div>
            ) : null}
          </div>

          {phase === "ready" && !clip ? (
            <Card>
              <CardContent className="pt-4">
                <p className="mb-2 text-xs font-medium text-fg">Before you record</p>
                <ul className="space-y-1 text-[12px] text-fg-subtle">
                  {TIPS.map((t) => <li key={t}>• {t}</li>)}
                </ul>
              </CardContent>
            </Card>
          ) : null}

          {error ? <p className="px-1 text-xs text-danger">{error}</p> : null}

          {/* Controls */}
          <div className="space-y-2">
            {phase === "preview" && clip ? (
              <div className="flex gap-2">
                <Button className="flex-1" onClick={upload} size="lg">
                  <Upload className="h-4 w-4" /> Upload &amp; analyse
                </Button>
                <Button
                  variant="secondary"
                  size="lg"
                  onClick={() => {
                    URL.revokeObjectURL(clip.url);
                    setClip(null);
                    setPhase("ready");
                  }}
                  aria-label="Re-record"
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
              </div>
            ) : phase === "uploading" ? (
              <Button className="w-full" size="lg" disabled>
                <Spinner /> Uploading…
              </Button>
            ) : phase === "recording" ? (
              <Button className="w-full" size="lg" variant="danger" onClick={stopRecording}>
                Stop recording
              </Button>
            ) : (
              <>
                {cameraOk ? (
                  <Button className="w-full" size="lg" onClick={startRecording}>
                    <Video className="h-4 w-4" /> Record {MAX_SECONDS}s clip
                  </Button>
                ) : (
                  <p className="text-center text-xs text-warn">
                    Camera unavailable — choose a video from your gallery instead.
                  </p>
                )}
                <Button
                  className="w-full"
                  size="lg"
                  variant="outline"
                  onClick={() => fileRef.current?.click()}
                >
                  <Upload className="h-4 w-4" /> Choose from gallery
                </Button>
                <input
                  ref={fileRef}
                  type="file"
                  accept="video/*"
                  capture="environment"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && onGallery(e.target.files[0])}
                />
              </>
            )}
          </div>

          <p className="px-1 text-center text-[11px] text-fg-subtle">
            For clinician review · not a diagnosis. Video is sent only to your configured backend.
          </p>
        </>
      )}
    </div>
  );
}
