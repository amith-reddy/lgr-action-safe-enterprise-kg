#!/usr/bin/env python3
"""Build and verify the LGR/JWS release-candidate archive."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUBMISSION = ROOT / "submission" / "ickg_lgr_2026"
VERSION = "3.0.0"
DEFAULT_CANDIDATE = "rc1"


def archive_path(candidate: str) -> Path:
    return SUBMISSION / f"lgr_jws_artifact_{candidate}.tar.gz"


def report_path(candidate: str) -> Path:
    suffix = "" if candidate == DEFAULT_CANDIDATE else f"_{candidate}"
    return SUBMISSION / f"artifact_archive_report{suffix}.json"


def package_name(candidate: str) -> str:
    return f"lgr-jws-artifact-{VERSION}-{candidate}"

INCLUDE_DIRS = (
    "scripts",
    "tests",
    "data/evomem_enterprise",
    "data/evomem_enterprise_v3",
    "experiments/lgr_jws",
    "experiments/lgr_reproduction",
)
INCLUDE_FILES = (
    "LICENSE",
    "LICENSE-DATA",
    ".zenodo.json",
    "submission/ickg_lgr_2026/ickg_lgr.tex",
    "submission/ickg_lgr_2026/ickg_lgr.pdf",
    "submission/ickg_lgr_2026/README.md",
    "submission/ickg_lgr_2026/REPRODUCIBILITY.md",
    "submission/ickg_lgr_2026/JWS_REVIEW_TRIAGE_AND_IMPLEMENTATION.md",
    "submission/ickg_lgr_2026/ARTIFACT_RELEASE_CHECKLIST.md",
    "submission/ickg_lgr_2026/CITATION.cff",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_inputs(destination: Path) -> None:
    for relative in INCLUDE_DIRS:
        source = ROOT / relative
        shutil.copytree(
            source,
            destination / relative,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
    for relative in INCLUDE_FILES:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def write_manifest(package_root: Path) -> dict[str, str]:
    files = sorted(
        path
        for path in package_root.rglob("*")
        if path.is_file() and path.name != "MANIFEST.sha256"
    )
    manifest = {str(path.relative_to(package_root)): digest(path) for path in files}
    lines = [f"{value}  {name}" for name, value in manifest.items()]
    (package_root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return manifest


def verify_manifest(package_root: Path) -> tuple[bool, list[str]]:
    mismatches = []
    for line in (package_root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        path = package_root / relative
        if not path.is_file() or digest(path) != expected:
            mismatches.append(relative)
    return not mismatches, mismatches


def run_reproduction(package_root: Path) -> dict:
    output = package_root / "verification-output"
    process = subprocess.run(
        [
            sys.executable,
            str(package_root / "scripts" / "reproduce_lgr_release.py"),
            "--output-dir",
            str(output),
        ],
        cwd=package_root,
        text=True,
        capture_output=True,
    )
    status = None
    report_path = output / "reproduction_report.json"
    if report_path.exists():
        status = json.loads(report_path.read_text(encoding="utf-8")).get("status")
    return {
        "returncode": process.returncode,
        "reported_status": status,
        "stderr_tail": process.stderr[-2000:],
    }


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    base = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if target != base and base not in target.parents:
            raise ValueError(f"archive member escapes destination: {member.name}")
    archive.extractall(destination)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--release-candidate",
        default=DEFAULT_CANDIDATE,
        help="release-candidate tag; names the archive, package root, and report",
    )
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    candidate = args.release_candidate
    PACKAGE = package_name(candidate)
    args.output = args.output or archive_path(candidate)
    args.report = args.report or report_path(candidate)
    output = args.output.resolve()
    if output.exists():
        if not args.force:
            raise SystemExit(f"refusing to overwrite {output}; pass --force")
        output.unlink()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="lgr-artifact-build-") as temporary:
        package_root = Path(temporary) / PACKAGE
        package_root.mkdir()
        copy_inputs(package_root)
        manifest = write_manifest(package_root)
        with tarfile.open(output, "w:gz") as archive:
            archive.add(package_root, arcname=PACKAGE)

    with tempfile.TemporaryDirectory(prefix="lgr-artifact-verify-") as temporary:
        extract_root = Path(temporary)
        with tarfile.open(output, "r:gz") as archive:
            safe_extract(archive, extract_root)
        package_root = extract_root / PACKAGE
        manifest_ok, mismatches = verify_manifest(package_root)
        reproduction = run_reproduction(package_root)

    report = {
        "release_candidate": candidate,
        "package_root": PACKAGE,
        "status": "pass"
        if manifest_ok and reproduction["returncode"] == 0 and reproduction["reported_status"] == "pass"
        else "fail",
        # Name only: an absolute path would leak the builder's local layout.
        "archive": output.name,
        "archive_sha256": digest(output),
        "archive_bytes": output.stat().st_size,
        "manifest_entries": len(manifest),
        "manifest_verified_after_clean_extraction": manifest_ok,
        "manifest_mismatches": mismatches,
        "frozen_release_reproduction_after_clean_extraction": reproduction,
        "license": "MIT throughout: code under LICENSE, generated benchmark data and recorded outputs under LICENSE-DATA, both at the package root; manuscript sources under submission/ are not covered by either",
        "doi_status": "no DOI claimed; .zenodo.json is prepared for deposit but the archive has not been deposited",
    }
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
