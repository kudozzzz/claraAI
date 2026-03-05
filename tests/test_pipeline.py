"""
Tests for the Clara AI automation pipeline.

Run with:
    python -m pytest tests/ -v
    python -m pytest tests/ -v --tb=short
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure repo root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Force rule-based extraction in tests
os.environ["LLM_BACKEND"] = "rule_based"

from scripts.extract_memo import (
    extract_memo,
    extract_rule_based,
    _extract_business_hours,
    _extract_emergency_triggers,
    _extract_integration_constraints,
    _extract_company_name,
    _extract_address,
    _parse_time,
    _expand_day_range,
)
from scripts.generate_agent_spec import generate_agent_spec
from scripts.update_agent import merge_memo, generate_changelog, apply_onboarding_update
from scripts.utils import deep_diff, now_iso, write_json, read_json


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DEMO_TRANSCRIPT = """
DEMO CALL TRANSCRIPT — TestCo Fire Protection
Account ID: account_test
Date: 2024-01-01

Sarah: Hi, I'm Sarah from Clara Answers.

John: We're TestCo Fire Protection. We do sprinkler systems and fire suppression.
Our office is at 123 Main Street, Suite 400, Austin, TX 78701.
We're open Monday through Friday, 8 AM to 5 PM Central Time.

Sarah: What are emergencies for you?

John: An active sprinkler discharge, fire suppression discharge, fire alarm going off.
We also use ServiceTrade but that's internal — never mention it to customers.

Sarah: Great. What if the on-call doesn't answer?

John: Someone will call back within 15 minutes.
"""

SAMPLE_ONBOARDING_TRANSCRIPT = """
ONBOARDING CALL TRANSCRIPT — TestCo Fire Protection
Account ID: account_test
Date: 2024-02-01

James: Let's confirm details.

John: Business hours: Monday through Friday, 8 AM to 5 PM Central Time. America/Chicago.
Office: 123 Main Street, Suite 400, Austin, TX 78701.
Emergency primary: 512-555-0100. Backup: 512-555-0199.
Try primary for 30 seconds. If no answer, try backup. If backup fails, tell them
we will call back within 15 minutes.
Business hours line: 512-555-0150.

Carol: Also add CO detector activation as emergency.
Never create sprinkler jobs in ServiceTrade from field techs.
Clara should never mention ServiceTrade to callers.

James: Voice style — friendly but professional. Agent name Clara.
"""


@pytest.fixture
def sample_v1_memo():
    """A sample v1 memo extracted from the demo transcript."""
    return extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)


@pytest.fixture
def sample_v2_memo(sample_v1_memo):
    """A sample v2 memo after merging onboarding data."""
    onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
    v2, _ = merge_memo(sample_v1_memo, onboarding_memo)
    return v2


# ---------------------------------------------------------------------------
# Unit tests: time/day parsing helpers
# ---------------------------------------------------------------------------

class TestTimeHelpers:
    def test_parse_12h_am(self):
        assert _parse_time("8am") == "08:00"
        assert _parse_time("8 AM") == "08:00"

    def test_parse_12h_pm(self):
        assert _parse_time("5pm") == "17:00"
        assert _parse_time("5:30 PM") == "17:30"

    def test_parse_noon(self):
        assert _parse_time("12pm") == "12:00"

    def test_parse_midnight(self):
        assert _parse_time("12am") == "00:00"

    def test_parse_24h(self):
        assert _parse_time("14:30") == "14:30"

    def test_expand_day_range_weekdays(self):
        days = _expand_day_range("Monday", "Friday")
        assert days == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

    def test_expand_day_range_partial(self):
        days = _expand_day_range("Tuesday", "Thursday")
        assert days == ["Tuesday", "Wednesday", "Thursday"]

    def test_expand_day_range_weekend(self):
        days = _expand_day_range("Saturday", "Sunday")
        assert days == ["Saturday", "Sunday"]


# ---------------------------------------------------------------------------
# Unit tests: business hours extraction
# ---------------------------------------------------------------------------

class TestBusinessHoursExtraction:
    def test_extract_weekdays(self):
        text = "We're open Monday through Friday, 8 AM to 5 PM Mountain Time."
        hours = _extract_business_hours(text)
        assert hours["days"] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        assert hours["start"] == "08:00"
        assert hours["end"] == "17:00"
        assert hours["timezone"] == "America/Denver"

    def test_extract_with_saturday(self):
        text = "Monday through Friday, 7 AM to 6 PM, Saturday 8 AM to 2 PM Arizona time."
        hours = _extract_business_hours(text)
        assert "Saturday" in hours["days"]
        assert hours["timezone"] == "America/Phoenix"

    def test_extract_half_hour(self):
        text = "Monday through Friday, 7:30 AM to 5:30 PM Central Time."
        hours = _extract_business_hours(text)
        assert hours["start"] == "07:30"
        assert hours["end"] == "17:30"
        assert hours["timezone"] == "America/Chicago"

    def test_pacific_timezone(self):
        text = "8 AM to 5 PM Pacific Time, Monday through Friday."
        hours = _extract_business_hours(text)
        assert hours["timezone"] == "America/Los_Angeles"

    def test_phoenix_before_mst(self):
        """Arizona should map to America/Phoenix even when MST is mentioned."""
        text = "Arizona doesn't do daylight saving, we're always on MST — America/Phoenix timezone."
        hours = _extract_business_hours(text)
        assert hours["timezone"] == "America/Phoenix"


# ---------------------------------------------------------------------------
# Unit tests: emergency definition extraction
# ---------------------------------------------------------------------------

class TestEmergencyExtraction:
    def test_sprinkler_discharge(self):
        text = "An emergency is an active sprinkler discharge."
        triggers = _extract_emergency_triggers(text)
        assert any("sprinkler" in t.lower() for t in triggers)

    def test_fire_suppression(self):
        text = "Fire suppression system discharge is an emergency."
        triggers = _extract_emergency_triggers(text)
        assert any("fire suppression" in t.lower() for t in triggers)

    def test_power_failure(self):
        text = "Total power failure affecting the whole building is an emergency."
        triggers = _extract_emergency_triggers(text)
        assert any("power" in t.lower() for t in triggers)

    def test_co_detector(self):
        text = "CO detector activation is always an emergency."
        triggers = _extract_emergency_triggers(text)
        assert any("CO" in t or "carbon monoxide" in t.lower() for t in triggers)

    def test_no_emergency_keywords(self):
        text = "We just schedule inspections and do routine maintenance."
        triggers = _extract_emergency_triggers(text)
        assert triggers == []

    def test_clean_labels_not_snippets(self):
        """Emergency definitions should be clean labels, not raw text snippets."""
        text = "An active sprinkler discharge is a true emergency for us."
        triggers = _extract_emergency_triggers(text)
        for t in triggers:
            assert len(t) < 200, f"Trigger too long (likely a raw snippet): {t}"
            assert "\n" not in t, f"Trigger contains newline: {t}"


# ---------------------------------------------------------------------------
# Unit tests: integration constraint extraction
# ---------------------------------------------------------------------------

class TestIntegrationConstraints:
    def test_servicetrade_internal(self):
        text = "We use ServiceTrade. Never mention it to callers — internal use only."
        constraints = _extract_integration_constraints(text)
        assert any("ServiceTrade" in c for c in constraints)

    def test_servicetrade_sprinkler_jobs(self):
        text = "Never create sprinkler jobs in ServiceTrade from field techs."
        constraints = _extract_integration_constraints(text)
        assert any("sprinkler" in c.lower() for c in constraints)

    def test_zendesk(self):
        text = "Clara should never create or look up Zendesk tickets."
        constraints = _extract_integration_constraints(text)
        assert any("Zendesk" in c for c in constraints)

    def test_servicetitan(self):
        text = "We use ServiceTitan internally."
        constraints = _extract_integration_constraints(text)
        assert any("ServiceTitan" in c for c in constraints)

    def test_no_software_mentioned(self):
        text = "We just answer phones and dispatch technicians."
        constraints = _extract_integration_constraints(text)
        assert constraints == []


# ---------------------------------------------------------------------------
# Integration tests: extract_memo
# ---------------------------------------------------------------------------

class TestExtractMemo:
    def test_basic_extraction(self):
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        assert memo["account_id"] == "account_test"
        assert memo["company_name"] == "TestCo Fire Protection"
        assert memo["business_hours"]["timezone"] == "America/Chicago"
        assert memo["business_hours"]["start"] == "08:00"
        assert memo["business_hours"]["end"] == "17:00"

    def test_services_extracted(self):
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        assert len(memo["services_supported"]) > 0

    def test_emergency_defs_extracted(self):
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        assert len(memo["emergency_definition"]) > 0

    def test_questions_when_data_missing(self):
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        # Demo transcript doesn't have phone numbers, so questions should be flagged
        assert len(memo["questions_or_unknowns"]) > 0

    def test_no_hallucination(self):
        """Memo should not invent phone numbers that aren't in transcript."""
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        routing = memo.get("emergency_routing_rules", {})
        # No phone numbers in demo transcript
        assert routing.get("primary_transfer_number") is None

    def test_prefer_llm_false_uses_rule_based(self):
        """With prefer_llm=False, should use rule-based extraction."""
        memo = extract_memo(SAMPLE_DEMO_TRANSCRIPT, prefer_llm=False)
        assert memo["account_id"] == "account_test"

    def test_address_extraction(self):
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        assert memo["office_address"] is not None
        assert "123" in memo["office_address"] or "Main" in memo["office_address"]

    def test_integration_constraints(self):
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        assert len(memo["integration_constraints"]) > 0
        assert any("ServiceTrade" in c for c in memo["integration_constraints"])

    def test_required_fields_present(self):
        """All required account memo fields must be present."""
        memo = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        required_fields = [
            "account_id", "company_name", "business_hours", "office_address",
            "services_supported", "emergency_definition", "emergency_routing_rules",
            "non_emergency_routing_rules", "call_transfer_rules",
            "integration_constraints", "after_hours_flow_summary",
            "office_hours_flow_summary", "questions_or_unknowns", "notes"
        ]
        for field in required_fields:
            assert field in memo, f"Required field missing: {field}"


# ---------------------------------------------------------------------------
# Integration tests: generate_agent_spec
# ---------------------------------------------------------------------------

class TestGenerateAgentSpec:
    def test_spec_structure(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo, version="v1")
        assert spec["version"] == "v1"
        assert "system_prompt" in spec
        assert "key_variables" in spec
        assert "call_transfer_protocol" in spec
        assert "fallback_protocol" in spec

    def test_system_prompt_has_business_hours_flow(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        assert "BUSINESS HOURS CALL FLOW" in prompt

    def test_system_prompt_has_after_hours_flow(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        assert "AFTER-HOURS CALL FLOW" in prompt

    def test_system_prompt_has_greeting(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        assert "GREET" in prompt or "greet" in prompt.lower()

    def test_system_prompt_has_transfer_protocol(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        assert "TRANSFER" in prompt

    def test_system_prompt_has_fallback(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        assert "fallback" in prompt.lower() or "FALLBACK" in prompt

    def test_system_prompt_no_tool_mentions(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        # System prompt should NOT instruct the agent to say tool names to callers
        # (the instructions say not to mention tools)
        assert "function call" not in prompt.lower()
        assert "tool_invocation" not in prompt.lower()

    def test_no_voicemail_for_emergencies(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        fallback = spec.get("fallback_protocol", {})
        never_do = fallback.get("never_do", [])
        assert any("voicemail" in item.lower() for item in never_do)

    def test_collects_name_and_number(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        prompt = spec["system_prompt"]
        assert "name" in prompt.lower()
        assert "number" in prompt.lower() or "callback" in prompt.lower()

    def test_v2_label(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo, version="v2")
        assert spec["version"] == "v2"

    def test_key_variables_populated(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        kv = spec["key_variables"]
        assert "timezone" in kv
        assert "business_hours_days" in kv

    def test_tool_placeholders_present(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        tools = spec.get("tool_invocation_placeholders", [])
        tool_names = [t["tool"] for t in tools]
        assert "transfer_call" in tool_names
        assert "log_message" in tool_names

    def test_retell_import_instructions(self, sample_v1_memo):
        spec = generate_agent_spec(sample_v1_memo)
        instructions = spec.get("retell_import_instructions", {})
        assert len(instructions) > 0


# ---------------------------------------------------------------------------
# Integration tests: merge_memo / Pipeline B
# ---------------------------------------------------------------------------

class TestMergeMemo:
    def test_phone_numbers_added(self, sample_v1_memo):
        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        v2, conflicts = merge_memo(sample_v1_memo, onboarding_memo)
        routing = v2.get("emergency_routing_rules", {})
        # Onboarding has explicit phone numbers
        assert routing.get("primary_transfer_number") is not None

    def test_resolved_questions_removed(self, sample_v1_memo):
        """Questions that were open in v1 should be resolved in v2 if data is provided."""
        # v1 should have open questions about phone numbers
        assert len(sample_v1_memo.get("questions_or_unknowns", [])) > 0

        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        v2, _ = merge_memo(sample_v1_memo, onboarding_memo)

        # v2 should have fewer or equal questions
        assert len(v2.get("questions_or_unknowns", [])) <= len(
            sample_v1_memo.get("questions_or_unknowns", [])
        )

    def test_existing_data_preserved(self, sample_v1_memo):
        """v1 data that wasn't updated should still be present in v2."""
        company_name_v1 = sample_v1_memo["company_name"]
        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        v2, _ = merge_memo(sample_v1_memo, onboarding_memo)
        assert v2["company_name"] is not None

    def test_account_id_preserved(self, sample_v1_memo):
        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        v2, _ = merge_memo(sample_v1_memo, onboarding_memo)
        assert v2["account_id"] == sample_v1_memo["account_id"]

    def test_v2_version_set(self, sample_v1_memo):
        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        v2, _ = merge_memo(sample_v1_memo, onboarding_memo)
        assert v2.get("version") == "v2"

    def test_lists_merged_not_replaced(self, sample_v1_memo):
        """Lists should be merged (union), not replaced."""
        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        v2, _ = merge_memo(sample_v1_memo, onboarding_memo)
        # v2 services should include everything from v1 plus new items from onboarding
        v1_services = set(sample_v1_memo.get("services_supported", []))
        v2_services = set(v2.get("services_supported", []))
        assert v1_services.issubset(v2_services)

    def test_conflict_detected(self):
        """Conflicts should be detected when both v1 and onboarding have different values."""
        v1 = extract_rule_based(SAMPLE_DEMO_TRANSCRIPT)
        # Manually set a conflicting timezone
        v1["business_hours"]["timezone"] = "America/New_York"
        onboarding_memo = extract_rule_based(SAMPLE_ONBOARDING_TRANSCRIPT)
        onboarding_memo["business_hours"]["timezone"] = "America/Chicago"
        _, conflicts = merge_memo(v1, onboarding_memo)
        # Should detect timezone conflict
        assert any("timezone" in c.get("field", "") for c in conflicts)


# ---------------------------------------------------------------------------
# Integration tests: changelog
# ---------------------------------------------------------------------------

class TestChangelog:
    def test_changelog_generated(self, sample_v1_memo, sample_v2_memo):
        v1_spec = generate_agent_spec(sample_v1_memo, version="v1")
        v2_spec = generate_agent_spec(sample_v2_memo, version="v2")
        changelog = generate_changelog(
            v1_memo=sample_v1_memo,
            v2_memo=sample_v2_memo,
            v1_spec=v1_spec,
            v2_spec=v2_spec,
            conflicts=[],
            account_id="account_test",
        )
        assert "account_test" in changelog
        assert "v1" in changelog and "v2" in changelog

    def test_changelog_shows_changes(self, sample_v1_memo, sample_v2_memo):
        v1_spec = generate_agent_spec(sample_v1_memo, version="v1")
        v2_spec = generate_agent_spec(sample_v2_memo, version="v2")
        changelog = generate_changelog(
            v1_memo=sample_v1_memo,
            v2_memo=sample_v2_memo,
            v1_spec=v1_spec,
            v2_spec=v2_spec,
            conflicts=[],
            account_id="account_test",
        )
        assert "CHANGED" in changelog or "ADDED" in changelog

    def test_changelog_markdown_format(self, sample_v1_memo, sample_v2_memo):
        v1_spec = generate_agent_spec(sample_v1_memo, version="v1")
        v2_spec = generate_agent_spec(sample_v2_memo, version="v2")
        changelog = generate_changelog(
            v1_memo=sample_v1_memo,
            v2_memo=sample_v2_memo,
            v1_spec=v1_spec,
            v2_spec=v2_spec,
            conflicts=[],
            account_id="account_test",
        )
        assert changelog.startswith("#")  # Markdown heading


# ---------------------------------------------------------------------------
# Integration tests: deep_diff utility
# ---------------------------------------------------------------------------

class TestDeepDiff:
    def test_no_diff_identical(self):
        d = {"a": 1, "b": "x"}
        assert deep_diff(d, d) == []

    def test_detect_change(self):
        old = {"a": 1}
        new = {"a": 2}
        diffs = deep_diff(old, new)
        assert len(diffs) == 1
        assert diffs[0]["action"] == "changed"
        assert diffs[0]["old"] == 1
        assert diffs[0]["new"] == 2

    def test_detect_addition(self):
        old = {"a": 1}
        new = {"a": 1, "b": 2}
        diffs = deep_diff(old, new)
        assert any(d["action"] == "added" and d["path"] == "b" for d in diffs)

    def test_detect_removal(self):
        old = {"a": 1, "b": 2}
        new = {"a": 1}
        diffs = deep_diff(old, new)
        assert any(d["action"] == "removed" and d["path"] == "b" for d in diffs)

    def test_nested_diff(self):
        old = {"a": {"b": 1}}
        new = {"a": {"b": 2}}
        diffs = deep_diff(old, new)
        assert any(d["path"] == "a.b" for d in diffs)


# ---------------------------------------------------------------------------
# End-to-end tests: full pipeline
# ---------------------------------------------------------------------------

class TestEndToEnd:
    def test_full_pipeline_a(self, tmp_path):
        """Test that Pipeline A produces valid v1 artifacts."""
        # Write transcript to temp file
        transcript_file = tmp_path / "demo_test.txt"
        transcript_file.write_text(SAMPLE_DEMO_TRANSCRIPT)

        from scripts.pipeline_a import run_pipeline_a
        result = run_pipeline_a(
            transcript_path=str(transcript_file),
            account_id="account_test_e2e",
            prefer_llm=False,
        )

        assert result["account_id"] == "account_test_e2e"
        assert os.path.exists(result["memo_path"])
        assert os.path.exists(result["spec_path"])

        # Validate memo JSON structure
        with open(result["memo_path"]) as f:
            memo = json.load(f)
        assert memo["version"] == "v1"
        assert memo["company_name"] is not None

        # Validate spec JSON structure
        with open(result["spec_path"]) as f:
            spec = json.load(f)
        assert spec["version"] == "v1"
        assert "system_prompt" in spec

    def test_full_pipeline_b(self, tmp_path):
        """Test that Pipeline B produces valid v2 artifacts and changelog."""
        # First run Pipeline A
        demo_file = tmp_path / "demo_test.txt"
        demo_file.write_text(SAMPLE_DEMO_TRANSCRIPT)

        onboarding_file = tmp_path / "onboarding_test.txt"
        onboarding_file.write_text(SAMPLE_ONBOARDING_TRANSCRIPT)

        from scripts.pipeline_a import run_pipeline_a
        from scripts.pipeline_b import run_pipeline_b

        run_pipeline_a(
            transcript_path=str(demo_file),
            account_id="account_e2e_full",
            prefer_llm=False,
        )

        result = run_pipeline_b(
            onboarding_transcript_path=str(onboarding_file),
            account_id="account_e2e_full",
            prefer_llm=False,
        )

        assert os.path.exists(result["v2_memo_path"])
        assert os.path.exists(result["v2_spec_path"])
        assert os.path.exists(result["changelog_path"])
        assert os.path.exists(result["diff_path"])

        with open(result["v2_memo_path"]) as f:
            v2_memo = json.load(f)
        assert v2_memo["version"] == "v2"

        with open(result["v2_spec_path"]) as f:
            v2_spec = json.load(f)
        assert v2_spec["version"] == "v2"

        with open(result["changelog_path"]) as f:
            changelog = f.read()
        assert "account_e2e_full" in changelog

    def test_idempotent_pipeline_a(self, tmp_path):
        """Running Pipeline A twice should produce the same output (idempotent)."""
        demo_file = tmp_path / "demo_test.txt"
        demo_file.write_text(SAMPLE_DEMO_TRANSCRIPT)

        from scripts.pipeline_a import run_pipeline_a

        result1 = run_pipeline_a(
            transcript_path=str(demo_file),
            account_id="account_idempotent",
            prefer_llm=False,
        )
        result2 = run_pipeline_a(
            transcript_path=str(demo_file),
            account_id="account_idempotent",
            prefer_llm=False,
        )

        # Both runs should produce structurally equivalent memos
        with open(result1["memo_path"]) as f:
            memo1 = json.load(f)
        with open(result2["memo_path"]) as f:
            memo2 = json.load(f)

        # Strip timestamps for comparison
        for m in (memo1, memo2):
            m.pop("extracted_at", None)

        assert memo1 == memo2

    def test_pipeline_b_requires_v1(self, tmp_path):
        """Pipeline B should fail gracefully if v1 doesn't exist."""
        onboarding_file = tmp_path / "onboarding_test.txt"
        onboarding_file.write_text(SAMPLE_ONBOARDING_TRANSCRIPT)

        from scripts.pipeline_b import run_pipeline_b

        with pytest.raises(FileNotFoundError):
            run_pipeline_b(
                onboarding_transcript_path=str(onboarding_file),
                account_id="account_nonexistent_xyz",
                prefer_llm=False,
            )

    def test_sample_outputs_exist(self):
        """Verify that sample outputs were generated by the batch run."""
        repo_root = Path(__file__).parent.parent
        outputs_root = repo_root / "outputs" / "accounts"

        if not outputs_root.exists():
            pytest.skip("Sample outputs not generated yet — run batch_run.py first")

        for i in range(1, 6):
            account_id = f"account_00{i}"
            v1_dir = outputs_root / account_id / "v1"
            v2_dir = outputs_root / account_id / "v2"

            assert (v1_dir / "memo.json").exists(), f"Missing v1 memo for {account_id}"
            assert (v1_dir / "agent_spec.json").exists(), f"Missing v1 spec for {account_id}"
            assert (v2_dir / "memo.json").exists(), f"Missing v2 memo for {account_id}"
            assert (v2_dir / "agent_spec.json").exists(), f"Missing v2 spec for {account_id}"
            assert (outputs_root / account_id / "changelog.md").exists(), f"Missing changelog for {account_id}"

    def test_sample_v1_no_phone_numbers(self):
        """v1 memos from demo calls should have null phone numbers (not hallucinated)."""
        repo_root = Path(__file__).parent.parent
        outputs_root = repo_root / "outputs" / "accounts"

        if not outputs_root.exists():
            pytest.skip("Sample outputs not generated yet")

        for i in range(1, 6):
            account_id = f"account_00{i}"
            memo_path = outputs_root / account_id / "v1" / "memo.json"
            if not memo_path.exists():
                continue
            with open(memo_path) as f:
                memo = json.load(f)
            routing = memo.get("emergency_routing_rules", {})
            # Demo transcripts in our dataset don't include explicit phone numbers
            # So v1 should flag them as unknowns, not invent them
            questions = memo.get("questions_or_unknowns", [])
            assert any("phone" in q.lower() or "number" in q.lower() for q in questions), \
                f"{account_id}/v1: phone number not flagged as unknown"

    def test_sample_v2_has_phone_numbers(self):
        """v2 memos should have phone numbers filled in from onboarding."""
        repo_root = Path(__file__).parent.parent
        outputs_root = repo_root / "outputs" / "accounts"

        if not outputs_root.exists():
            pytest.skip("Sample outputs not generated yet")

        for i in range(1, 6):
            account_id = f"account_00{i}"
            memo_path = outputs_root / account_id / "v2" / "memo.json"
            if not memo_path.exists():
                continue
            with open(memo_path) as f:
                memo = json.load(f)
            routing = memo.get("emergency_routing_rules", {})
            assert routing.get("primary_transfer_number") is not None, \
                f"{account_id}/v2: primary phone number still null after onboarding"
