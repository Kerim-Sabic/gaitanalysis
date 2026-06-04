"""Evaluate every local gait candidate with available real pose backends.

Generated media and reports are ignored by git. The selected canonical clip is
always backed by measured real inference; no synthetic sample is created.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401
from _vision import POSE_BACKENDS, REPO_ROOT
from download_gait_sample_videos import (
    VIDEO_SUFFIXES,
    convert_with_ffmpeg,
    convert_with_opencv,
    probe_video,
)

from app.pipeline.pose.quality_comparator import compare_backend_results
from app.pipeline.quality import QualityAssessmentService
from app.pipeline.video_processor import VideoProcessor

SAMPLE_DIR = REPO_ROOT / "data" / "sample_videos"
CANONICAL = SAMPLE_DIR / "walk_test.mp4"
PROCESSED = SAMPLE_DIR / "processed"
REPORTS = SAMPLE_DIR / "reports"
JSON_REPORT = REPORTS / "best_sample_selection.json"
MD_REPORT = REPORTS / "best_sample_selection.md"


def parse_args():
    parser = argparse.ArgumentParser(description="Select the best measured local gait sample.")
    parser.add_argument("--limit", type=int, default=0, help="Candidate cap; 0 evaluates all.")
    parser.add_argument("--max-eval-frames", type=int, default=36)
    parser.add_argument("--final-eval-frames", type=int, default=180)
    parser.add_argument("--no-copy", action="store_true")
    return parser.parse_args()


def relative(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")


def candidates() -> list[Path]:
    roots = [SAMPLE_DIR / "raw", SAMPLE_DIR / "processed", SAMPLE_DIR / "manual_input"]
    found = []
    for root in roots:
        if root.exists():
            found.extend(
                path for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES
            )
    return sorted(set(found))


def source(path: Path) -> str:
    lowered = str(path).lower()
    if "gahu" in lowered or "_t1_" in lowered:
        return "gahu"
    if "healthgait" in lowered:
        return "healthgait"
    if "manual_input" in lowered:
        return "manual"
    return "processed"


def build_estimators():
    ready, failures = {}, {}
    for label, adapter in POSE_BACKENDS.items():
        if label == "MMPose RTMW3D":
            continue
        error = getattr(adapter, "availability_error", lambda: None)()
        if error or not adapter.is_available():
            failures[label] = error or "unavailable"
            continue
        try:
            ready[label] = adapter()
        except Exception as exc:
            failures[label] = f"{type(exc).__name__}: {exc}"
    return ready, failures


def evaluate(path: Path, estimators: dict, max_frames: int) -> dict:
    item = asdict(probe_video(path, source(path)))
    item["path"] = relative(path)
    item["backend_failures"] = {}
    item["backend_scores"] = {}
    item["status"] = "failed"
    try:
        decoded = VideoProcessor(max_frames=max_frames).load(path, min_seconds=0.1)
        results = {}
        for label, estimator in estimators.items():
            backend = getattr(estimator, "backend_id", label)
            try:
                started = time.perf_counter()
                seq = estimator.estimate_2d_pose(decoded.frames, decoded.fps)
                results[backend] = (seq, time.perf_counter() - started)
            except Exception as exc:
                item["backend_failures"][backend] = f"{type(exc).__name__}: {exc}"
        comparison = compare_backend_results(results, item["backend_failures"])
        selected = comparison["selected_backend"]
        seq = results[selected][0]
        quality = QualityAssessmentService().assess(decoded, seq)
        best = comparison["backend_scores"][selected]
        duration_bonus = 4.0 if 5 <= item["duration_sec"] <= 15 else 0.0
        side_hint = 2.0 if any(word in item["path"].lower() for word in ("right", "left", "side", "track")) else 0.0
        item.update({
            "status": "evaluated",
            "selected_backend": selected,
            "selection_reason": comparison["selection_reason"],
            "backend_scores": comparison["backend_scores"],
            "quality": quality.model_dump(mode="json"),
            "valid_pose_frames": int(round(best["valid_pose_percentage"] / 100 * seq.num_frames)),
            "valid_pose_percentage": best["valid_pose_percentage"],
            "average_keypoint_confidence": best["average_confidence"],
            "hip_confidence": best["hip_confidence"],
            "knee_confidence": best["knee_confidence"],
            "ankle_confidence": best["ankle_confidence"],
            "heel_confidence": best["heel_confidence"],
            "foot_index_confidence": best["foot_index_confidence"],
            "left_leg_confidence": _leg_conf(seq, "left"),
            "right_leg_confidence": _leg_conf(seq, "right"),
            "foot_visibility_score": quality.feet_visibility,
            "person_size_estimate": quality.person_size_percent,
            "number_of_people": 1 if best["valid_pose_percentage"] > 0 else 0,
            "occlusion_missing_percentage": best["missing_frame_percentage"],
            "full_body_visible": quality.full_body_visibility >= 60,
            "feet_visible": quality.feet_visibility >= 55,
            "estimated_camera_view": quality.detected_view.value,
            "final_score": round(
                0.78 * best["final_score"] + 0.18 * quality.overall_score
                + duration_bonus + side_hint,
                3,
            ),
        })
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
    return item


def _leg_conf(seq, side: str) -> float:
    names = seq.all_names()
    points = seq.all_keypoints()
    wanted = [f"{side}_hip", f"{side}_knee", f"{side}_ankle", f"{side}_heel", f"{side}_foot_index"]
    idx = [names.index(name) for name in wanted if name in names]
    return round(float(np.nanmean(points[:, idx, 2])), 4) if idx else 0.0


def normalize(selected: Path) -> tuple[Path, str]:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    output = PROCESSED / "best_sample_selected.mp4"
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        ok, _command, error = convert_with_ffmpeg(ffmpeg, selected, output, keep_long=False)
        if ok:
            return output, "ffmpeg_h264"
        print(f"ffmpeg conversion failed; using OpenCV fallback: {error}")
    convert_with_opencv(selected, output, keep_long=False)
    return output, "opencv_mp4v"


def write_reports(report: dict) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    best = report.get("selected") or {}
    final = report.get("final_verification") or {}
    lines = [
        "# Best Gait Sample Selection",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Candidates evaluated: **{report['candidates_evaluated']}**",
        f"Available backends: `{', '.join(report['available_backends'])}`",
        "",
        "## Selected Candidate",
        "",
        f"- Source: `{best.get('source', '-')}`",
        f"- Path: `{best.get('path', '-')}`",
        f"- Score: `{best.get('final_score', 0):.3f}`",
        f"- Valid pose: `{best.get('valid_pose_percentage', 0):.1f}%`",
        f"- Mean confidence: `{best.get('average_keypoint_confidence', 0):.3f}`",
        f"- Ankle / heel / foot-index: `{best.get('ankle_confidence', 0):.3f}` / "
        f"`{best.get('heel_confidence', 0):.3f}` / `{best.get('foot_index_confidence', 0):.3f}`",
        f"- Selected backend: `{best.get('selected_backend', '-')}`",
        "",
        "## Canonical Verification",
        "",
    ]
    for name, score in final.get("backend_scores", {}).items():
        lines.append(
            f"- `{name}`: score {score.get('final_score', 0):.1f}, "
            f"valid {score.get('valid_pose_percentage', 0):.1f}%, "
            f"confidence {score.get('average_confidence', 0):.3f}"
        )
    if best.get("average_keypoint_confidence", 0) < 0.35:
        lines += [
            "",
            "**Weak sample warning:** the best available candidate remains below 0.35 "
            "mean confidence. It is retained only because no better local candidate exists.",
        ]
    MD_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    paths = candidates()
    if args.limit > 0:
        paths = paths[:args.limit]
    estimators, backend_failures = build_estimators()
    print(f"Evaluating {len(paths)} candidates with: {', '.join(estimators) or 'none'}")
    if not paths or not estimators:
        print("BLOCKED: no candidates or real pose backends available.")
        return 1
    evaluated = []
    for index, path in enumerate(paths, 1):
        item = evaluate(path, estimators, args.max_eval_frames)
        evaluated.append(item)
        print(
            f"[{index}/{len(paths)}] {relative(path)}: "
            f"{item.get('final_score', 0):.1f} "
            f"({item.get('valid_pose_percentage', 0):.1f}% valid, "
            f"{item.get('average_keypoint_confidence', 0):.3f} conf)"
        )
    viable = [item for item in evaluated if item.get("status") == "evaluated"]
    if not viable:
        print("BLOCKED: all candidate videos failed real pose inference.")
        return 1
    best = max(viable, key=lambda item: item["final_score"])
    final_verification = {}
    method = "not_copied"
    if not args.no_copy:
        normalized, method = normalize(REPO_ROOT / best["path"])
        shutil.copy2(normalized, CANONICAL)
        final_item = evaluate(CANONICAL, estimators, args.final_eval_frames)
        final_verification = {
            "selected_backend": final_item.get("selected_backend"),
            "selection_reason": final_item.get("selection_reason"),
            "backend_scores": final_item.get("backend_scores", {}),
            "quality": final_item.get("quality", {}),
        }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidates_evaluated": len(evaluated),
        "available_backends": list(estimators),
        "backend_setup_failures": backend_failures,
        "selected": best,
        "canonical_path": relative(CANONICAL),
        "conversion_method": method,
        "final_verification": final_verification,
        "candidates": evaluated,
    }
    write_reports(report)
    print(f"Selected: {best['path']}")
    print(f"Canonical: {relative(CANONICAL)}")
    print(f"Report: {relative(JSON_REPORT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
