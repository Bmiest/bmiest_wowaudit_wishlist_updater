"""Fold one run summary into the dashboard's data directory.

The data directory lives on the `dashboard-data` branch so history survives between runs:

    data/runs/<run_id>.json   full summary of each run (the newest KEEP_RUNS are kept)
    data/index.json           run headers, newest first (no gear or QE results)
    data/latest.json          full summary of the newest run

Usage: python -m wishlist_updater.dashboard SUMMARY_JSON DATA_DIR
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KEEP_RUNS = 200
_RUN_ID_RE = re.compile(r"^[0-9A-Za-z_-]{1,40}$")


def run_header(summary: dict) -> dict:
    return {
        **summary["run"],
        "characters": [
            {
                "name": c["name"],
                "realm": c["realm"],
                "region": c["region"],
                "class": c.get("class"),
                "spec": c.get("spec"),
                "error": c.get("error"),
                "skipped": c.get("skipped"),
                "warnings": c.get("warnings", []),
                "reports": [
                    {
                        k: r.get(k)
                        for k in ("difficulty", "report_id", "report_url", "uploaded_via", "error")
                    }
                    for r in c.get("reports", [])
                ],
            }
            for c in summary.get("characters", [])
        ],
    }


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")


def publish(summary: dict | None, data_dir: Path, keep: int = KEEP_RUNS) -> list[dict]:
    """Add `summary` (if any) to data_dir and rebuild index.json/latest.json. Returns the index."""
    runs_dir = data_dir / "runs"
    if summary is not None:
        run_id = str(summary["run"].get("id") or "")
        if not _RUN_ID_RE.match(run_id):
            raise ValueError(f"Refusing to publish a summary with run id {run_id!r}")
        _write(runs_dir / f"{run_id}.json", summary)

    runs = [(p, s) for p in runs_dir.glob("*.json") if (s := _load(p)) and "run" in s]
    runs.sort(key=lambda ps: ps[1]["run"].get("started_at") or "", reverse=True)
    for path, _ in runs[keep:]:
        path.unlink()
    runs = runs[:keep]

    index = [run_header(s) for _, s in runs]
    _write(data_dir / "index.json", {"schema": 1, "runs": index})
    if runs:
        _write(data_dir / "latest.json", runs[0][1])
    return index


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    summary_path, data_dir = Path(argv[0]), Path(argv[1])
    # A failed run may not have produced a summary; still rebuild so the site deploys.
    summary = _load(summary_path) if summary_path.exists() else None
    index = publish(summary, data_dir)
    print(f"dashboard: {len(index)} run(s) in {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
