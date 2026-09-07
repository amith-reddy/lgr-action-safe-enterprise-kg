#!/usr/bin/env python3
"""Reproduce LGR results from frozen inputs without mutating the release."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "data" / "evomem_enterprise"
DEFAULT_OUTPUT = ROOT / "experiments" / "lgr_reproduction"
INPUT_DIRS = ("config", "generated", "ontology", "policy", "workflows", "schema", "prompts")


def hashes(root: Path) -> dict[str, str]:
    result = {}
    for directory in INPUT_DIRS:
        base = root / directory
        if not base.exists():
            continue
        for path in sorted(item for item in base.rglob("*") if item.is_file()):
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def run(script: str, *arguments: str) -> dict:
    command = [sys.executable, str(ROOT / "scripts" / script), *arguments]
    process = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    record = {"command": command, "returncode": process.returncode, "stdout": process.stdout, "stderr": process.stderr}
    if process.returncode:
        raise RuntimeError(json.dumps(record, indent=2))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    source, output = args.data_root.resolve(), args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        if not args.force:
            raise SystemExit(f"refusing to overwrite nonempty output directory: {output}; pass --force")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    before = hashes(source)
    commands = []
    with tempfile.TemporaryDirectory(prefix="lgr-reproduction-") as temporary:
        working = Path(temporary) / "evomem"
        working.mkdir()
        for directory in INPUT_DIRS:
            if (source / directory).exists():
                shutil.copytree(source / directory, working / directory)
        commands.append(run("validate_evomem_enterprise.py", "--data-root", str(working)))
        commands.append(run("verify_gold_labels.py", "--data-root", str(working)))
        commands.append(run("verify_evidence_labels.py", "--data-root", str(working)))
        commands.append(run("run_phase3_experiments.py", "--data-root", str(working), "--output-dir", str(output)))
        commands.append(run("report_evidence_regimes.py", "--data-root", str(working), "--output-dir", str(output)))
        commands.append(run("validate_phase3_results.py", "--data-root", str(working), "--output-dir", str(output)))
        commands.append(run("run_decisive_strata.py", "--data-root", str(working), "--output-dir", str(output)))
    after = hashes(source)
    report = {
        "status": "pass" if before == after else "fail",
        "source_data_root": str(source),
        "output_dir": str(output),
        "python": sys.version,
        "frozen_input_sha256": before,
        "source_inputs_unchanged": before == after,
        "commands": [{"command": item["command"], "returncode": item["returncode"]} for item in commands],
    }
    (output / "reproduction_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
