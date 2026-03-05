import sys
import os
import argparse

# Allow running as a script from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import (
    get_logger, read_transcript, write_json, write_text,
    get_output_dir, now_iso,
)
from scripts.extract_memo import extract_memo
from scripts.generate_agent_spec import generate_agent_spec

logger = get_logger("pipeline_a")


def run_pipeline_a(
    transcript_path: str,
    account_id: str | None = None,
    prefer_llm: bool = True,
) -> dict:
    """
    Execute Pipeline A for a single demo call transcript.

    Args:
        transcript_path: Path to the demo call transcript file.
        account_id: Override account ID (auto-detected from transcript if None).
        prefer_llm: Whether to attempt LLM extraction first.

    Returns:
        Dict with keys: account_id, memo_path, spec_path, memo, spec
    """
    logger.info("Pipeline A started — transcript: %s", transcript_path)

    # Step 1: Read transcript
    transcript = read_transcript(transcript_path)
    logger.info("Transcript loaded (%d chars)", len(transcript))

    # Step 2: Extract account memo
    memo = extract_memo(transcript, prefer_llm=prefer_llm)
    memo["source_file"] = os.path.basename(transcript_path)
    memo["pipeline"] = "A"
    memo["extracted_at"] = now_iso()
    memo["version"] = "v1"

    # Override account ID if provided
    if account_id:
        memo["account_id"] = account_id

    effective_account_id = memo.get("account_id") or "unknown"
    logger.info("Account ID: %s, Company: %s", effective_account_id, memo.get("company_name"))

    # Step 3: Generate agent spec v1
    spec = generate_agent_spec(memo, version="v1")

    # Step 4: Store artifacts
    out_dir = get_output_dir(effective_account_id, "v1")
    memo_path = os.path.join(out_dir, "memo.json")
    spec_path = os.path.join(out_dir, "agent_spec.json")

    write_json(memo, memo_path)
    write_json(spec, spec_path)

    logger.info("Pipeline A complete — outputs written to %s", out_dir)
    logger.info("  memo.json: %s", memo_path)
    logger.info("  agent_spec.json: %s", spec_path)

    # Log open questions
    questions = memo.get("questions_or_unknowns", [])
    if questions:
        logger.warning("Open questions/unknowns for %s:", effective_account_id)
        for q in questions:
            logger.warning("  ? %s", q)

    return {
        "account_id": effective_account_id,
        "memo_path": memo_path,
        "spec_path": spec_path,
        "memo": memo,
        "spec": spec,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline A: Demo Call Transcript → v1 Account Memo + Agent Spec"
    )
    parser.add_argument("transcript", help="Path to the demo call transcript file")
    parser.add_argument(
        "--account-id",
        help="Override account ID (auto-detected from transcript if not provided)",
        default=None,
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use rule-based extraction only (skip LLM even if available)",
    )
    args = parser.parse_args()

    result = run_pipeline_a(
        transcript_path=args.transcript,
        account_id=args.account_id,
        prefer_llm=not args.no_llm,
    )
    print(f"\nDone. Outputs saved to: outputs/accounts/{result['account_id']}/v1/")
    print(f"  memo.json     : {result['memo_path']}")
    print(f"  agent_spec.json: {result['spec_path']}")


if __name__ == "__main__":
    main()
