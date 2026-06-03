"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import { confidenceColor, type GaitEvent, type PoseTrack } from "@horalix/shared";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type ColorMode = "default" | "tracking" | "movement" | "both" | "none";

type Toggles = {
  skeleton: boolean;
  labels: boolean;
  events: boolean;
};

const LEFT = "#f2a93b";
const RIGHT = "#5aa0f7";
const GAIT_LABELS: Record<string, string> = {
  left_hip: "L hip", right_hip: "R hip", left_knee: "L knee", right_knee: "R knee",
  left_ankle: "L ankle", right_ankle: "R ankle", left_heel: "L heel", right_heel: "R heel",
  left_foot_index: "L toe", right_foot_index: "R toe",
};

export function SkeletonCanvas({
  pose,
  events,
  videoUrl,
  isDemo,
  colorMode = "default",
  movementColors,
  selectedKeypoint = null,
  onSelectKeypoint,
}: {
  pose: PoseTrack;
  events: GaitEvent[];
  videoUrl?: string | null;
  isDemo: boolean;
  colorMode?: ColorMode;
  movementColors?: Record<number, string>;
  selectedKeypoint?: number | null;
  onSelectKeypoint?: (index: number) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const rafRef = useRef<number | null>(null);
  const lastTsRef = useRef<number>(0);
  const tRef = useRef<number>(0);

  const [playing, setPlaying] = useState(true);
  const [t, setT] = useState(0);
  const [toggles, setToggles] = useState<Toggles>({
    skeleton: true,
    labels: false,
    events: true,
  });

  const duration = pose.frame_count > 0 ? pose.frames[pose.frame_count - 1].t : 0;
  const leftSet = useMemo(() => new Set(pose.left_indices), [pose.left_indices]);

  const frameAt = useCallback(
    (time: number) => {
      const frames = pose.frames;
      let lo = 0;
      let hi = frames.length - 1;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (frames[mid].t < time) lo = mid + 1;
        else hi = mid;
      }
      return frames[lo];
    },
    [pose.frames],
  );

  const nearbyEvent = useCallback(
    (time: number): GaitEvent | null => {
      let best: GaitEvent | null = null;
      let bestDt = 0.12;
      for (const e of events) {
        const dt = Math.abs(e.timestamp - time);
        if (dt < bestDt) {
          bestDt = dt;
          best = e;
        }
      }
      return best;
    },
    [events],
  );

  const fillFor = useCallback(
    (j: number, score: number): string => {
      switch (colorMode) {
        case "tracking":
        case "both":
          return confidenceColor(score);
        case "movement":
          return movementColors?.[j] ?? "#64748b";
        case "none":
          return "#94a3b8";
        default:
          return leftSet.has(j) ? LEFT : RIGHT;
      }
    },
    [colorMode, movementColors, leftSet],
  );

  const draw = useCallback(
    (time: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const W = canvas.width;
      const H = canvas.height;

      ctx.clearRect(0, 0, W, H);
      if (!videoUrl) {
        const g = ctx.createLinearGradient(0, 0, 0, H);
        g.addColorStop(0, "#10192c");
        g.addColorStop(1, "#1b2740");
        ctx.fillStyle = g;
        ctx.fillRect(0, 0, W, H);
        ctx.strokeStyle = "rgba(255,255,255,0.06)";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, H * 0.84);
        ctx.lineTo(W, H * 0.84);
        ctx.stroke();
      }

      const frame = frameAt(time);
      if (!frame) return;
      const kp = frame.keypoints;
      const interp = new Set(frame.interp ?? []);

      if (toggles.skeleton) {
        ctx.lineWidth = Math.max(2, W * 0.004);
        ctx.lineCap = "round";
        for (const [a, b] of pose.skeleton_edges) {
          const pa = kp[a];
          const pb = kp[b];
          if (!pa || !pb || pa[2] < 0.2 || pb[2] < 0.2) continue;
          ctx.strokeStyle =
            colorMode === "default" || colorMode === "none"
              ? leftSet.has(a)
                ? LEFT
                : RIGHT
              : "rgba(180,195,215,0.55)";
          ctx.globalAlpha = 0.9;
          ctx.beginPath();
          ctx.moveTo(pa[0], pa[1]);
          ctx.lineTo(pb[0], pb[1]);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;

        for (let j = 0; j < kp.length; j++) {
          const [x, y, s] = kp[j];
          if (s < 0.1) continue;
          const r = Math.max(3, W * 0.006) + s * 3;
          ctx.fillStyle = fillFor(j, s);
          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fill();

          // "both" mode: movement ring around tracking-colored fill.
          if (colorMode === "both" && movementColors?.[j]) {
            ctx.strokeStyle = movementColors[j];
            ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.arc(x, y, r + 3, 0, Math.PI * 2);
            ctx.stroke();
          }
          // interpolated -> dashed ring (distinct from reliable points).
          if (interp.has(j)) {
            ctx.strokeStyle = "#cbd5e1";
            ctx.lineWidth = 1.5;
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.arc(x, y, r + 4, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
          }
          // selected highlight.
          if (selectedKeypoint === j) {
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.arc(x, y, r + 7, 0, Math.PI * 2);
            ctx.stroke();
          }
          if (toggles.labels && GAIT_LABELS[pose.keypoint_names[j]]) {
            ctx.fillStyle = "rgba(255,255,255,0.85)";
            ctx.font = `${Math.round(W * 0.014)}px ui-sans-serif, sans-serif`;
            ctx.fillText(GAIT_LABELS[pose.keypoint_names[j]], x + 8, y - 6);
          }
        }
      }

      if (toggles.events) {
        const ev = nearbyEvent(time);
        if (ev) {
          ctx.fillStyle = "rgba(90,220,120,0.95)";
          ctx.font = `${Math.round(W * 0.02)}px ui-sans-serif, sans-serif`;
          ctx.fillText(`${ev.type.replace("_", " ")} · ${ev.side ?? ""}`, 16, 34);
          ctx.beginPath();
          ctx.arc(W - 26, 26, 9, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    },
    [colorMode, fillFor, frameAt, leftSet, movementColors, nearbyEvent, pose.keypoint_names,
     pose.skeleton_edges, selectedKeypoint, toggles, videoUrl],
  );

  useEffect(() => {
    function loop(ts: number) {
      const video = videoRef.current;
      let nextT = tRef.current;
      if (video && videoUrl) {
        nextT = video.currentTime;
      } else if (playing) {
        const dt = lastTsRef.current ? (ts - lastTsRef.current) / 1000 : 0;
        nextT = tRef.current + dt;
        if (nextT > duration) nextT = 0;
      }
      lastTsRef.current = ts;
      tRef.current = nextT;
      setT(nextT);
      draw(nextT);
      rafRef.current = requestAnimationFrame(loop);
    }
    rafRef.current = requestAnimationFrame(loop);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      lastTsRef.current = 0;
    };
  }, [draw, duration, playing, videoUrl]);

  function togglePlay() {
    const video = videoRef.current;
    if (video && videoUrl) {
      if (playing) video.pause();
      else void video.play();
    }
    setPlaying((p) => !p);
  }

  function scrub(value: number) {
    tRef.current = value;
    setT(value);
    const video = videoRef.current;
    if (video && videoUrl) video.currentTime = value;
    draw(value);
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!onSelectKeypoint) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const sx = canvas.width / rect.width;
    const sy = canvas.height / rect.height;
    const mx = (e.clientX - rect.left) * sx;
    const my = (e.clientY - rect.top) * sy;
    const frame = frameAt(tRef.current);
    let best = -1;
    let bestD = (canvas.width * 0.04) ** 2;
    frame.keypoints.forEach(([x, y, s], j) => {
      if (s < 0.1) return;
      const d = (x - mx) ** 2 + (y - my) ** 2;
      if (d < bestD) {
        bestD = d;
        best = j;
      }
    });
    if (best >= 0) onSelectKeypoint(best);
  }

  const frame = frameAt(t);

  return (
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-2xl border border-border bg-black/40">
        {videoUrl ? (
          <video
            ref={videoRef}
            src={videoUrl}
            className="block w-full"
            muted
            playsInline
            loop
            autoPlay
            style={{ aspectRatio: `${pose.width} / ${pose.height}` }}
          />
        ) : null}
        <canvas
          ref={canvasRef}
          width={pose.width}
          height={pose.height}
          onClick={handleClick}
          className={cn(
            "w-full",
            videoUrl ? "absolute inset-0" : "block",
            onSelectKeypoint ? "cursor-pointer" : "",
          )}
          style={{ aspectRatio: `${pose.width} / ${pose.height}` }}
        />
        <div className="pointer-events-none absolute left-3 top-3 rounded-md bg-black/55 px-2 py-1 text-[10px] font-medium text-white/90">
          {isDemo ? "DEMO · simulated keypoints" : "Real AI keypoints"} · conf{" "}
          {(frame?.mean_confidence ?? 0).toFixed(2)}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button size="icon" variant="secondary" onClick={togglePlay} aria-label="Play/pause">
          {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        </Button>
        <div className="relative flex-1">
          <input
            type="range"
            min={0}
            max={duration || 1}
            step={0.01}
            value={t}
            onChange={(e) => scrub(Number(e.target.value))}
            className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-muted accent-primary"
          />
          <div className="pointer-events-none absolute inset-x-0 top-1/2 -translate-y-1/2">
            {events
              .filter((e) => e.type === "heel_strike")
              .map((e, i) => (
                <span
                  key={i}
                  className="absolute h-2 w-0.5 -translate-y-1/2 rounded bg-good/70"
                  style={{ left: `${(e.timestamp / (duration || 1)) * 100}%` }}
                />
              ))}
          </div>
        </div>
        <span className="tabular w-20 text-right text-xs text-fg-subtle">
          {t.toFixed(2)}s / {duration.toFixed(1)}s
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {(
          [
            ["skeleton", "Skeleton"],
            ["events", "Gait events"],
            ["labels", "Joint labels"],
          ] as [keyof Toggles, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            onClick={() => setToggles((s) => ({ ...s, [key]: !s[key] }))}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition",
              toggles[key]
                ? "border-primary/40 bg-primary/15 text-primary"
                : "border-border bg-surface-2 text-fg-subtle hover:text-fg",
            )}
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
