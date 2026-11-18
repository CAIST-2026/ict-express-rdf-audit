"""Build a reproducible inventory of ICT project artefacts.

Read-only with respect to original files. Writes:
  ICT_EXPRESS_REVISION/00_AUDIT/PROJECT_INVENTORY.csv
"""
from __future__ import annotations

import csv
import hashlib
from datetime import datetime
from pathlib import Path

ROOT = Path("/Users/yuxiangsun/Desktop/ICT")
OUT = ROOT / "ICT_EXPRESS_REVISION" / "00_AUDIT" / "PROJECT_INVENTORY.csv"

EXCLUDE_PARTS = {
    "node_modules", ".git", "__pycache__", "site-packages", ".pytest_cache"
}
KEYWORDS = {
    "manuscript_pdf": ("main.pdf", "main(2).pdf", ".pdf"),
    "latex_source": (".tex", ".bib", ".cls", ".bst"),
    "experiment_code": ("experiment", "benchmark", "baseline", "probe", "latency", "scaling", "stat", "summarize", "diagnos", "audit"),
    "rdf_generator": ("scalable_data", "generator", "build_dataset"),
    "query_set": ("quer", "benchmark"),
    "alignment": ("align", "alias", "memory"),
    "per_query_records": ("per_query", "experimental_results", "probe_by_group", "results.csv"),
    "configuration": ("run_config", "config", "requirements"),
    "log": (".log",),
}


def classify(p: Path) -> str:
    name = p.name.lower()
    parts = {x.lower() for x in p.parts}
    if "ict_express_submission" in parts and "paper" in parts and name == "main.pdf":
        return "operative_manuscript_pdf"
    if name == "main(2).pdf":
        return "named_manuscript_pdf_missing_if_absent"
    if any(x in name for x in ("experiment", "benchmark", "baseline")) and p.suffix in {".py", ".csv"}:
        return "experiment_code_or_result"
    if "align" in name or "alias_index" in name or "knowledge" in name:
        return "alignment_artifact"
    if "per_query" in name or name in {"experimental_results.csv", "probe_by_group.csv"}:
        return "per_query_records"
    if name.startswith("run_config") or name in {"requirements.txt", "run_config.json"}:
        return "configuration"
    if p.suffix == ".py":
        return "source_code"
    if p.suffix in {".csv", ".json"}:
        return "result_or_data"
    if p.suffix == ".pdf":
        return "pdf"
    if p.suffix in {".tex", ".bib"}:
        return "latex_or_bib"
    return "other"


def sha256(path: Path, limit: int = 20_000_000) -> str:
    try:
        if path.stat().st_size > limit:
            return "SKIPPED_LARGE_FILE"
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return "UNREADABLE"


def main() -> None:
    rows = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in EXCLUDE_PARTS for part in p.parts):
            continue
        if ROOT / "ICT_EXPRESS_REVISION" in p.parents:
            continue
        st = p.stat()
        rows.append({
            "relative_path": str(p.relative_to(ROOT)),
            "category": classify(p),
            "bytes": st.st_size,
            "mtime": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
            "sha256": sha256(p),
        })
    rows.sort(key=lambda r: r["relative_path"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["relative_path", "category", "bytes", "mtime", "sha256"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT} rows={len(rows)}")


if __name__ == "__main__":
    main()
