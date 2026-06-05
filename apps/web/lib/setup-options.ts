import type { AnalysisOptions } from "@horalix/shared";

const STORAGE_KEY = "horalix.analysisSetup";

export const DEFAULT_OPTIONS: AnalysisOptions = {
  capture_source: "upload",
  protocol: "standard_walk",
  analysis_quality_mode: "standard",
  pose_backend: null,
  auto_best_mode: null,
  enable_sam2: null,
  enable_depth: null,
  enable_wham: null,
  require_selected_pose_backend: false,
  require_advanced_helpers: false,
  calibration_mode: "none",
  patient_height_cm: null,
  known_distance_m: null,
  camera_view: "unknown",
  notes: null,
};

/** Persist the chosen setup so phone/live capture inherit the same model selection. */
export function saveSetupOptions(options: AnalysisOptions): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(options));
  } catch {
    /* sessionStorage unavailable */
  }
}

export function loadSetupOptions(): AnalysisOptions | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as AnalysisOptions) : null;
  } catch {
    return null;
  }
}

export function clearSetupOptions(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** Map a backend/helper status string to a Badge tone + short label. */
export function statusTone(status: string): "good" | "warn" | "danger" | "muted" {
  if (status === "READY" || status === "WORKING" || status === "AVAILABLE") return "good";
  if (status === "AVAILABLE_NOT_SELECTED" || status === "NOT_REQUESTED") return "muted";
  if (
    status === "DOCKER_REQUIRED" ||
    status === "BLOCKED_LICENSED_ASSETS" ||
    status === "BLOCKED_CONFIG"
  )
    return "warn";
  return "danger";
}

export function statusLabel(status: string): string {
  const map: Record<string, string> = {
    READY: "Ready",
    AVAILABLE: "Installed",
    WORKING: "Active",
    AVAILABLE_NOT_SELECTED: "Available",
    DOCKER_REQUIRED: "Needs Docker",
    BLOCKED_LICENSED_ASSETS: "Needs license",
    BLOCKED_CONFIG: "Needs config",
    BLOCKED_WEIGHT: "Missing weights",
    BLOCKED_DEPENDENCY: "Not installed",
    BLOCKED_RUNTIME: "Unavailable",
    NOT_REQUESTED: "Off",
  };
  return map[status] ?? status;
}
