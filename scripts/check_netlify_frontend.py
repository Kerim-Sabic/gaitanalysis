"""Verify that the frontend is ready for Netlify + an external FastAPI API."""
from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import _bootstrap

ROOT = _bootstrap.REPO_ROOT
WEB = ROOT / "apps" / "web"
WEIGHT_EXTS = (
    ".task", ".pt", ".pth", ".pth.tar", ".ckpt", ".safetensors", ".onnx",
    ".bin", ".pkl", ".npy", ".npz", ".zip", ".tar.gz", ".rar",
)
VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".webm")
REPORT_DIRS = ("data/reports/", "data/processed/model_tests/", "data/sample_videos/reports/")


class Checks:
    def __init__(self) -> None:
        self.rows: list[tuple[str, bool, str]] = []
        self.blockers: list[str] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.rows.append((name, ok, detail))
        if not ok:
            self.blockers.append(f"{name}: {detail}")


def git_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines()]


def frontend_source_files() -> list[Path]:
    files: list[Path] = [WEB / "next.config.mjs"]
    for folder in ("app", "components", "lib"):
        for pattern in ("*.ts", "*.tsx", "*.js", "*.mjs"):
            files.extend((WEB / folder).rglob(pattern))
    return [path for path in files if path.exists()]


def run_build() -> tuple[bool, str]:
    env = os.environ.copy()
    env["NEXT_PUBLIC_API_URL"] = ""
    env.pop("API_URL", None)
    npm = "npm.cmd" if os.name == "nt" else "npm"
    result = subprocess.run(
        [npm, "run", "build"],
        cwd=WEB,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True, "build passes with NEXT_PUBLIC_API_URL unset"
    output = (result.stderr or result.stdout).strip().splitlines()
    return False, output[-1] if output else f"exit {result.returncode}"


def main() -> int:
    checks = Checks()
    netlify_path = ROOT / "netlify.toml"
    package_path = WEB / "package.json"
    env_example = WEB / ".env.local.example"
    api_client = WEB / "lib" / "api.ts"
    live_page = WEB / "app" / "live-analysis" / "page.tsx"
    deployment_doc = ROOT / "docs" / "deployment.md"

    checks.add("netlify.toml exists", netlify_path.exists(), str(netlify_path))
    checks.add("web package exists", package_path.exists(), str(package_path))
    checks.add("env example exists", env_example.exists(), str(env_example))
    checks.add("live-analysis route exists", live_page.exists(), str(live_page))

    if netlify_path.exists():
        config = tomllib.loads(netlify_path.read_text(encoding="utf-8"))
        build = config.get("build", {})
        config_ok = (
            build.get("base") == "apps/web"
            and "npm run build" in build.get("command", "")
            and build.get("publish") == ".next"
        )
        checks.add(
            "Netlify monorepo config",
            config_ok,
            f"base={build.get('base')} command={build.get('command')} publish={build.get('publish')}",
        )

    source_hits: list[str] = []
    for path in frontend_source_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "http://localhost" in text or "http://127.0.0.1" in text:
            source_hits.append(str(path.relative_to(ROOT)))
    checks.add(
        "no production localhost URL",
        not source_hits,
        "none" if not source_hits else ", ".join(source_hits),
    )

    api_text = api_client.read_text(encoding="utf-8", errors="ignore") if api_client.exists() else ""
    helpers = ("getApiBaseUrl", "isApiConfigured", "apiFetch", "getApiHealth", "getLiveStatus")
    helpers_ok = all(f"function {name}" in api_text or f"const {name}" in api_text for name in helpers)
    checks.add("API client helpers", helpers_ok, ", ".join(helpers))
    checks.add(
        "missing API URL handled",
        "api_not_configured" in api_text and "NEXT_PUBLIC_API_URL" in api_text,
        "typed api_not_configured error",
    )
    checks.add(
        "offline and CORS handled",
        "api_unreachable" in api_text and "CORS must allow this Netlify domain" in api_text,
        "typed api_unreachable error with CORS guidance",
    )

    tracked = git_files()
    weights = [path for path in tracked if path.lower().endswith(WEIGHT_EXTS)]
    videos = [path for path in tracked if path.lower().endswith(VIDEO_EXTS)]
    reports = [
        path for path in tracked
        if path != "data/reports/.gitkeep"
        and (path.lower().endswith(".pdf") or any(path.startswith(folder) for folder in REPORT_DIRS))
    ]
    checks.add("no model weights tracked", not weights, "none" if not weights else str(weights[:5]))
    checks.add("no videos tracked", not videos, "none" if not videos else str(videos[:5]))
    checks.add("no generated reports tracked", not reports, "none" if not reports else str(reports[:5]))

    docs_text = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in (ROOT / "README.md", deployment_doc)
        if path.exists()
    )
    docs_ok = (
        "Netlify" in docs_text
        and "NEXT_PUBLIC_API_URL" in docs_text
        and "HORALIX_CORS_ORIGINS" in docs_text
        and "FastAPI" in docs_text
    )
    checks.add("deployment docs", docs_ok, "Netlify + external FastAPI + CORS documented")

    build_ok, build_detail = run_build()
    checks.add("frontend build without API URL", build_ok, build_detail)

    print("\n=== Netlify frontend readiness ===")
    for name, ok, detail in checks.rows:
        print(f"{name:32s} {'PASS' if ok else 'FAIL':4s}  {detail}")

    if checks.blockers:
        print("\nBLOCKED: " + " | ".join(checks.blockers))
        return 1
    print("\nNETLIFY FRONTEND READY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
