import type { ModelInfo, QualityResult } from "@horalix/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

function Row({ label, value, tone }: { label: string; value: string; tone?: "good" | "danger" | "muted" }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
      <span className="text-xs text-fg-subtle">{label}</span>
      <span
        className={
          "tabular text-xs font-medium " +
          (tone === "good" ? "text-good" : tone === "danger" ? "text-danger" : "text-fg")
        }
      >
        {value}
      </span>
    </div>
  );
}

const helperPurpose: Record<string, string> = {
  mmpose: "Whole-body pose/keypoints",
  sam2: "Segmentation-assisted capture quality",
  depth: "Relative-depth scene metadata",
  wham: "Optional 3D reconstruction",
};

function HelperStatus({ name, details }: { name: string; details: Record<string, unknown> }) {
  const status = String(details.status ?? "NOT_RUN");
  const active = details.used_in_analysis === true || status === "WORKING";
  const error = String(details.error ?? "");
  return (
    <div className="border-b border-border/60 py-2 last:border-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-fg">{name.toUpperCase()}</span>
        <span className={active ? "text-xs font-medium text-good" : "text-xs font-medium text-fg-subtle"}>
          {active ? "Active" : status}
        </span>
      </div>
      <p className="mt-0.5 text-[11px] leading-snug text-fg-subtle">
        {helperPurpose[name] ?? "Optional helper"}
        {active ? " - used in this analysis." : ` - not used in this analysis${error ? `: ${error}` : "."}`}
      </p>
    </div>
  );
}

export function ModelTransparency({
  model,
  quality,
}: {
  model: ModelInfo;
  quality: QualityResult;
}) {
  const real = !model.simulated_data_used;
  const req = (model.analysis_request ?? {}) as Record<string, unknown>;
  const exec = (model.model_execution ?? {}) as Record<string, unknown>;
  const hasProvenance = Object.keys(req).length > 0 || Object.keys(exec).length > 0;
  const boolLabel = (v: unknown) => (v === true ? "Yes" : v === false ? "No" : "—");
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Model transparency</CardTitle>
        <Badge tone={real ? "good" : "warn"}>
          {real ? "Real AI keypoint analysis" : "Demo · simulated"}
        </Badge>
      </CardHeader>
      <CardContent className="pt-0">
        {hasProvenance ? (
          <div className="mb-3 rounded-lg border border-border/60 bg-surface-2/40 p-2">
            <p className="mb-1 text-[11px] font-medium text-fg-subtle">Requested vs actual</p>
            <Row label="Quality mode" value={String(req.analysis_quality_mode ?? "—")} />
            <Row
              label="Pose backend (requested → actual)"
              value={`${String(req.pose_backend_requested ?? "—")} → ${String(exec.pose_backend_actual ?? "—")}`}
              tone={exec.pose_backend_honored === false ? "danger" : "good"}
            />
            <Row
              label="SAM2 (requested → active)"
              value={`${boolLabel(req.sam2_requested)} → ${boolLabel(exec.sam2_active)}`}
              tone={req.sam2_requested && !exec.sam2_active ? "danger" : undefined}
            />
            <Row
              label="Depth (requested → active)"
              value={`${boolLabel(req.depth_requested)} → ${boolLabel(exec.depth_active)}`}
              tone={req.depth_requested && !exec.depth_active ? "danger" : undefined}
            />
            <Row label="Capture source" value={String(req.capture_source ?? "—")} />
          </div>
        ) : null}
        <Row label="Active model" value={`${model.pose_model} ${model.pose_model_version}`} />
        <Row label="Backend" value={model.pose_backend} />
        <Row label="Selected backend" value={model.selected_backend || model.pose_backend} />
        <Row
          label="Foot landmarks"
          value={model.foot_landmarks_available ? "Available" : "Unavailable"}
          tone={model.foot_landmarks_available ? "good" : "muted"}
        />
        <Row label="MMPose" value={model.mmpose_status ?? "not_run"} />
        <Row label="SAM2 segmentation" value={model.sam2_status ?? "not_run"} />
        <Row label="Depth helper" value={model.depth_status ?? "not_run"} />
        <Row label="WHAM 3D" value={model.wham_status ?? "not_run"} />
        <Row label="Analysis mode" value={model.analysis_mode} />
        <Row
          label="Real model loaded"
          value={model.model_loaded ? "Yes" : "No"}
          tone={model.model_loaded ? "good" : "muted"}
        />
        <Row
          label="Model verified"
          value={model.model_verified ? "Yes" : "No"}
          tone={model.model_verified ? "good" : "muted"}
        />
        <Row label="Device" value={model.device} />
        <Row label="Keypoint format" value={model.keypoint_format} />
        <Row label="Frames processed" value={String(model.frame_count)} />
        <Row label="Valid pose frames" value={String(model.valid_pose_frames)} />
        <Row label="Failed frames" value={String(model.failed_frames)} />
        <Row
          label="Mean keypoint confidence"
          value={`${Math.round(model.mean_keypoint_confidence * 100)}%`}
        />
        <Row
          label="Lowest-confidence keypoints"
          value={model.lowest_confidence_keypoints.join(", ") || "—"}
        />
        <Row label="Interpolation used" value={model.interpolation_used ? "Yes" : "No"} />
        <Row label="Calibration" value={model.calibration_status} />
        <Row label="Detected view" value={quality.detected_view} />
        <Row label="Processing time" value={`${model.processing_time_sec.toFixed(2)}s`} />
        {model.timings_ms && Object.keys(model.timings_ms).length ? (
          <Row
            label="Pipeline timing"
            value={`decode ${Math.round(model.timings_ms.decode_ms ?? 0)}ms · inference ${Math.round(
              model.timings_ms.inference_ms ?? 0,
            )}ms · post ${Math.round(model.timings_ms.postprocess_ms ?? 0)}ms`}
          />
        ) : null}
        <Row
          label="Simulated data used"
          value={model.simulated_data_used ? "Yes" : "No"}
          tone={model.simulated_data_used ? "danger" : "good"}
        />
        <Row label="Clinical validation" value={model.clinical_validation_status} />
        {model.helper_models && Object.keys(model.helper_models).length ? (
          <div className="mt-3 border-t border-border/60 pt-1">
            {Object.entries(model.helper_models).map(([name, details]) => (
              <HelperStatus key={name} name={name} details={details} />
            ))}
          </div>
        ) : null}
        {model.notes.length ? (
          <p className="mt-3 text-[11px] leading-snug text-fg-subtle">{model.notes.join(" ")}</p>
        ) : null}
        {model.selection_reason ? (
          <p className="mt-3 text-[11px] leading-snug text-fg-subtle">
            {model.selection_reason}
          </p>
        ) : null}
        {Object.keys(model.backend_scores).length ? (
          <p className="mt-2 text-[11px] leading-snug text-fg-subtle">
            Compared:{" "}
            {Object.entries(model.backend_scores)
              .map(([name, score]) => `${name} ${Number(score.final_score ?? 0).toFixed(1)}/100`)
              .join(" · ")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
