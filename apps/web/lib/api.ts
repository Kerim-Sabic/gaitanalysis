import type {
  AnalysisProgress,
  CaseSummary,
  DemoPreset,
  GaitAnalysisResult,
  KeypointStat,
  ModelInfo,
  ModelStatus,
  ModelVerifyResult,
  PatientCase,
  PatientCaseCreate,
  PoseTrack,
  QualityResult,
  TestType,
  VideoMetadata,
} from "@horalix/shared";

const DEFAULT_TIMEOUT_MS = 30_000;
const UPLOAD_TIMEOUT_MS = 180_000;
const LIVE_TIMEOUT_MS = 10_000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function getApiBaseUrl(): string | null {
  const value = process.env.NEXT_PUBLIC_API_URL?.trim().replace(/\/+$/, "");
  if (!value) return null;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? value : null;
  } catch {
    return null;
  }
}

export function isApiConfigured(): boolean {
  return getApiBaseUrl() !== null;
}

export function getApiHostname(): string | null {
  const base = getApiBaseUrl();
  return base ? new URL(base).hostname : null;
}

function getApiUrl(path: string): string {
  const base = getApiBaseUrl();
  if (!base) {
    throw new ApiError(
      "API not configured. Set NEXT_PUBLIC_API_URL to the public FastAPI backend URL.",
      0,
      "api_not_configured",
    );
  }
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}

type ApiRequestInit = RequestInit & { timeoutMs?: number };

export async function apiFetch<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const controller = new AbortController();
  const timeout = window.setTimeout(
    () => controller.abort(),
    init.timeoutMs ?? DEFAULT_TIMEOUT_MS,
  );

  try {
    const res = await fetch(getApiUrl(path), {
      ...init,
      headers: {
        ...(init.body && !(init.body instanceof FormData)
          ? { "Content-Type": "application/json" }
          : {}),
        ...init.headers,
      },
      cache: "no-store",
      signal: controller.signal,
    });

    if (!res.ok) {
      let detail: unknown = res.statusText;
      try {
        const body = await res.json();
        detail = body.detail ?? body;
      } catch {
        // Keep the HTTP status text when the response is not JSON.
      }

      const structured =
        detail && typeof detail === "object"
          ? (detail as {
              code?: string;
              message?: string;
              user_message?: string;
              suggested_fix?: string;
            })
          : null;
      const code = structured?.code;
      const serverMessage =
        structured?.user_message || structured?.message || String(detail || res.statusText);
      const isUpload = path === "/videos/upload";

      if (res.status === 413) {
        throw new ApiError(
          "Video upload is larger than the backend limit. Choose a shorter or compressed clip.",
          res.status,
          code || "upload_too_large",
          detail,
        );
      }
      if (isUpload && (res.status === 415 || code === "video_invalid")) {
        throw new ApiError(
          "The backend rejected this video format or codec. Browser recordings may be WebM; enable WebM support or convert the clip to H.264 MP4.",
          res.status,
          code || "video_invalid",
          detail,
        );
      }
      if (res.status >= 500) {
        throw new ApiError(
          `The backend could not complete the request. ${serverMessage}`,
          res.status,
          code || "backend_error",
          detail,
        );
      }
      throw new ApiError(serverMessage, res.status, code, detail);
    }

    return (await res.json()) as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        "The backend request timed out. Check the backend status and try again.",
        0,
        "api_timeout",
      );
    }
    throw new ApiError(
      "Backend is offline or unreachable. If this is a Netlify deployment, backend CORS must allow this Netlify domain.",
      0,
      "api_unreachable",
    );
  } finally {
    window.clearTimeout(timeout);
  }
}

export interface ApiHealth {
  status: string;
  pose_backend_pref: string;
  models: {
    real_analysis_available: boolean;
    active_backend: string;
  };
  demo_mode: boolean;
}

export interface KeypointSeries {
  analysis_id: string;
  analysis_mode: string;
  keypoint_source: string;
  keypoint_stats: KeypointStat[];
  track: PoseTrack;
}

export interface LiveStatus {
  available: boolean;
  backend: string;
  model_variant: string;
  model_version: string;
  model_file: string;
  error?: string | null;
  keypoint_source: string;
  simulated_data_used: boolean;
  final_backend: string;
}

export interface LiveFrameResult {
  frame_index: number;
  timestamp: number;
  width: number;
  height: number;
  keypoints: number[][];
  keypoint_names: string[];
  valid_pose: boolean;
  mean_confidence: number;
  left_leg_visible: boolean;
  right_leg_visible: boolean;
  feet_visible: boolean;
  inference_ms: number;
  backend: string;
  keypoint_source: string;
  simulated_data_used: boolean;
  warnings: string[];
  good_capture: boolean;
}

export const getApiHealth = () => apiFetch<ApiHealth>("/health");
export const getLiveStatus = () => apiFetch<LiveStatus>("/live/status");

export const api = {
  health: getApiHealth,

  // Cases
  createCase: (payload: PatientCaseCreate) =>
    apiFetch<PatientCase>("/cases", { method: "POST", body: JSON.stringify(payload) }),
  listCases: () => apiFetch<CaseSummary[]>("/cases"),
  getCase: (id: string) => apiFetch<PatientCase>(`/cases/${id}`),

  // Videos
  uploadVideo: (form: FormData) =>
    apiFetch<VideoMetadata>("/videos/upload", {
      method: "POST",
      body: form,
      timeoutMs: UPLOAD_TIMEOUT_MS,
    }),
  getQuality: (videoId: string) => apiFetch<QualityResult>(`/videos/${videoId}/quality`),
  rawVideoUrl: (videoId: string) => getApiUrl(`/videos/${videoId}/raw`),

  // Models (control plane)
  modelStatus: () => apiFetch<ModelStatus>("/models/status"),
  modelVerify: () => apiFetch<ModelVerifyResult>("/models/verify"),

  // Analysis
  startAnalysis: (payload: {
    video_id: string;
    test_type?: TestType;
    demo_preset?: string;
  }) =>
    apiFetch<AnalysisProgress>("/analysis/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startDemo: (preset: DemoPreset) =>
    apiFetch<AnalysisProgress>("/analysis/demo", {
      method: "POST",
      body: JSON.stringify({ preset }),
    }),
  getStatus: (id: string) => apiFetch<AnalysisProgress>(`/analysis/${id}/status`),
  getResult: (id: string) => apiFetch<GaitAnalysisResult>(`/analysis/${id}/result`),
  getPose: (id: string) => apiFetch<PoseTrack>(`/analysis/${id}/pose`),
  getKeypoints: (id: string) => apiFetch<KeypointSeries>(`/analysis/${id}/keypoints`),
  getAnalysisModelStatus: (id: string) =>
    apiFetch<{ model_info: ModelInfo }>(`/analysis/${id}/model-status`),
  reportPdfUrl: (id: string) => getApiUrl(`/analysis/${id}/report.pdf`),
  reportJsonUrl: (id: string) => getApiUrl(`/analysis/${id}/report.json`),
  overlayVideoUrl: (id: string) => getApiUrl(`/analysis/${id}/overlay-video`),

  // Live (near-real-time) preview
  liveStatus: getLiveStatus,
  liveFrame: (blob: Blob, frameIndex: number) => {
    const fd = new FormData();
    fd.append("file", blob, "frame.jpg");
    return apiFetch<LiveFrameResult>(`/live/frame?frame_index=${frameIndex}`, {
      method: "POST",
      body: fd,
      timeoutMs: LIVE_TIMEOUT_MS,
    });
  },
};
