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

export function ModelTransparency({
  model,
  quality,
}: {
  model: ModelInfo;
  quality: QualityResult;
}) {
  const real = !model.simulated_data_used;
  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Model transparency</CardTitle>
        <Badge tone={real ? "good" : "warn"}>
          {real ? "Real AI keypoint analysis" : "Demo · simulated"}
        </Badge>
      </CardHeader>
      <CardContent className="pt-0">
        <Row label="Active model" value={`${model.pose_model} ${model.pose_model_version}`} />
        <Row label="Backend" value={model.pose_backend} />
        <Row label="Selected backend" value={model.selected_backend || model.pose_backend} />
        <Row
          label="Foot landmarks"
          value={model.foot_landmarks_available ? "Available" : "Unavailable"}
          tone={model.foot_landmarks_available ? "good" : "muted"}
        />
        <Row label="MMPose" value={model.mmpose_status} />
        <Row label="SAM2" value={model.sam2_status} />
        <Row label="Segmentation" value={model.segmentation_status} />
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
        <Row
          label="Simulated data used"
          value={model.simulated_data_used ? "Yes" : "No"}
          tone={model.simulated_data_used ? "danger" : "good"}
        />
        <Row label="Clinical validation" value={model.clinical_validation_status} />
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
