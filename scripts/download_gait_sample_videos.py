"""Download, rank, normalize, and verify small public gait sample videos.

Default behavior tries the Health&Gait Zenodo sample archive and any files in
``data/sample_videos/manual_input``. It never downloads the full Health&Gait
dataset and never creates a fake ``walk_test.mp4``.

Examples:

    python scripts/download_gait_sample_videos.py
    python scripts/download_gait_sample_videos.py --source healthgait --limit 3
    python scripts/download_gait_sample_videos.py --process-manual
    python scripts/download_gait_sample_videos.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import _bootstrap  # noqa: F401

REPO_ROOT = _bootstrap.REPO_ROOT
SAMPLE_DIR = REPO_ROOT / "data" / "sample_videos"
RAW_DIR = SAMPLE_DIR / "raw"
PROCESSED_DIR = SAMPLE_DIR / "processed"
REPORTS_DIR = SAMPLE_DIR / "reports"
MANUAL_DIR = SAMPLE_DIR / "manual_input"
CANONICAL = SAMPLE_DIR / "walk_test.mp4"
JSON_REPORT = REPORTS_DIR / "download_report.json"
MD_REPORT = REPORTS_DIR / "download_report.md"

HEALTHGAIT_RECORD_API = "https://zenodo.org/api/records/14039922"
HEALTHGAIT_PAGE = "https://zenodo.org/records/14039922"
GAHU_PAGE = "https://data.mendeley.com/datasets/gprg4s73v4/1"
GAHU_API = "https://api.mendeley.com/datasets/gprg4s73v4?fields=id,name,version,files"
GAHU_PUBLIC_ARCHIVE = "https://data.mendeley.com/public-api/zip/gprg4s73v4/download/1"
VIDEO_SUFFIXES = {".mp4", ".avi", ".mov", ".mkv"}
PREFERRED_WORDS = (
    "side", "sagittal", "normal", "walk", "walking", "gait", "track",
    "left", "right",
)
USER_AGENT = "Horalix-Gait-AI-sample-downloader/1.0"


@dataclass
class VideoInfo:
    path: str
    source: str
    size_bytes: int
    decode_success: bool = False
    duration_sec: float = 0.0
    fps: float = 0.0
    width: int = 0
    height: int = 0
    frame_count: int = 0
    brightness: float | None = None
    blur_score: float | None = None
    codec: str = ""
    keyword_hits: int = 0
    rank_score: float = -1_000_000.0
    error: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download and prepare a small real walking video for Horalix."
    )
    parser.add_argument("--source", choices=("healthgait", "gahu", "manual"))
    parser.add_argument("--process-manual", action="store_true")
    parser.add_argument("--max-download-mb", type=float, default=1000.0)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-convert", action="store_true")
    parser.add_argument("--keep-long", action="store_true")
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()
    if args.max_download_mb <= 0:
        parser.error("--max-download-mb must be greater than zero")
    if args.limit <= 0:
        parser.error("--limit must be greater than zero")
    return args


def ensure_directories() -> None:
    for path in (SAMPLE_DIR, RAW_DIR, PROCESSED_DIR, REPORTS_DIR, MANUAL_DIR):
        path.mkdir(parents=True, exist_ok=True)


def relative(path: str | Path) -> str:
    p = Path(path)
    try:
        return str(p.resolve().relative_to(REPO_ROOT.resolve())).replace("\\", "/")
    except ValueError:
        return str(p)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def request_json(url: str, timeout: int = 30) -> Any:
    request = urllib.request.Request(
        url, headers={"Accept": "application/json", "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def request_text(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(
        url, headers={"Accept": "text/html", "User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def download_file(
    url: str,
    destination: Path,
    max_bytes: int,
    expected_checksum: str | None,
    force: bool,
) -> dict[str, Any]:
    if destination.exists() and not force:
        return {
            "path": relative(destination),
            "size_bytes": destination.stat().st_size,
            "url": url,
            "reused": True,
            "checksum_verified": verify_checksum(destination, expected_checksum),
        }

    part = destination.with_suffix(destination.suffix + ".part")
    part.unlink(missing_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as out:
            content_length = int(response.headers.get("Content-Length") or 0)
            if content_length and content_length > max_bytes:
                raise RuntimeError(
                    f"Remote file is {content_length / 1_000_000:.1f} MB, above "
                    f"the {max_bytes / 1_000_000:.1f} MB limit."
                )
            downloaded = 0
            last_print = 0.0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > max_bytes:
                    raise RuntimeError(
                        f"Download exceeded the {max_bytes / 1_000_000:.1f} MB limit."
                    )
                out.write(chunk)
                current = time.monotonic()
                if current - last_print >= 2:
                    print(f"  downloaded {downloaded / 1_000_000:.1f} MB")
                    last_print = current
        checksum_result = verify_checksum(part, expected_checksum)
        if checksum_result is False:
            raise RuntimeError("Downloaded file checksum does not match source metadata.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(part, destination)
        return {
            "path": relative(destination),
            "size_bytes": destination.stat().st_size,
            "url": url,
            "reused": False,
            "checksum_verified": checksum_result,
        }
    except Exception:
        part.unlink(missing_ok=True)
        raise


def remote_file_size(url: str, timeout: int = 30) -> int | None:
    """Probe public file size with a one-byte range request."""
    request = urllib.request.Request(
        url,
        headers={"Range": "bytes=0-0", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_range = response.headers.get("Content-Range") or ""
        match = re.search(r"/(\d+)$", content_range)
        if match:
            return int(match.group(1))
        length = int(response.headers.get("Content-Length") or 0)
        return length or None


def verify_checksum(path: Path, expected: str | None) -> bool | None:
    if not expected:
        return None
    algorithm, _, expected_value = expected.partition(":")
    if algorithm.lower() != "md5" or not expected_value:
        return None
    digest = hashlib.md5()  # noqa: S324 - verifies public Zenodo metadata only
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().lower() == expected_value.lower()


def safe_extract_zip(archive: Path, destination: Path, force: bool) -> list[Path]:
    destination.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []
    root = destination.resolve()
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            parts = sanitize_archive_parts(member.filename)
            if not parts:
                continue
            target = destination.joinpath(*parts).resolve()
            if root not in target.parents and target != root:
                raise RuntimeError(f"Unsafe archive path rejected: {member.filename}")
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            if target.exists() and not force:
                extracted.append(target)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(target)
    return extracted


def sanitize_archive_parts(name: str) -> list[str]:
    """Return safe cross-platform path components for an archive member."""
    parts: list[str] = []
    for raw in name.replace("\\", "/").split("/"):
        if not raw or raw in (".", ".."):
            continue
        clean = re.sub(r'[<>:"|?*\x00-\x1f]', "_", raw).rstrip(" .")
        if not clean:
            clean = "_"
        parts.append(clean)
    return parts


def extract_nested_gahu_videos(
    archives: list[Path],
    destination: Path,
    limit: int,
    force: bool,
    report: dict[str, Any],
    attempt: dict[str, Any],
) -> list[Path]:
    extractor = (
        shutil.which("7z")
        or shutil.which("7zz")
        or shutil.which("unrar")
        or shutil.which("tar")
    )
    attempt["nested_archive_extractor"] = extractor
    if not extractor:
        report["warnings"].append(
            "GaHu contains nested RAR files, but no 7z, unrar, or bsdtar executable "
            "is available."
        )
        return []

    def archive_rank(path: Path) -> tuple[int, int, str]:
        name = path.name.lower()
        preferred = (
            0 if "track 1_right" in name else
            1 if "track 1_left" in name else
            2 if "right" in name else
            3 if "left" in name else
            4 if "track" in name else
            5
        )
        return preferred, path.stat().st_size, name

    videos: list[Path] = []
    used: list[dict[str, Any]] = []
    for archive in sorted(archives, key=archive_rank):
        if len(videos) >= limit:
            break
        output = destination / f"extracted_{safe_stem(archive.stem)}"
        output_resolved = output.resolve()
        destination_resolved = destination.resolve()
        if destination_resolved not in output_resolved.parents:
            raise RuntimeError(f"Unsafe nested archive output rejected: {output}")
        if output.exists() and force:
            shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)
        if not force:
            existing = find_videos(output)
            if existing:
                used.append({
                    "archive": relative(archive),
                    "output": relative(output),
                    "status": "reused_existing_extraction",
                    "video_count": len(existing),
                })
                videos.extend(existing)
                continue
        name = Path(extractor).name.lower()
        if name in ("7z", "7z.exe", "7zz", "7zz.exe"):
            command = [extractor, "x", "-y", f"-o{output}", str(archive)]
        elif name in ("unrar", "unrar.exe"):
            command = [extractor, "x", "-o+", str(archive), str(output) + os.sep]
        else:
            command = [extractor, "-xf", str(archive), "-C", str(output)]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        item = {
            "archive": relative(archive),
            "output": relative(output),
            "command": command,
            "return_code": result.returncode,
        }
        used.append(item)
        if result.returncode != 0:
            item["error"] = (result.stderr or result.stdout or "archive extraction failed")[-2000:]
            continue
        found = find_videos(output)
        item["video_count"] = len(found)
        videos.extend(found)
    attempt["nested_archives_used"] = used
    return videos


def safe_stem(value: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return clean or "archive"


def discover_healthgait(args: argparse.Namespace, report: dict[str, Any]) -> list[Path]:
    attempt = source_attempt(report, "healthgait", HEALTHGAIT_PAGE)
    try:
        record = request_json(HEALTHGAIT_RECORD_API)
        files = record.get("files") or []
        attempt["dataset_samples_found"] = any(
            item.get("key") == "dataset_samples.zip" for item in files
        )
        eligible = [
            item for item in files
            if str(item.get("key", "")).lower().endswith(
                (".zip", ".mp4", ".avi", ".mov", ".mkv")
            )
            and int(item.get("size") or 0) <= int(args.max_download_mb * 1_000_000)
        ]
        eligible.sort(key=lambda item: (
            0 if item.get("key") == "dataset_samples.zip" else 1,
            int(item.get("size") or 0),
        ))
        if not eligible:
            raise RuntimeError(
                f"No sample archive/video is below --max-download-mb={args.max_download_mb:g}."
            )
        chosen = eligible[0]
        key = str(chosen["key"])
        url = ((chosen.get("links") or {}).get("self")
               or (chosen.get("links") or {}).get("content"))
        if not url:
            raise RuntimeError(f"Zenodo metadata for {key} has no public download URL.")
        destination = (
            RAW_DIR / "healthgait_dataset_samples.zip"
            if key == "dataset_samples.zip"
            else RAW_DIR / f"healthgait_{Path(key).name}"
        )
        attempt["selected_remote_file"] = {
            "name": key,
            "size_bytes": int(chosen.get("size") or 0),
            "url": url,
        }
        if args.dry_run:
            print(
                f"DRY RUN: would download {key} "
                f"({int(chosen.get('size') or 0) / 1_000_000:.1f} MB) to {relative(destination)}"
            )
            attempt["status"] = "dry_run"
            return []

        print(f"Preparing Health&Gait sample: {key}")
        downloaded = download_file(
            url=url,
            destination=destination,
            max_bytes=int(args.max_download_mb * 1_000_000),
            expected_checksum=chosen.get("checksum"),
            force=args.force,
        )
        report["downloads"].append(downloaded)
        attempt["status"] = "downloaded"

        if destination.suffix.lower() == ".zip":
            extract_dir = RAW_DIR / "healthgait_samples"
            files_out = safe_extract_zip(destination, extract_dir, args.force)
            videos = [p for p in files_out if p.suffix.lower() in VIDEO_SUFFIXES]
        else:
            videos = [destination]
        attempt["candidate_video_count"] = len(videos)
        if not videos:
            attempt["status"] = "downloaded_no_videos"
            attempt["note"] = (
                "dataset_samples.zip contains derived pose, optical-flow, semantic "
                "segmentation, and silhouette files, but no original RGB video."
            )
            report["warnings"].append(f"Health&Gait: {attempt['note']}")
            report["manual_instructions"].append(gahu_manual_instructions())
        return videos
    except Exception as exc:
        attempt["status"] = "failed"
        attempt["error"] = f"{type(exc).__name__}: {exc}"
        report["errors"].append(f"Health&Gait: {attempt['error']}")
        print(f"Health&Gait failed: {attempt['error']}")
        return []


def discover_gahu(args: argparse.Namespace, report: dict[str, Any]) -> list[Path]:
    attempt = source_attempt(report, "gahu", GAHU_PAGE)
    try:
        direct_urls: list[str] = []
        try:
            metadata = request_json(GAHU_API)
            for item in metadata.get("files") or []:
                url = item.get("download_url") or item.get("url")
                name = str(item.get("filename") or item.get("name") or url or "")
                size = int(item.get("size") or 0)
                if url and Path(name).suffix.lower() in VIDEO_SUFFIXES:
                    if not size or size <= int(args.max_download_mb * 1_000_000):
                        direct_urls.append(str(url))
        except urllib.error.HTTPError as exc:
            attempt["api_status"] = f"HTTP {exc.code}: public API requires authorization"

        if not direct_urls:
            page = request_text(GAHU_PAGE)
            direct_urls = re.findall(
                r'https?://[^"\'\s<>]+\.(?:mp4|avi|mov|mkv)(?:\?[^"\'\s<>]*)?',
                page,
                flags=re.IGNORECASE,
            )
        direct_urls = list(dict.fromkeys(direct_urls))
        attempt["direct_public_video_urls_found"] = len(direct_urls)
        archive_size = remote_file_size(GAHU_PUBLIC_ARCHIVE)
        attempt["public_archive"] = {
            "url": GAHU_PUBLIC_ARCHIVE,
            "size_bytes": archive_size,
        }
        max_bytes = int(args.max_download_mb * 1_000_000)
        if not direct_urls and archive_size and archive_size <= max_bytes:
            archive = RAW_DIR / "gahu_dataset.zip"
            if args.dry_run:
                print(
                    f"DRY RUN: would download GaHu public archive "
                    f"({archive_size / 1_000_000:.1f} MB) to {relative(archive)}"
                )
                attempt["status"] = "dry_run"
                return []
            print(f"Preparing GaHu public archive ({archive_size / 1_000_000:.1f} MB)")
            item = download_file(
                GAHU_PUBLIC_ARCHIVE, archive, max_bytes, None, args.force
            )
            report["downloads"].append(item)
            extracted = safe_extract_zip(archive, RAW_DIR / "gahu_samples", args.force)
            videos = [path for path in extracted if path.suffix.lower() in VIDEO_SUFFIXES]
            nested = [path for path in extracted if path.suffix.lower() == ".rar"]
            attempt["nested_archive_count"] = len(nested)
            if not videos and nested:
                videos = extract_nested_gahu_videos(
                    nested,
                    RAW_DIR / "gahu_samples",
                    args.limit,
                    args.force,
                    report,
                    attempt,
                )
            attempt["candidate_video_count"] = len(videos)
            attempt["status"] = "downloaded" if videos else "downloaded_no_videos"
            if not videos:
                attempt["error"] = "The public GaHu archive contained no supported video files."
                report["manual_instructions"].append(gahu_manual_instructions())
            return videos
        if not direct_urls:
            attempt["status"] = "manual_required"
            if archive_size and archive_size > max_bytes:
                attempt["error"] = (
                    f"Public GaHu archive is {archive_size / 1_000_000:.1f} MB, above "
                    f"the {args.max_download_mb:g} MB limit."
                )
            else:
                attempt["error"] = (
                    "No direct public video URL was discoverable without authentication."
                )
            report["manual_instructions"].append(gahu_manual_instructions())
            print(f"GaHu: {attempt['error']}")
            return []

        videos: list[Path] = []
        for index, url in enumerate(direct_urls[:args.limit], start=1):
            suffix = Path(urllib.parse.urlparse(url).path).suffix.lower() or ".avi"
            destination = RAW_DIR / f"gahu_public_{index:02d}{suffix}"
            if args.dry_run:
                print(f"DRY RUN: would download GaHu direct video {url}")
                continue
            item = download_file(
                url, destination, int(args.max_download_mb * 1_000_000), None, args.force
            )
            report["downloads"].append(item)
            videos.append(destination)
        attempt["status"] = "dry_run" if args.dry_run else "downloaded"
        return videos
    except Exception as exc:
        attempt["status"] = "failed"
        attempt["error"] = f"{type(exc).__name__}: {exc}"
        report["errors"].append(f"GaHu: {attempt['error']}")
        report["manual_instructions"].append(gahu_manual_instructions())
        print(f"GaHu failed: {attempt['error']}")
        return []


def discover_manual(report: dict[str, Any]) -> list[Path]:
    attempt = source_attempt(report, "manual", relative(MANUAL_DIR))
    videos = find_videos(MANUAL_DIR)
    attempt["candidate_video_count"] = len(videos)
    attempt["status"] = "found" if videos else "empty"
    if not videos:
        report["manual_instructions"].append(gahu_manual_instructions())
    return videos


def source_attempt(report: dict[str, Any], name: str, url: str) -> dict[str, Any]:
    attempt = {"source": name, "url": url, "status": "started"}
    report["source_attempts"].append(attempt)
    return attempt


def gahu_manual_instructions() -> str:
    return (
        "1. Open https://data.mendeley.com/datasets/gprg4s73v4/1\n"
        "2. Download the GaHu-Video dataset or a small edited gait video.\n"
        "3. Choose a simple side-view walking clip, preferably right/left track.\n"
        "4. Place it here: data/sample_videos/manual_input/\n"
        "5. Re-run: python scripts/download_gait_sample_videos.py --process-manual"
    )


def find_videos(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in VIDEO_SUFFIXES
    )


def probe_video(path: Path, source: str) -> VideoInfo:
    info = VideoInfo(path=relative(path), source=source, size_bytes=path.stat().st_size)
    path_text = str(path).lower()
    info.keyword_hits = sum(word in path_text for word in PREFERRED_WORDS)
    try:
        import cv2

        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            raise RuntimeError("OpenCV could not open the video.")
        info.fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        info.width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        info.height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        info.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        info.duration_sec = (
            info.frame_count / info.fps if info.fps > 0 and info.frame_count > 0 else 0.0
        )
        codec_int = int(cap.get(cv2.CAP_PROP_FOURCC) or 0)
        info.codec = "".join(chr((codec_int >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00")

        brightness: list[float] = []
        blur: list[float] = []
        positions = sample_positions(info.frame_count, 10)
        decoded = 0
        for frame_index in positions:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            decoded += 1
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness.append(float(gray.mean()))
            blur.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
        cap.release()
        info.decode_success = decoded > 0
        info.brightness = round(statistics.fmean(brightness), 2) if brightness else None
        info.blur_score = round(statistics.fmean(blur), 2) if blur else None
        if not info.decode_success:
            info.error = "OpenCV opened the file but could not decode sampled frames."
    except Exception as exc:
        info.error = f"{type(exc).__name__}: {exc}"
    info.rank_score = rank_video(info)
    return info


def sample_positions(frame_count: int, count: int) -> list[int]:
    if frame_count <= 1:
        return [0]
    return sorted({
        min(frame_count - 1, int(round(i * (frame_count - 1) / max(1, count - 1))))
        for i in range(count)
    })


def rank_video(info: VideoInfo) -> float:
    if not info.decode_success:
        return -1_000_000.0
    score = 1000.0
    if 5.0 <= info.duration_sec <= 15.0:
        score += 400.0
    else:
        score -= min(abs(info.duration_sec - 10.0), 60.0) * 5.0
    if info.height >= 480:
        score += 200.0
    else:
        score += max(0.0, info.height / 480.0) * 100.0
    if info.fps >= 24.0:
        score += 150.0
    else:
        score += max(0.0, info.fps / 24.0) * 75.0
    score += info.keyword_hits * 35.0
    if info.brightness is not None and 45.0 <= info.brightness <= 220.0:
        score += 40.0
    if info.blur_score is not None and info.blur_score >= 80.0:
        score += 40.0
    score -= math.log10(max(info.size_bytes, 1)) * 3.0
    return round(score, 3)


def convert_candidates(
    candidates: list[VideoInfo],
    args: argparse.Namespace,
    report: dict[str, Any],
) -> list[Path]:
    outputs: list[Path] = []
    counts = {"healthgait": 0, "gahu": 0, "manual": 0}
    ffmpeg = shutil.which("ffmpeg")
    report["conversion"]["ffmpeg_path"] = ffmpeg
    report["conversion"]["ffmpeg_used"] = False
    report["conversion"]["opencv_fallback_used"] = False
    if not ffmpeg:
        message = (
            "ffmpeg not found. Used OpenCV fallback. Install ffmpeg for better MP4 "
            "compatibility."
        )
        print(message)
        report["warnings"].append(message)

    for info in candidates[:args.limit]:
        source_path = REPO_ROOT / info.path
        counts[info.source] = counts.get(info.source, 0) + 1
        output = PROCESSED_DIR / f"walk_test_{info.source}_{counts[info.source]:02d}.mp4"
        item = {
            "source": info.source,
            "input": info.path,
            "output": relative(output),
            "status": "started",
        }
        report["processed_files"].append(item)
        if output.exists() and not args.force:
            item["status"] = "reused"
            outputs.append(output)
            continue
        if args.dry_run:
            item["status"] = "dry_run"
            print(f"DRY RUN: would create {relative(output)} from {info.path}")
            continue
        try:
            if args.no_convert:
                if source_path.suffix.lower() != ".mp4":
                    raise RuntimeError("--no-convert only accepts MP4 input candidates.")
                shutil.copy2(source_path, output)
                item["method"] = "copy_no_convert"
            else:
                converted = False
                if ffmpeg:
                    converted, command, error = convert_with_ffmpeg(
                        ffmpeg, source_path, output, keep_long=args.keep_long
                    )
                    item["ffmpeg_command"] = command
                    if converted:
                        item["method"] = "ffmpeg_h264"
                        report["conversion"]["ffmpeg_used"] = True
                    else:
                        item["ffmpeg_error"] = error
                if not converted:
                    if ffmpeg:
                        message = (
                            f"ffmpeg H.264 conversion failed for {info.path}. Used OpenCV "
                            "MP4V fallback; install/repair ffmpeg for better MP4 compatibility."
                        )
                        print(message)
                        report["warnings"].append(message)
                    convert_with_opencv(source_path, output, keep_long=args.keep_long)
                    item["method"] = "opencv_mp4v"
                    report["conversion"]["opencv_fallback_used"] = True
            output_info = probe_video(output, info.source)
            item["metadata"] = asdict(output_info)
            if not output_info.decode_success:
                raise RuntimeError(output_info.error or "Converted output did not decode.")
            item["status"] = "created"
            outputs.append(output)
        except Exception as exc:
            output.unlink(missing_ok=True)
            item["status"] = "failed"
            item["error"] = f"{type(exc).__name__}: {exc}"
            report["errors"].append(f"Conversion {info.path}: {item['error']}")
            print(f"Conversion failed for {info.path}: {item['error']}")
    return outputs


def convert_with_ffmpeg(
    ffmpeg: str, source: Path, output: Path, keep_long: bool
) -> tuple[bool, list[str], str | None]:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg, "-y", "-i", str(source)]
    if not keep_long:
        command += ["-t", "10"]
    command += [
        "-vf", r"fps=30,scale=min(1280\,iw):-2",
        "-an",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(
        command, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    if result.returncode == 0 and output.exists() and output.stat().st_size > 0:
        return True, command, None
    output.unlink(missing_ok=True)
    error = (result.stderr or result.stdout or "ffmpeg failed")[-2000:]
    return False, command, error


def convert_with_opencv(source: Path, output: Path, keep_long: bool) -> None:
    import cv2

    cap = cv2.VideoCapture(str(source))
    if not cap.isOpened():
        raise RuntimeError("OpenCV could not open input for conversion.")
    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 30.0
    source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    source_duration = source_frames / source_fps if source_frames > 0 else 10.0
    target_duration = source_duration if keep_long else min(source_duration, 10.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError("Input resolution is invalid.")
    scale = min(1.0, 1280.0 / width)
    out_width = max(2, int(round(width * scale)) // 2 * 2)
    out_height = max(2, int(round(height * scale)) // 2 * 2)
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), 30.0, (out_width, out_height)
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError("OpenCV could not open MP4V output writer.")
    target_frames = max(1, int(round(target_duration * 30.0)))
    written = 0
    try:
        for i in range(target_frames):
            cap.set(cv2.CAP_PROP_POS_MSEC, i * 1000.0 / 30.0)
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if frame.shape[1] != out_width or frame.shape[0] != out_height:
                frame = cv2.resize(frame, (out_width, out_height), interpolation=cv2.INTER_AREA)
            writer.write(frame)
            written += 1
    finally:
        cap.release()
        writer.release()
    if written == 0:
        raise RuntimeError("OpenCV decoded zero frames during conversion.")


def select_canonical(
    processed: list[Path], args: argparse.Namespace, report: dict[str, Any]
) -> Path | None:
    if args.dry_run:
        return None
    if CANONICAL.exists() and not args.force:
        report["selected_final_video"] = {
            "path": relative(CANONICAL),
            "status": "reused_existing",
            "metadata": asdict(probe_video(CANONICAL, "existing")),
        }
        return CANONICAL
    available = [path for path in processed if path.exists()]
    if not available:
        return None
    # ``processed`` preserves the original candidate ranking. Keep that order so
    # normalized 30 FPS outputs do not hide that one source was truly 30 FPS
    # while another was upsampled from 15 FPS.
    best = available[0]
    shutil.copy2(best, CANONICAL)
    canonical_info = probe_video(CANONICAL, infer_source(best))
    report["selected_final_video"] = {
        "path": relative(CANONICAL),
        "selected_from": relative(best),
        "status": "created",
        "metadata": asdict(canonical_info),
    }
    return CANONICAL


def infer_source(path: Path) -> str:
    for source in ("healthgait", "gahu", "manual"):
        if source in path.name.lower():
            return source
    return "unknown"


def run_verification(args: argparse.Namespace, report: dict[str, Any]) -> None:
    verification = report["verification"]
    verification["requested"] = not args.no_verify
    if args.dry_run:
        verification["status"] = "skipped_dry_run"
        return
    if args.no_verify:
        verification["status"] = "skipped_by_option"
        return
    if not CANONICAL.exists():
        verification["status"] = "skipped_no_sample"
        return
    script = REPO_ROOT / "scripts" / "test_pose_on_sample_video.py"
    if not script.exists():
        verification["status"] = "skipped_script_missing"
        return
    python = verification_python()
    command = [str(python), str(script)]
    print(f"Running pose verification: {' '.join(command)}")
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    verification.update({
        "command": command,
        "return_code": result.returncode,
        "stdout": result.stdout[-8000:],
        "stderr": result.stderr[-4000:],
    })
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    model_report = REPO_ROOT / "data" / "processed" / "model_tests" / "model_test_report.json"
    if model_report.exists():
        try:
            details = json.loads(model_report.read_text(encoding="utf-8"))
            verification["valid_pose_frames"] = int(details.get("valid_pose_frames") or 0)
            verification["average_confidence"] = float(details.get("average_confidence") or 0.0)
            verification["frames_processed"] = int(details.get("frames_processed") or 0)
        except Exception as exc:
            verification["report_read_error"] = f"{type(exc).__name__}: {exc}"
    valid = int(verification.get("valid_pose_frames") or 0)
    verification["status"] = "passed" if result.returncode == 0 and valid > 0 else "failed"


def verification_python() -> Path:
    candidates = [
        REPO_ROOT / "apps" / "api" / ".venv" / "Scripts" / "python.exe",
        REPO_ROOT / "apps" / "api" / ".venv" / "bin" / "python",
        Path(sys.executable),
    ]
    return next((path for path in candidates if path.exists()), Path(sys.executable))


def determine_final_status(report: dict[str, Any], dry_run: bool) -> str:
    if dry_run:
        return "DRY RUN COMPLETE"
    if not CANONICAL.exists():
        return "BLOCKED: MANUAL DOWNLOAD REQUIRED"
    verification = report.get("verification") or {}
    if verification.get("status") == "passed" and int(verification.get("valid_pose_frames") or 0) > 0:
        return "SAMPLE VIDEO READY"
    return "VIDEO DOWNLOADED BUT NOT GOOD FOR POSE DETECTION"


def write_reports(report: dict[str, Any]) -> None:
    report["finished_at"] = now_iso()
    JSON_REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    MD_REPORT.write_text(markdown_report(report), encoding="utf-8")


def markdown_report(report: dict[str, Any]) -> str:
    selected = report.get("selected_final_video") or {}
    metadata = selected.get("metadata") or {}
    verification = report.get("verification") or {}
    lines = [
        "# Gait Sample Video Download Report",
        "",
        f"Generated: `{report.get('finished_at', now_iso())}`",
        "",
        f"Final status: **{report.get('final_status', 'UNKNOWN')}**",
        "",
        "## Sources Attempted",
        "",
    ]
    for attempt in report.get("source_attempts") or []:
        lines.append(
            f"- **{attempt.get('source')}**: {attempt.get('status')} "
            f"({attempt.get('url')})"
        )
        if attempt.get("error"):
            lines.append(f"  - Error: {attempt['error']}")
    lines += ["", "## Downloads", ""]
    if report.get("downloads"):
        for item in report["downloads"]:
            lines.append(
                f"- `{item.get('path')}`: {int(item.get('size_bytes') or 0) / 1_000_000:.2f} MB"
            )
    else:
        lines.append("- None.")
    lines += ["", "## Candidate Videos", ""]
    if report.get("candidates"):
        for item in report["candidates"]:
            lines.append(
                f"- `{item.get('path')}`: duration {item.get('duration_sec', 0):.2f}s, "
                f"{item.get('fps', 0):.2f} FPS, {item.get('width', 0)}x{item.get('height', 0)}, "
                f"decode={item.get('decode_success')}, rank={item.get('rank_score')}"
            )
    else:
        lines.append("- None.")
    lines += ["", "## Selected Final Video", ""]
    if selected:
        lines += [
            f"- Path: `{selected.get('path')}`",
            f"- Selected from: `{selected.get('selected_from', 'existing file')}`",
            f"- Duration: {metadata.get('duration_sec', 0):.2f} seconds",
            f"- FPS: {metadata.get('fps', 0):.2f}",
            f"- Resolution: {metadata.get('width', 0)}x{metadata.get('height', 0)}",
            f"- Frame count: {metadata.get('frame_count', 0)}",
            f"- Codec: `{metadata.get('codec', '')}`",
        ]
    else:
        lines.append("- No `walk_test.mp4` was created.")
    lines += [
        "",
        "## Conversion",
        "",
        f"- ffmpeg used: {report.get('conversion', {}).get('ffmpeg_used', False)}",
        f"- OpenCV fallback used: {report.get('conversion', {}).get('opencv_fallback_used', False)}",
        "",
        "## Pose Verification",
        "",
        f"- Status: {verification.get('status', 'not run')}",
        f"- Valid pose frames: {verification.get('valid_pose_frames', 0)}",
        f"- Average keypoint confidence: {verification.get('average_confidence', 0.0)}",
        "",
        "## Manual Download Instructions",
        "",
    ]
    instructions = report.get("manual_instructions") or [gahu_manual_instructions()]
    lines.extend(instructions)
    lines += [
        "",
        "Health&Gait source: https://zenodo.org/records/14039922 (CC BY 4.0).",
        "",
    ]
    return "\n".join(lines)


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "started_at": now_iso(),
        "arguments": vars(args),
        "source_attempts": [],
        "downloads": [],
        "candidates": [],
        "processed_files": [],
        "selected_final_video": None,
        "conversion": {},
        "verification": {},
        "warnings": [],
        "errors": [],
        "manual_instructions": [],
        "final_status": "UNKNOWN",
    }


def source_plan(args: argparse.Namespace) -> list[str]:
    if args.source:
        sources = [args.source]
    else:
        sources = ["healthgait", "manual"]
    if args.process_manual and "manual" not in sources:
        sources.append("manual")
    return sources


def main() -> int:
    args = parse_args()
    ensure_directories()
    report = build_report(args)
    print("=== Horalix gait sample video downloader ===")
    print(f"Sources: {', '.join(source_plan(args))}")
    print(f"Download limit: {args.max_download_mb:g} MB")
    print(f"Dry run: {'yes' if args.dry_run else 'no'}")

    discovered: list[tuple[Path, str]] = []
    for source in source_plan(args):
        if source == "healthgait":
            paths = discover_healthgait(args, report)
        elif source == "gahu":
            paths = discover_gahu(args, report)
        else:
            paths = discover_manual(report)
        discovered.extend((path, source) for path in paths)

    infos = [probe_video(path, source) for path, source in discovered if path.exists()]
    infos.sort(key=lambda item: item.rank_score, reverse=True)
    report["candidates"] = [asdict(item) for item in infos]
    if infos:
        print("Ranked candidates:")
        for item in infos[:args.limit]:
            print(
                f"  {item.path}: score={item.rank_score:.1f}, "
                f"{item.duration_sec:.2f}s, {item.fps:.2f}fps, "
                f"{item.width}x{item.height}, decode={item.decode_success}"
            )
    elif not args.dry_run:
        print("No decodable gait video candidates were found.")

    decodable = [item for item in infos if item.decode_success]
    processed = convert_candidates(decodable, args, report)
    select_canonical(processed, args, report)
    run_verification(args, report)
    report["final_status"] = determine_final_status(report, args.dry_run)
    write_reports(report)

    print(f"JSON report: {relative(JSON_REPORT)}")
    print(f"Markdown report: {relative(MD_REPORT)}")
    print(f"STATUS: {report['final_status']}")
    if report["final_status"] == "BLOCKED: MANUAL DOWNLOAD REQUIRED":
        print(gahu_manual_instructions())
        return 1
    if report["final_status"] == "VIDEO DOWNLOADED BUT NOT GOOD FOR POSE DETECTION":
        print("Choose another candidate, use a clearer side-view video, or record your own clip.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
