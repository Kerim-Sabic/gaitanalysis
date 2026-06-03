import type { ModelInfo, QualityResult } from "@horalix/shared";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-border/60 py-1.5 last:border-0">
      <span className="text-xs text-fg-subtle">{label}</span>
      <span className="tabular text-xs font-medium text-fg">{value}</span>
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
  return (
    <Card>
      <CardHeader>
        <CardTitle>Model transparency</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <Row label="Pose model" value={`${model.pose_model} ${model.pose_model_version}`} />
        <Row label="Analysis mode" value={model.analysis_mode} />
        <Row label="Keypoint format" value={model.keypoint_format} />
        <Row label="Frames analysed" value={String(model.frame_count)} />
        <Row label="Effective FPS" value={model.fps.toFixed(1)} />
        <Row
          label="Mean keypoint confidence"
          value={`${Math.round(model.mean_keypoint_confidence * 100)}%`}
        />
        <Row label="Calibration" value={model.calibration_status} />
        <Row label="Detected view" value={quality.detected_view} />
        <Row label="Pipeline" value={`v${model.pipeline_version}`} />
        {model.notes.length ? (
          <p className="mt-3 text-[11px] leading-snug text-fg-subtle">
            {model.notes.join(" ")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
