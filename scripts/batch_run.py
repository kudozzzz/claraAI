"""
batch_run.py — Run all 10 call files through both Pipeline A and Pipeline B.

Usage:
    python scripts/batch_run.py                          # auto-discover data/ folder
    python scripts/batch_run.py --demo-dir data/demo --onboarding-dir data/onboarding
    python scripts/batch_run.py --no-llm                 # force rule-based extraction
"""

import sys
import os
import argparse
import json
import traceback
from pathlib import Path

# Allow running as a script from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import get_logger, now_iso, write_json
from scripts.pipeline_a import run_pipeline_a
from scripts.pipeline_b import run_pipeline_b

logger = get_logger("batch_run")


def discover_files(directory: str, pattern: str = "*.txt") -> list:
    """Return sorted list of files matching pattern in directory."""
    return sorted(Path(directory).glob(pattern))


def match_demo_onboarding(demo_files: list, onboarding_files: list) -> list:
    """
    Pair demo files with their matching onboarding files.
    Matching strategy: extract the numeric suffix from filenames
    (e.g., demo_001.txt → 001, onboarding_001.txt → 001).

    Returns list of (demo_path, onboarding_path, account_id) tuples.
    """
    import re

    def extract_num(path) -> str:
        m = re.search(r"(\d+)", Path(path).stem)
        return m.group(1) if m else ""

    demo_map = {extract_num(f): f for f in demo_files}
    onboarding_map = {extract_num(f): f for f in onboarding_files}

    pairs = []
    for num in sorted(set(list(demo_map.keys()) + list(onboarding_map.keys()))):
        demo_f = demo_map.get(num)
        onboard_f = onboarding_map.get(num)
        account_id = f"account_{num}"
        pairs.append((demo_f, onboard_f, account_id))

    return pairs


def run_batch(
    demo_dir: str,
    onboarding_dir: str,
    prefer_llm: bool = True,
) -> dict:
    """
    Run Pipeline A on all demo files, then Pipeline B on all onboarding files.

    Returns a summary dict with results and any errors.
    """
    logger.info("=" * 60)
    logger.info("BATCH RUN STARTED — %s", now_iso())
    logger.info("Demo dir      : %s", demo_dir)
    logger.info("Onboarding dir: %s", onboarding_dir)
    logger.info("LLM mode      : %s", "enabled" if prefer_llm else "rule-based only")
    logger.info("=" * 60)

    demo_files = discover_files(demo_dir)
    onboarding_files = discover_files(onboarding_dir)

    logger.info("Found %d demo files, %d onboarding files", len(demo_files), len(onboarding_files))

    pairs = match_demo_onboarding(demo_files, onboarding_files)
    logger.info("Matched %d pairs", len(pairs))

    summary = {
        "batch_run_at": now_iso(),
        "llm_mode": "prefer_llm" if prefer_llm else "rule_based",
        "total_accounts": len(pairs),
        "pipeline_a_results": [],
        "pipeline_b_results": [],
        "errors": [],
    }

    # -----------------------------------------------------------------------
    # Pipeline A: Demo calls → v1
    # -----------------------------------------------------------------------
    logger.info("")
    logger.info("=== PIPELINE A (Demo → v1) ===")

    for demo_path, onboard_path, account_id in pairs:
        if demo_path is None:
            logger.warning("No demo file found for %s — skipping Pipeline A", account_id)
            summary["errors"].append({
                "account_id": account_id,
                "pipeline": "A",
                "error": "No demo transcript found",
            })
            continue

        logger.info("  Processing [A] %s — %s", account_id, demo_path.name)
        try:
            result = run_pipeline_a(
                transcript_path=str(demo_path),
                account_id=account_id,
                prefer_llm=prefer_llm,
            )
            summary["pipeline_a_results"].append({
                "account_id": account_id,
                "status": "success",
                "company_name": result["memo"].get("company_name"),
                "memo_path": result["memo_path"],
                "spec_path": result["spec_path"],
                "open_questions": result["memo"].get("questions_or_unknowns", []),
            })
            logger.info("    ✓ Pipeline A success: %s", result["memo"].get("company_name"))
        except Exception as exc:
            logger.error("    ✗ Pipeline A failed for %s: %s", account_id, exc)
            logger.debug(traceback.format_exc())
            summary["errors"].append({
                "account_id": account_id,
                "pipeline": "A",
                "error": str(exc),
            })
            summary["pipeline_a_results"].append({
                "account_id": account_id,
                "status": "error",
                "error": str(exc),
            })

    # -----------------------------------------------------------------------
    # Pipeline B: Onboarding calls → v2
    # -----------------------------------------------------------------------
    logger.info("")
    logger.info("=== PIPELINE B (Onboarding → v2) ===")

    for demo_path, onboard_path, account_id in pairs:
        if onboard_path is None:
            logger.warning("No onboarding file found for %s — skipping Pipeline B", account_id)
            summary["errors"].append({
                "account_id": account_id,
                "pipeline": "B",
                "error": "No onboarding transcript found",
            })
            continue

        # Check that v1 exists
        v1_memo_path = (
            Path(__file__).parent.parent
            / "outputs" / "accounts" / account_id / "v1" / "memo.json"
        )
        if not v1_memo_path.exists():
            logger.warning(
                "  Skipping [B] %s — v1 memo not found (Pipeline A must have failed)",
                account_id,
            )
            summary["errors"].append({
                "account_id": account_id,
                "pipeline": "B",
                "error": "v1 memo not found — Pipeline A must be run first",
            })
            continue

        logger.info("  Processing [B] %s — %s", account_id, onboard_path.name)
        try:
            result = run_pipeline_b(
                onboarding_transcript_path=str(onboard_path),
                account_id=account_id,
                prefer_llm=prefer_llm,
            )
            summary["pipeline_b_results"].append({
                "account_id": account_id,
                "status": "success",
                "company_name": result["v2_memo"].get("company_name"),
                "v2_memo_path": result["v2_memo_path"],
                "v2_spec_path": result["v2_spec_path"],
                "changelog_path": result["changelog_path"],
                "conflicts_resolved": len(result["conflicts"]),
                "remaining_questions": result["v2_memo"].get("questions_or_unknowns", []),
            })
            logger.info(
                "    ✓ Pipeline B success: %s (%d conflicts resolved)",
                result["v2_memo"].get("company_name"),
                len(result["conflicts"]),
            )
        except Exception as exc:
            logger.error("    ✗ Pipeline B failed for %s: %s", account_id, exc)
            logger.debug(traceback.format_exc())
            summary["errors"].append({
                "account_id": account_id,
                "pipeline": "B",
                "error": str(exc),
            })
            summary["pipeline_b_results"].append({
                "account_id": account_id,
                "status": "error",
                "error": str(exc),
            })

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    logger.info("")
    logger.info("=== BATCH RUN COMPLETE ===")

    a_success = sum(1 for r in summary["pipeline_a_results"] if r.get("status") == "success")
    b_success = sum(1 for r in summary["pipeline_b_results"] if r.get("status") == "success")
    total_errors = len(summary["errors"])

    logger.info("Pipeline A: %d/%d succeeded", a_success, len(pairs))
    logger.info("Pipeline B: %d/%d succeeded", b_success, len(pairs))
    if total_errors:
        logger.warning("Errors: %d", total_errors)
        for e in summary["errors"]:
            logger.warning("  [%s] %s: %s", e["pipeline"], e["account_id"], e["error"])

    # Write batch summary JSON
    summary_path = (
        Path(__file__).parent.parent / "outputs" / "batch_summary.json"
    )
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(summary_path), "w") as f:
        json.dump(summary, f, indent=2)

    logger.info("Batch summary written to: %s", summary_path)
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Batch runner: process all demo + onboarding calls through both pipelines"
    )
    parser.add_argument(
        "--demo-dir",
        default="data/demo",
        help="Directory containing demo call transcripts (default: data/demo)",
    )
    parser.add_argument(
        "--onboarding-dir",
        default="data/onboarding",
        help="Directory containing onboarding transcripts (default: data/onboarding)",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use rule-based extraction only (skip LLM even if available)",
    )
    args = parser.parse_args()

    # Resolve relative to repo root
    repo_root = Path(__file__).parent.parent
    demo_dir = str(repo_root / args.demo_dir)
    onboarding_dir = str(repo_root / args.onboarding_dir)

    summary = run_batch(
        demo_dir=demo_dir,
        onboarding_dir=onboarding_dir,
        prefer_llm=not args.no_llm,
    )

    # Print final counts
    a_success = sum(1 for r in summary["pipeline_a_results"] if r.get("status") == "success")
    b_success = sum(1 for r in summary["pipeline_b_results"] if r.get("status") == "success")
    total_errors = len(summary["errors"])

    print("\n" + "=" * 50)
    print(f"BATCH COMPLETE — {now_iso()}")
    print(f"  Pipeline A (demo → v1): {a_success}/{summary['total_accounts']} succeeded")
    print(f"  Pipeline B (onboarding → v2): {b_success}/{summary['total_accounts']} succeeded")
    if total_errors:
        print(f"  Errors: {total_errors}")
    print(f"\nOutputs: outputs/accounts/<account_id>/v1/ and v2/")
    print(f"Summary: outputs/batch_summary.json")


if __name__ == "__main__":
    main()
