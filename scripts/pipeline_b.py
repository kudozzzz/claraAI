import sys
import os
import argparse

# Allow running as a script from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils import (
    get_logger, read_transcript, read_json, write_json, write_text,
    get_output_dir, get_account_dir, now_iso,
)
from scripts.update_agent import apply_onboarding_update

logger = get_logger("pipeline_b")


def run_pipeline_b(
    onboarding_transcript_path: str,
    account_id: str,
    prefer_llm: bool = True,
) -> dict:
    """
    Execute Pipeline B for a single onboarding call transcript.

    Args:
        onboarding_transcript_path: Path to onboarding call transcript file.
        account_id: Account ID for the existing v1 artifacts.
        prefer_llm: Whether to attempt LLM extraction first.

    Returns:
        Dict with keys: account_id, v2_memo_path, v2_spec_path, changelog_path, ...
    """
    logger.info("Pipeline B started — account: %s, transcript: %s", account_id, onboarding_transcript_path)

    # Step 1: Load v1 artifacts
    v1_dir = get_output_dir(account_id, "v1")
    v1_memo_path = os.path.join(v1_dir, "memo.json")
    v1_spec_path = os.path.join(v1_dir, "agent_spec.json")

    if not os.path.exists(v1_memo_path):
        raise FileNotFoundError(
            f"v1 memo not found at {v1_memo_path}. "
            f"Run Pipeline A first for account {account_id}."
        )
    if not os.path.exists(v1_spec_path):
        raise FileNotFoundError(
            f"v1 agent spec not found at {v1_spec_path}. "
            f"Run Pipeline A first for account {account_id}."
        )

    v1_memo = read_json(v1_memo_path)
    v1_spec = read_json(v1_spec_path)
    logger.info("v1 artifacts loaded for account=%s", account_id)

    # Step 2: Read onboarding transcript
    onboarding_transcript = read_transcript(onboarding_transcript_path)
    logger.info("Onboarding transcript loaded (%d chars)", len(onboarding_transcript))

    # Step 3: Apply onboarding update
    v2_memo, v2_spec, changelog_md, conflicts = apply_onboarding_update(
        v1_memo=v1_memo,
        v1_spec=v1_spec,
        onboarding_transcript=onboarding_transcript,
    )

    # Annotate metadata
    v2_memo["source_file"] = os.path.basename(onboarding_transcript_path)
    v2_memo["pipeline"] = "B"
    v2_memo["updated_at"] = now_iso()
    v2_memo["version"] = "v2"

    # Step 4: Store v2 artifacts
    out_dir = get_output_dir(account_id, "v2")
    v2_memo_path = os.path.join(out_dir, "memo.json")
    v2_spec_path = os.path.join(out_dir, "agent_spec.json")

    write_json(v2_memo, v2_memo_path)
    write_json(v2_spec, v2_spec_path)

    # Step 5: Write changelog to account root (not versioned)
    account_dir = get_account_dir(account_id)
    changelog_path = os.path.join(account_dir, "changelog.md")
    write_text(changelog_md, changelog_path)

    # Also write a structured diff JSON for programmatic use
    from scripts.utils import deep_diff
    diff_data = {
        "account_id": account_id,
        "generated_at": now_iso(),
        "memo_diff": deep_diff(v1_memo, v2_memo),
        "conflicts_resolved": conflicts,
    }
    diff_path = os.path.join(account_dir, "diff.json")
    write_json(diff_data, diff_path)

    logger.info("Pipeline B complete — outputs written to %s", out_dir)
    logger.info("  v2/memo.json      : %s", v2_memo_path)
    logger.info("  v2/agent_spec.json: %s", v2_spec_path)
    logger.info("  changelog.md      : %s", changelog_path)
    logger.info("  diff.json         : %s", diff_path)

    if conflicts:
        logger.info("%d conflict(s) resolved during merge:", len(conflicts))
        for c in conflicts:
            logger.info("  ~ %s: '%s' → '%s'", c["field"], c["old_value"], c["new_value"])

    remaining = v2_memo.get("questions_or_unknowns", [])
    if remaining:
        logger.warning("Remaining open questions for %s:", account_id)
        for q in remaining:
            logger.warning("  ? %s", q)
    else:
        logger.info("All questions resolved for %s", account_id)

    return {
        "account_id": account_id,
        "v2_memo_path": v2_memo_path,
        "v2_spec_path": v2_spec_path,
        "changelog_path": changelog_path,
        "diff_path": diff_path,
        "v2_memo": v2_memo,
        "v2_spec": v2_spec,
        "conflicts": conflicts,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline B: Onboarding Transcript → v2 Account Memo + Agent Spec + Changelog"
    )
    parser.add_argument("transcript", help="Path to the onboarding call transcript file")
    parser.add_argument("--account-id", required=True, help="Account ID for existing v1 artifacts")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Use rule-based extraction only (skip LLM even if available)",
    )
    args = parser.parse_args()

    result = run_pipeline_b(
        onboarding_transcript_path=args.transcript,
        account_id=args.account_id,
        prefer_llm=not args.no_llm,
    )

    print(f"\nDone. Outputs saved to: outputs/accounts/{result['account_id']}/")
    print(f"  v2/memo.json      : {result['v2_memo_path']}")
    print(f"  v2/agent_spec.json: {result['v2_spec_path']}")
    print(f"  changelog.md      : {result['changelog_path']}")
    print(f"  diff.json         : {result['diff_path']}")
    print(f"\nConflicts resolved: {len(result['conflicts'])}")


if __name__ == "__main__":
    main()
