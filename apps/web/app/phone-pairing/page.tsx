"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { Check, Copy, RefreshCw, Smartphone, Upload } from "lucide-react";
import { api, ApiError, type MobileSession } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DisclaimerBar } from "@/components/ui/disclaimer";
import { CenteredSpinner, Spinner } from "@/components/ui/states";

const STATUS_LABEL: Record<MobileSession["status"], string> = {
  waiting: "Waiting for phone…",
  phone_connected: "Phone connected — record on your phone",
  uploading: "Receiving video from phone…",
  analyzing: "Analysing gait…",
  completed: "Analysis complete",
  error: "Capture failed",
  expired: "QR code expired",
  cancelled: "Cancelled on phone",
};

function appOrigin(): string {
  const env = process.env.NEXT_PUBLIC_APP_URL?.trim().replace(/\/+$/, "");
  if (env) return env;
  return typeof window !== "undefined" ? window.location.origin : "";
}

export default function PhonePairingPage() {
  const router = useRouter();
  const [created, setCreated] = useState<{ id: string; token: string; path: string } | null>(null);
  const [session, setSession] = useState<MobileSession | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState<number>(0);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const start = useCallback(async () => {
    setError(null);
    setSession(null);
    setCreated(null);
    try {
      const s = await api.createMobileSession();
      setCreated({ id: s.session_id, token: s.pairing_token, path: s.mobile_url_path });
      setSecondsLeft(Math.max(0, Math.round((new Date(s.expires_at).getTime() - Date.now()) / 1000)));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not reach the backend to create a session.");
    }
  }, []);

  useEffect(() => {
    void start();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [start]);

  // Poll session status.
  useEffect(() => {
    if (!created) return;
    let cancelled = false;
    async function poll() {
      try {
        const s = await api.getMobileSession(created!.id, created!.token);
        if (cancelled) return;
        setSession(s);
        setSecondsLeft(s.seconds_remaining);
        if (s.status === "completed" && s.analysis_id) {
          router.push(`/analysis/${s.analysis_id}`);
          return;
        }
        if (["error", "expired", "cancelled"].includes(s.status)) return; // stop polling
        timer.current = setTimeout(poll, 1500);
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Lost connection to the backend.");
        timer.current = setTimeout(poll, 3000);
      }
    }
    poll();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [created, router]);

  const fullUrl = created ? `${appOrigin()}${created.path}` : "";
  const status = session?.status ?? "waiting";
  const active = ["waiting", "phone_connected", "uploading", "analyzing"].includes(status);
  const mmss = `${Math.floor(secondsLeft / 60)}:${String(secondsLeft % 60).padStart(2, "0")}`;

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(fullUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Capture with your phone</h1>
        <p className="mt-1 max-w-xl text-sm text-fg-subtle">
          Scan the code with your phone to record a walking clip on a better camera.
          The video is analysed by the verified backend and the result opens here.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Scan to pair</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            {error ? (
              <div className="w-full rounded-xl border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
                {error}
              </div>
            ) : null}
            {created ? (
              <>
                <div className="rounded-2xl bg-white p-4 shadow-soft">
                  <QRCodeSVG value={fullUrl} size={200} level="M" includeMargin />
                </div>
                <div className="flex w-full items-center gap-2">
                  <input
                    readOnly
                    value={fullUrl}
                    className="h-9 flex-1 truncate rounded-lg border border-border bg-surface-2 px-2 text-xs text-fg-subtle"
                  />
                  <Button size="sm" variant="secondary" onClick={copyLink} aria-label="Copy link">
                    {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                  </Button>
                </div>
                <p className="text-[11px] text-fg-subtle">
                  Expires in <span className="tabular font-medium">{mmss}</span> · no account or app needed
                </p>
              </>
            ) : (
              <CenteredSpinner label="Creating secure session…" />
            )}
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>Session status</CardTitle>
              <Badge
                tone={
                  status === "completed"
                    ? "good"
                    : status === "error" || status === "expired"
                      ? "danger"
                      : active
                        ? "primary"
                        : "muted"
                }
              >
                {STATUS_LABEL[status]}
              </Badge>
            </CardHeader>
            <CardContent className="space-y-3">
              <ol className="space-y-2 text-sm">
                <Step done={status !== "waiting"} active={status === "waiting"} label="Scan the QR with your phone" />
                <Step
                  done={["uploading", "analyzing", "completed"].includes(status)}
                  active={status === "phone_connected"}
                  label="Record a 5–15 s walking clip"
                />
                <Step
                  done={["analyzing", "completed"].includes(status)}
                  active={status === "uploading"}
                  label="Upload to the verified backend"
                />
                <Step done={status === "completed"} active={status === "analyzing"} label="AI gait analysis + report" />
              </ol>
              {status === "analyzing" ? (
                <p className="flex items-center gap-2 text-xs text-fg-subtle">
                  <Spinner /> Analysing — the result will open automatically.
                </p>
              ) : null}
              {["error", "expired", "cancelled"].includes(status) ? (
                <Button variant="secondary" size="sm" onClick={start}>
                  <RefreshCw className="h-4 w-4" /> New QR code
                </Button>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-2 pt-5 text-xs text-fg-subtle">
              <p className="flex items-center gap-2 font-medium text-fg">
                <Smartphone className="h-4 w-4 text-primary" /> No app, no account
              </p>
              <p>
                The phone link is single-use and expires automatically. Videos are sent only to
                your configured backend for analysis. De-identify subjects (codes/initials).
              </p>
              <Link href="/analyze" className="inline-flex items-center gap-1 text-primary hover:underline">
                <Upload className="h-3.5 w-3.5" /> Prefer to upload from this device
              </Link>
            </CardContent>
          </Card>
        </div>
      </div>

      <DisclaimerBar />
    </div>
  );
}

function Step({ done, active, label }: { done: boolean; active: boolean; label: string }) {
  return (
    <li className="flex items-center gap-3">
      <span
        className={
          "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-[11px] " +
          (done
            ? "border-good bg-good/15 text-good"
            : active
              ? "border-primary bg-primary/15 text-primary"
              : "border-border text-fg-subtle")
        }
      >
        {done ? <Check className="h-3.5 w-3.5" /> : active ? <Spinner className="h-3 w-3" /> : "•"}
      </span>
      <span className={done || active ? "text-fg" : "text-fg-subtle"}>{label}</span>
    </li>
  );
}
