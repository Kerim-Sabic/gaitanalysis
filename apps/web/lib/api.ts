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

// Browser calls go through the Next rewrite at /api -> FastAPI.
const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public data?: unknown,
  ) {
    super(message);
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init?.body && !(init.body instanceof FormData)
        ? { "Content-Type": "application/json" }
        : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? detail;
    } catch {
      /* ignore */
    }
    // FastAPI detail may be a structured object (e.g. model_unavailable).
    if (detail && typeof detail === "object") {
      const d = detail as { message?: string; code?: string };
      throw new ApiError(d.message ?? "Request failed", res.status, d.code, detail);
    }
    throw new ApiError(String(detail), res.status);
  }
  return (await res.json()) as T;
}

export interface KeypointSeries {
  analysis_id: string;
  analysis_mode: string;
  keypoint_source: string;
  keypoint_stats: KeypointStat[];
  track: PoseTrack;
}

export const api = {
  // Cases
  createCase: (payload: PatientCaseCreate) =>
    req<PatientCase>("/cases", { method: "POST", body: JSON.stringify(payload) }),
  listCases: () => req<CaseSummary[]>("/cases"),
  getCase: (id: string) => req<PatientCase>(`/cases/${id}`),

  // Videos
  uploadVideo: (form: FormData) =>
    req<VideoMetadata>("/videos/upload", { method: "POST", body: form }),
  getQuality: (videoId: string) => req<QualityResult>(`/videos/${videoId}/quality`),
  rawVideoUrl: (videoId: string) => `${BASE}/videos/${videoId}/raw`,

  // Models (control plane)
  modelStatus: () => req<ModelStatus>("/models/status"),
  modelVerify: () => req<ModelVerifyResult>("/models/verify"),

  // Analysis
  startAnalysis: (payload: {
    video_id: string;
    test_type?: TestType;
    demo_preset?: string;
  }) =>
    req<AnalysisProgress>("/analysis/start", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  startDemo: (preset: DemoPreset) =>
    req<AnalysisProgress>("/analysis/demo", {
      method: "POST",
      body: JSON.stringify({ preset }),
    }),
  getStatus: (id: string) => req<AnalysisProgress>(`/analysis/${id}/status`),
  getResult: (id: string) => req<GaitAnalysisResult>(`/analysis/${id}/result`),
  getPose: (id: string) => req<PoseTrack>(`/analysis/${id}/pose`),
  getKeypoints: (id: string) => req<KeypointSeries>(`/analysis/${id}/keypoints`),
  getAnalysisModelStatus: (id: string) =>
    req<{ model_info: ModelInfo }>(`/analysis/${id}/model-status`),
  reportPdfUrl: (id: string) => `${BASE}/analysis/${id}/report.pdf`,
  reportJsonUrl: (id: string) => `${BASE}/analysis/${id}/report.json`,
  overlayVideoUrl: (id: string) => `${BASE}/analysis/${id}/overlay-video`,
};
