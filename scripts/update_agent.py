import json
from typing import Any

from scripts.utils import get_logger, now_iso, deep_diff
from scripts.extract_memo import extract_memo
from scripts.generate_agent_spec import generate_agent_spec

logger = get_logger(__name__)


# Merge logic

def _merge_lists(existing: list, updates: list) -> list:
    """Merge two lists, deduplicating while preserving order (updates take priority)."""
    combined = list(existing)
    for item in updates:
        if item not in combined:
            combined.append(item)
    return combined


def _merge_dict(base: dict, update: dict) -> tuple[dict, list]:
    """
    Deep merge update dict into base dict.
    Returns (merged_dict, list_of_conflicts).
    A conflict occurs when both dicts have a value for the same scalar key
    and the values differ.
    """
    merged = dict(base)
    conflicts = []

    for key, new_val in update.items():
        old_val = base.get(key)

        if new_val is None:
            # Update explicitly sets null — keep existing value, note it
            continue
        elif old_val is None or old_val == "" or old_val == [] or old_val == {}:
            # Base was empty — apply update
            merged[key] = new_val
        elif isinstance(old_val, dict) and isinstance(new_val, dict):
            # Recurse
            sub_merged, sub_conflicts = _merge_dict(old_val, new_val)
            merged[key] = sub_merged
            conflicts.extend(sub_conflicts)
        elif isinstance(old_val, list) and isinstance(new_val, list):
            merged[key] = _merge_lists(old_val, new_val)
        elif old_val != new_val:
            # Conflict — update wins but we record it
            conflicts.append({
                "field": key,
                "old_value": old_val,
                "new_value": new_val,
                "resolution": "onboarding_value_applied",
            })
            merged[key] = new_val

    return merged, conflicts


def merge_memo(v1_memo: dict, onboarding_memo: dict) -> tuple[dict, list]:
    """
    Merge onboarding extracted data into v1 memo to produce v2 memo.

    Returns:
        (v2_memo, conflicts): merged memo and list of conflict records
    """
    logger.info("Merging onboarding data into v1 memo for account=%s", v1_memo.get("account_id"))

    # Start with v1 as base
    v2, conflicts = _merge_dict(v1_memo, onboarding_memo)

    # Update metadata
    v2["account_id"] = v1_memo.get("account_id", onboarding_memo.get("account_id"))
    v2["company_name"] = onboarding_memo.get("company_name") or v1_memo.get("company_name")
    v2["version"] = "v2"

    # Clear questions_or_unknowns that have now been resolved
    existing_questions = v1_memo.get("questions_or_unknowns", [])
    remaining_questions = []
    for q in existing_questions:
        # Check if this question is now answered
        q_lower = q.lower()
        if "phone number" in q_lower and v2.get("emergency_routing_rules", {}).get("primary_transfer_number"):
            continue  # Resolved
        if "timezone" in q_lower and v2.get("business_hours", {}).get("timezone"):
            continue  # Resolved
        if "address" in q_lower and v2.get("office_address"):
            continue  # Resolved
        if "business hours" in q_lower and "start" not in q_lower and v2.get("business_hours", {}).get("start"):
            continue  # Resolved
        if "services" in q_lower and v2.get("services_supported"):
            continue  # Resolved
        if "transfer timeout" in q_lower and v2.get("emergency_routing_rules", {}).get("transfer_timeout_seconds"):
            continue  # Resolved
        if "main transfer number" in q_lower and v2.get("call_transfer_rules", {}).get("business_hours_transfer_number"):
            continue  # Resolved
        if "emergency trigger" in q_lower and v2.get("emergency_definition"):
            continue  # Resolved
        remaining_questions.append(q)

    # Add new unknowns from onboarding extraction
    new_questions = onboarding_memo.get("questions_or_unknowns", [])
    for q in new_questions:
        if q not in remaining_questions:
            remaining_questions.append(q)

    v2["questions_or_unknowns"] = remaining_questions

    # Update notes
    v2["notes"] = (
        f"{v1_memo.get('notes', '')} | "
        f"Updated from onboarding call on {now_iso()[:10]}. "
        f"{len(conflicts)} field(s) updated."
    ).strip(" |")

    return v2, conflicts


# Changelog generator

def generate_changelog(
    v1_memo: dict,
    v2_memo: dict,
    v1_spec: dict,
    v2_spec: dict,
    conflicts: list,
    account_id: str,
) -> str:
    """Generate a Markdown changelog comparing v1 and v2 artifacts."""

    memo_diffs = deep_diff(v1_memo, v2_memo)
    spec_diffs = deep_diff(
        {k: v for k, v in v1_spec.items() if k not in ("system_prompt", "created_at")},
        {k: v for k, v in v2_spec.items() if k not in ("system_prompt", "created_at")},
    )

    lines = [
        f"# Changelog — {account_id}",
        "",
        f"**Generated:** {now_iso()}",
        f"**Account:** {v2_memo.get('company_name', account_id)}",
        "",
        "## Summary",
        "",
        f"- Version: v1 (demo) → v2 (post-onboarding)",
        f"- Total memo field changes: {len(memo_diffs)}",
        f"- Total spec field changes: {len(spec_diffs)}",
        f"- Conflicts resolved: {len(conflicts)}",
        "",
    ]

    # Account memo changes
    lines += ["## Account Memo Changes", ""]
    if memo_diffs:
        for d in memo_diffs:
            action = d["action"]
            path = d["path"]
            old_v = d["old"]
            new_v = d["new"]
            if action == "added":
                lines.append(f"- **ADDED** `{path}`: `{new_v}`")
            elif action == "removed":
                lines.append(f"- **REMOVED** `{path}` (was: `{old_v}`)")
            elif action == "changed":
                lines.append(f"- **CHANGED** `{path}`")
                lines.append(f"  - Before: `{old_v}`")
                lines.append(f"  - After:  `{new_v}`")
    else:
        lines.append("_No changes detected in account memo._")

    lines += ["", "## Agent Spec Changes", ""]
    if spec_diffs:
        for d in spec_diffs:
            action = d["action"]
            path = d["path"]
            old_v = d["old"]
            new_v = d["new"]
            if action == "added":
                lines.append(f"- **ADDED** `{path}`: `{new_v}`")
            elif action == "removed":
                lines.append(f"- **REMOVED** `{path}` (was: `{old_v}`)")
            elif action == "changed":
                lines.append(f"- **CHANGED** `{path}`")
                lines.append(f"  - Before: `{old_v}`")
                lines.append(f"  - After:  `{new_v}`")
    else:
        lines += [
            "_Key variable changes are listed above. System prompt was regenerated from updated memo._",
            "_See v1/agent_spec.json vs v2/agent_spec.json for full prompt diff._",
        ]

    # Conflicts
    if conflicts:
        lines += ["", "## Resolved Conflicts", ""]
        for c in conflicts:
            lines.append(f"- **Field:** `{c['field']}`")
            lines.append(f"  - Demo value: `{c['old_value']}`")
            lines.append(f"  - Onboarding value: `{c['new_value']}`")
            lines.append(f"  - Resolution: {c['resolution']}")

    # Remaining unknowns
    remaining = v2_memo.get("questions_or_unknowns", [])
    if remaining:
        lines += ["", "## Remaining Open Questions", ""]
        for q in remaining:
            lines.append(f"- {q}")
    else:
        lines += ["", "## Remaining Open Questions", "", "_All questions resolved._"]

    return "\n".join(lines)


# Public pipeline function

def apply_onboarding_update(
    v1_memo: dict,
    v1_spec: dict,
    onboarding_transcript: str,
) -> tuple[dict, dict, str, list]:
    """
    Apply onboarding transcript data to v1 artifacts, producing v2.

    Args:
        v1_memo: Existing v1 account memo.
        v1_spec: Existing v1 agent spec.
        onboarding_transcript: Raw text of the onboarding call transcript.

    Returns:
        (v2_memo, v2_spec, changelog_md, conflicts)
    """
    account_id = v1_memo.get("account_id", "unknown")
    logger.info("Applying onboarding update for account=%s", account_id)

    # Extract new data from onboarding transcript
    onboarding_memo = extract_memo(onboarding_transcript, prefer_llm=True)
    # Preserve the original account_id
    onboarding_memo["account_id"] = account_id

    # Merge into v1 memo
    v2_memo, conflicts = merge_memo(v1_memo, onboarding_memo)
    v2_memo["version"] = "v2"

    # Generate new agent spec
    v2_spec = generate_agent_spec(v2_memo, version="v2")

    # Generate changelog
    changelog_md = generate_changelog(
        v1_memo=v1_memo,
        v2_memo=v2_memo,
        v1_spec=v1_spec,
        v2_spec=v2_spec,
        conflicts=conflicts,
        account_id=account_id,
    )

    logger.info(
        "Onboarding update complete: %d memo diffs, %d conflicts",
        len(deep_diff(v1_memo, v2_memo)),
        len(conflicts),
    )

    return v2_memo, v2_spec, changelog_md, conflicts
