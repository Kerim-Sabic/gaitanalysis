import type {
  AnalysisProgress,
  CaseSummary,
  DemoPreset,
  GaitAnalysisResult,
  PatientCase,
  PatientCaseCreate,
  PoseTrack,
  QualityResult,
  TestType,
  VideoMetadata,
} from "@horalix/shared";

// Browser calls go through the Next rewrite at /api -> FastAPI.
const BASE = "/api";

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
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
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

  // Analysis
  startAnalysis: (payload: {
    video_id: string;
    test_type?: TestType;
    demo_preset?: string;
  }) => req<AnalysisProgress>("/analysis/start", { method: "POST", body: JSON.stringify(payload) }),
  startDemo: (preset: DemoPreset) =>
    req<AnalysisProgress>("/analysis/demo", {
      method: "POST",
      body: JSON.stringify({ preset }),
    }),
  getStatus: (id: string) => req<AnalysisProgress>(`/analysis/${id}/status`),
  getResult: (id: string) => req<GaitAnalysisResult>(`/analysis/${id}/result`),
  getPose: (id: string) => req<PoseTrack>(`/analysis/${id}/pose`),
  reportPdfUrl: (id: string) => `${BASE}/analysis/${id}/report.pdf`,
  reportJsonUrl: (id: string) => `${BASE}/analysis/${id}/report.json`,
  overlayVideoUrl: (id: string) => `${BASE}/analysis/${id}/overlay-video`,
};
