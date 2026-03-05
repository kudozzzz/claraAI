"""
extract_memo.py — Extract a structured Account Memo JSON from a call transcript.

Supports two modes:
  • LLM mode   — uses Groq (free tier) or local Ollama for extraction
  • Rule-based — pure regex + heuristic extraction (zero-cost, always works)

The LLM mode is more accurate for messy real-world transcripts; rule-based is
deterministic and always available.
"""

import re
import json
from typing import Any

from scripts.utils import get_logger, now_iso
from scripts.llm_client import call_llm, is_llm_available, BACKEND

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

EXTRACTION_SYSTEM_PROMPT = """You are a business operations analyst. Your job is to extract 
structured configuration data from call transcripts for service trade companies.

Extract ONLY what is explicitly stated. Do NOT invent, assume, or hallucinate values.
If a field is not mentioned, use null or an empty list.
If something is unclear or missing, add it to questions_or_unknowns.

Return ONLY valid JSON — no markdown, no explanation, just the JSON object."""

EXTRACTION_USER_PROMPT = """Extract the following fields from this transcript and return as JSON:

{
  "account_id": "string — use the account ID from the transcript header if present",
  "company_name": "string",
  "business_hours": {
    "days": ["Monday", "Tuesday", ...],
    "start": "HH:MM (24h)",
    "end": "HH:MM (24h)",
    "timezone": "IANA timezone string e.g. America/Denver"
  },
  "office_address": "string or null",
  "services_supported": ["list of services mentioned"],
  "emergency_definition": ["list of conditions that qualify as emergencies"],
  "emergency_routing_rules": {
    "primary_transfer_number": "phone number or null",
    "secondary_transfer_number": "phone number or null",
    "transfer_timeout_seconds": number or null,
    "max_attempts": number or null,
    "fallback_message": "what to tell caller if all transfers fail"
  },
  "non_emergency_routing_rules": {
    "action": "take_message | transfer | voicemail",
    "transfer_number": "phone number or null",
    "callback_promise": "e.g. next business day",
    "info_to_collect": ["name", "number", ...]
  },
  "call_transfer_rules": {
    "business_hours_transfer_number": "phone number or null",
    "transfer_timeout_seconds": number or null,
    "max_retries": number or null,
    "busy_fallback": "take_message | voicemail | transfer_to_backup"
  },
  "integration_constraints": ["list of software constraints e.g. never mention ServiceTrade"],
  "after_hours_flow_summary": "1-2 sentence summary of after-hours call flow",
  "office_hours_flow_summary": "1-2 sentence summary of business hours call flow",
  "questions_or_unknowns": ["list of fields that are missing or unclear"],
  "notes": "short free-text notes about anything unusual"
}

TRANSCRIPT:
"""


def extract_with_llm(transcript: str) -> dict:
    """Use LLM to extract structured memo from transcript."""
    logger.info("Attempting LLM extraction (backend=%s)", BACKEND)
    response = call_llm(EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT + transcript)

    if response == "RULE_BASED_FALLBACK":
        logger.info("LLM unavailable — using rule-based extraction")
        return extract_rule_based(transcript)

    # Strip markdown code fences if present
    response = response.strip()
    if response.startswith("```"):
        response = re.sub(r"^```[a-zA-Z]*\n?", "", response)
        response = re.sub(r"\n?```$", "", response)

    try:
        return json.loads(response)
    except json.JSONDecodeError as exc:
        logger.warning("LLM returned invalid JSON (%s) — falling back to rule-based", exc)
        return extract_rule_based(transcript)


# ---------------------------------------------------------------------------
# Rule-based extraction helpers
# ---------------------------------------------------------------------------

# Day name normaliser
_DAY_MAP = {
    "monday": "Monday", "mon": "Monday",
    "tuesday": "Tuesday", "tue": "Tuesday", "tues": "Tuesday",
    "wednesday": "Wednesday", "wed": "Wednesday",
    "thursday": "Thursday", "thu": "Thursday", "thur": "Thursday", "thurs": "Thursday",
    "friday": "Friday", "fri": "Friday",
    "saturday": "Saturday", "sat": "Saturday",
    "sunday": "Sunday", "sun": "Sunday",
}

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
_WEEKEND = ["Saturday", "Sunday"]
_ALL_DAYS = _WEEKDAYS + _WEEKEND


def _normalise_day(s: str) -> str:
    return _DAY_MAP.get(s.lower().strip(), s.strip().capitalize())


def _expand_day_range(start: str, end: str) -> list:
    """Expand 'Monday through Friday' to ['Monday', ..., 'Friday']."""
    start = _normalise_day(start)
    end = _normalise_day(end)
    if start not in _ALL_DAYS or end not in _ALL_DAYS:
        return [start, end]
    si, ei = _ALL_DAYS.index(start), _ALL_DAYS.index(end)
    return _ALL_DAYS[si:ei + 1]


def _parse_time(s: str) -> str | None:
    """Convert various time formats to HH:MM 24-hour."""
    s = s.strip().lower().replace(".", ":").replace(" ", "")
    # already 24-hour
    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"

    # 12-hour: 8am, 8:00am, 8:00 am, 8 am
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?(am|pm)$", s)
    if m:
        h = int(m.group(1))
        mins = m.group(2) or "00"
        ampm = m.group(3)
        if ampm == "pm" and h != 12:
            h += 12
        if ampm == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mins}"
    return None


def _extract_business_hours(text: str) -> dict:
    """Heuristically extract business hours from transcript text."""
    hours = {"days": [], "start": None, "end": None, "timezone": None}

    # Timezone
    tz_patterns = [
        # More specific patterns first to avoid MST matching America/Denver instead of America/Phoenix
        (r"America/Phoenix|Arizona(?:\s+Time)?(?:\s+timezone)?|AZ\s+Time|Phoenix,\s*AZ", "America/Phoenix"),
        (r"America/Denver|Mountain Time|MT\b|MST\b|MDT\b|Denver,\s*CO", "America/Denver"),
        (r"America/Chicago|Central Time|CT\b|CST\b|CDT\b|Chicago,\s*IL|Dallas,\s*TX", "America/Chicago"),
        (r"America/New_York|Eastern Time|ET\b|EST\b|EDT\b", "America/New_York"),
        (r"America/Los_Angeles|Pacific Time|PT\b|PST\b|PDT\b|Seattle,\s*WA|Los Angeles", "America/Los_Angeles"),
    ]
    for pattern, tz in tz_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            hours["timezone"] = tz
            break

    # Day range: "Monday through Friday" or "Monday to Friday" or "Monday - Friday"
    day_range = re.search(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s+"
        r"(?:through|to|–|-)\s+"
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)",
        text, re.IGNORECASE
    )
    if day_range:
        hours["days"] = _expand_day_range(day_range.group(1), day_range.group(2))
    elif re.search(r"Monday\s+through\s+Friday|Mon[-\s]?Fri|weekdays", text, re.IGNORECASE):
        hours["days"] = _WEEKDAYS[:]
    elif re.search(r"7 days|every day|daily", text, re.IGNORECASE):
        hours["days"] = _ALL_DAYS[:]

    # Also check for additional individual days (e.g. "and Saturday")
    if hours["days"] and re.search(r"\bSaturday\b", text, re.IGNORECASE):
        if "Saturday" not in hours["days"]:
            hours["days"].append("Saturday")

    # Time range: "8 AM to 5 PM" or "7:30 AM to 5:30 PM" etc.
    time_range = re.search(
        r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))\s*(?:to|–|-|through)\s*"
        r"(\d{1,2}(?::\d{2})?\s*(?:AM|PM|am|pm))",
        text, re.IGNORECASE
    )
    if time_range:
        hours["start"] = _parse_time(time_range.group(1))
        hours["end"] = _parse_time(time_range.group(2))

    return hours


def _extract_phone_numbers(text: str) -> list:
    """Extract all phone number patterns from text."""
    pattern = r"\b(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b"
    return re.findall(pattern, text)


def _extract_company_name(text: str, account_id: str = "") -> str:
    """Try to extract company name from transcript header or first mention."""
    # From header line: "— CompanyName" or "TRANSCRIPT — CompanyName"
    m = re.search(r"(?:TRANSCRIPT|CALL)[^\n]*?—\s*(.+?)(?:\n|$)", text, re.IGNORECASE)
    if m:
        name = m.group(1).strip()
        # Remove trailing metadata
        name = re.sub(r"\s*Account ID.*", "", name, flags=re.IGNORECASE)
        if name:
            return name

    # "We're <Company Name>" or "We are <Company Name>"
    m = re.search(r"(?:We(?:'re| are)\s+)([A-Z][A-Za-z\s&]+?(?:Inc\.|LLC|Co\.|Corp\.|Services|Systems|Solutions|Protection|Electric(?:al)?|HVAC|Security)?)", text)
    if m:
        return m.group(1).strip()

    return account_id.replace("_", " ").title() if account_id else "Unknown Company"


def _extract_address(text: str) -> str | None:
    """Extract a street address from transcript text."""
    # Pattern: number + street + optional suite + city + state + zip
    patterns = [
        # Full address with city, state, zip
        r"\b(\d{3,5}\s+(?:[A-Za-z]+\s+){1,5}(?:Drive|Ave(?:nue)?|Road|Street|Blvd|Boulevard|"
        r"Way|Lane|Court|Place|Suite|Plaza|Circle|Parkway|Highway|Dr|Ave|Rd|St)\b"
        r"(?:,?\s*Suite\s+\w+)?"
        r"(?:,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5})?)",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_account_id(text: str) -> str | None:
    """Extract account ID from transcript header."""
    m = re.search(r"Account\s+ID:\s*([\w_-]+)", text, re.IGNORECASE)
    return m.group(1) if m else None


def _extract_services(text: str) -> list:
    """Extract list of services mentioned."""
    service_keywords = [
        "fire sprinkler", "sprinkler system", "fire suppression", "fire alarm",
        "carbon monoxide", "CO detector", "smoke detector",
        "HVAC", "heating", "cooling", "ventilation", "air conditioning", "refrigeration",
        "electrical", "panel upgrade", "generator", "power system",
        "burglar alarm", "access control", "video surveillance", "security system",
        "inspection scheduling", "annual inspection", "certification",
        "kitchen hood", "hood suppression",
    ]
    found = []
    for kw in service_keywords:
        if re.search(kw, text, re.IGNORECASE):
            found.append(kw.title())
    return found


def _extract_emergency_triggers(text: str) -> list:
    """Extract emergency trigger definitions as clean, human-readable strings."""

    # Map of (regex_pattern, clean_label) pairs.
    # Pattern is used to detect presence; clean_label is what we store.
    emergency_pattern_map = [
        (r"active sprinkler discharge", "Active sprinkler discharge"),
        (r"fire suppression (?:system )?discharge", "Fire suppression system discharge"),
        (r"fire suppression (?:system )?activation", "Fire suppression system activation"),
        (r"fire alarm (?:panel )?activation", "Fire alarm panel activation"),
        (r"fire alarm (?:panel )?trouble", "Fire alarm panel trouble signal"),
        (r"fire alarm.*(?:going off|triggered|activated)", "Fire alarm actively going off"),
        (r"kitchen (?:hood|suppression) (?:discharge|activation)", "Kitchen hood/suppression discharge or activation"),
        (r"CO detector activation|carbon monoxide alarm", "CO detector / carbon monoxide alarm activation"),
        (r"smoke detector activation.*(?:real smoke|actual smoke)", "Smoke detector activation (confirmed real smoke)"),
        (r"no (?:A/C|AC|air conditioning).*(?:extreme heat|over 110|senior|small kids)", "No A/C in extreme heat (residential — senior citizens or families with small children)"),
        (r"(?:extreme heat|over 110).*no (?:A/C|AC|cooling)", "No cooling during extreme heat conditions"),
        (r"commercial.*HVAC.*(?:failure|down|fail)", "Commercial HVAC complete failure"),
        (r"(?:heat(?:ing)?).*completely.*(?:out|fail)|(?:heat(?:ing)?).*(?:out|fail).*below 32", "Heating system completely out (especially below 32°F)"),
        (r"below 32 degrees|freezing.*no heat", "No heat with outdoor temperature below 32°F"),
        (r"refrigeration failure.*(?:restaurant|food)", "Refrigeration failure at restaurant or food storage facility"),
        (r"medical facility.*(?:HVAC|cooling|heating)", "HVAC/cooling/heating failure at medical facility"),
        (r"total power failure|building(?:-wide)? power (?:failure|outage)|whole building.*power", "Total or building-wide power failure"),
        (r"sparking|burning smell|electrical fire risk", "Sparking, burning smell, or electrical fire risk"),
        (r"electric(?:al)? shock|energized equipment.*(?:safety|malfunction)", "Electric shock or energized equipment malfunction with safety risk"),
        (r"generator failure.*(?:hospital|data center|critical facility)", "Generator failure at critical facility (hospital, data center)"),
        (r"critical facility.*generator", "Generator failure at a critical facility"),
        (r"data center.*suppression discharge", "Suppression system discharge at data center or server room"),
        # Security / alarm emergencies
        (r"alarm.*(?:going off|activated|triggered).*(?:not.*false|unconfirmed|haven't confirmed)", "Active alarm activation not confirmed as false alarm"),
        (r"alarm (?:goes? off|went off|is going off|is active)", "Active alarm going off"),
        (r"intruder.*(?:video|camera)|(?:video|camera).*intruder|(?:someone|people).*shouldn't.*(?:video|camera)", "Intruder visible on video/camera surveillance"),
        (r"physical (?:damage|break).*security equipment|security equipment.*(?:damaged|destroyed)", "Physical damage to security equipment suggesting break-in attempt"),
        (r"fire alarm.*monitored site", "Fire alarm activation at a monitored site"),
        (r"water damage", "Active water damage"),
        (r"active alarm.*not.*false alarm|alarm.*not.*false", "Active alarm not confirmed as false alarm"),
    ]

    found = []
    seen_labels = set()

    for pattern, label in emergency_pattern_map:
        if re.search(pattern, text, re.IGNORECASE) and label not in seen_labels:
            found.append(label)
            seen_labels.add(label)

    return found


def _extract_integration_constraints(text: str) -> list:
    """Extract software/integration constraints."""
    constraints = []

    if re.search(r"ServiceTrade", text, re.IGNORECASE):
        # Check for "never mention" constraint
        if re.search(r"(?:never|don't|should not|must not|shouldn't|not mention|never mention).*ServiceTrade|ServiceTrade.*(?:never|don't|should not|must not|shouldn't|not mention|internal only|internal use)", text, re.IGNORECASE):
            constraints.append("Never mention ServiceTrade to callers — internal use only")
        elif re.search(r"ServiceTrade", text, re.IGNORECASE):
            # Default: any mention implies it's internal
            constraints.append("ServiceTrade is internal only — do not reference to callers")
        if re.search(r"sprinkler.*jobs.*ServiceTrade|ServiceTrade.*sprinkler.*jobs|never create.*sprinkler.*ServiceTrade", text, re.IGNORECASE):
            if "Do not create sprinkler jobs in ServiceTrade from field techs" not in constraints:
                constraints.append("Do not create sprinkler jobs in ServiceTrade from field techs")
        if re.search(r"kitchen hood.*ServiceTrade|ServiceTrade.*kitchen|hood.*jobs.*ServiceTrade", text, re.IGNORECASE):
            if "Do not create kitchen hood suppression jobs in ServiceTrade from field techs" not in constraints:
                constraints.append("Do not create kitchen hood suppression jobs in ServiceTrade from field techs")

    if re.search(r"ServiceTitan", text, re.IGNORECASE):
        constraints.append("ServiceTitan is internal only — Clara should not reference or access it")

    if re.search(r"FieldEdge", text, re.IGNORECASE):
        constraints.append("FieldEdge is internal only — Clara should not reference or create tickets")

    if re.search(r"Zendesk", text, re.IGNORECASE):
        constraints.append("Never create or look up Zendesk tickets — internal use only")

    if re.search(r"Immix", text, re.IGNORECASE):
        constraints.append("Immix central station software is internal — not referenced to callers")

    return constraints


def _build_questions_or_unknowns(memo: dict) -> list:
    """Identify fields that are missing or null."""
    questions = []

    hours = memo.get("business_hours", {})
    if not hours.get("days"):
        questions.append("Business hours days are not specified")
    if not hours.get("start") or not hours.get("end"):
        questions.append("Business hours start/end times are not confirmed")
    if not hours.get("timezone"):
        questions.append("Timezone is not specified")

    if not memo.get("office_address"):
        questions.append("Office address not mentioned in transcript")

    routing = memo.get("emergency_routing_rules", {})
    if not routing.get("primary_transfer_number"):
        questions.append("Emergency on-call primary phone number not specified")
    if not routing.get("transfer_timeout_seconds"):
        questions.append("Transfer timeout/retry settings not specified")

    if not memo.get("emergency_definition"):
        questions.append("Emergency trigger definitions are vague or not specified")

    if not memo.get("services_supported"):
        questions.append("List of supported services not clearly stated")

    transfer = memo.get("call_transfer_rules", {})
    if not transfer.get("business_hours_transfer_number"):
        questions.append("Business hours main transfer number not specified")

    return questions


# ---------------------------------------------------------------------------
# Main rule-based extraction
# ---------------------------------------------------------------------------

def extract_rule_based(transcript: str) -> dict:
    """
    Pure rule-based extraction of account memo from transcript text.
    Returns a structured dict matching the AccountMemo schema.
    """
    logger.info("Running rule-based extraction")

    account_id = _extract_account_id(transcript) or "unknown"
    company_name = _extract_company_name(transcript, account_id)
    hours = _extract_business_hours(transcript)
    address = _extract_address(transcript)
    phones = _extract_phone_numbers(transcript)
    services = _extract_services(transcript)
    emergency_triggers = _extract_emergency_triggers(transcript)
    constraints = _extract_integration_constraints(transcript)

    # Best-effort phone number assignment
    primary_emergency = phones[0] if len(phones) > 0 else None
    secondary_emergency = phones[1] if len(phones) > 1 else None
    biz_hours_number = phones[-1] if phones else None

    # Transfer timeout heuristic (look for explicit mention)
    timeout_match = re.search(r"(\d+)\s+seconds", transcript, re.IGNORECASE)
    timeout = int(timeout_match.group(1)) if timeout_match else None

    # Fallback callback promise
    callback_match = re.search(r"(?:call(?:back)? (?:within|in)|someone will call)\s+(\d+\s+(?:minutes?|hours?|days?))", transcript, re.IGNORECASE)
    fallback_msg = f"We will call you back within {callback_match.group(1)}" if callback_match else "We will have someone call you back shortly"

    # Non-emergency info to collect
    non_emerg_info = ["name", "callback_number"]
    if re.search(r"address|site address", transcript, re.IGNORECASE):
        non_emerg_info.append("site_address")
    if re.search(r"description|brief description|type of (?:issue|problem|request)", transcript, re.IGNORECASE):
        non_emerg_info.append("brief_description")
    if re.search(r"residential|commercial|industrial", transcript, re.IGNORECASE):
        non_emerg_info.append("residential_or_commercial")
    if re.search(r"model|equipment model", transcript, re.IGNORECASE):
        non_emerg_info.append("equipment_model")
    if re.search(r"company name", transcript, re.IGNORECASE):
        non_emerg_info.append("company_name")
    if re.search(r"which (?:city|market|region|location)", transcript, re.IGNORECASE):
        non_emerg_info.append("location_market")

    # After-hours / business-hours summaries
    after_hours_summary = (
        "After hours, Clara greets the caller, determines whether the call is an emergency, "
        "collects caller name, callback number, and address for emergencies, then attempts transfer "
        "to on-call. If transfer fails, informs caller of callback within the committed timeframe."
    )
    office_hours_summary = (
        "During business hours, Clara greets the caller, collects name and reason for call, "
        "then transfers to the main office line."
    )

    memo: dict[str, Any] = {
        "account_id": account_id,
        "company_name": company_name,
        "business_hours": hours,
        "office_address": address,
        "services_supported": services,
        "emergency_definition": emergency_triggers,
        "emergency_routing_rules": {
            "primary_transfer_number": primary_emergency,
            "secondary_transfer_number": secondary_emergency,
            "transfer_timeout_seconds": timeout,
            "max_attempts": 2,
            "fallback_message": fallback_msg,
        },
        "non_emergency_routing_rules": {
            "action": "take_message",
            "transfer_number": None,
            "callback_promise": "next business day",
            "info_to_collect": non_emerg_info,
        },
        "call_transfer_rules": {
            "business_hours_transfer_number": biz_hours_number,
            "transfer_timeout_seconds": timeout,
            "max_retries": 1,
            "busy_fallback": "take_message",
        },
        "integration_constraints": constraints,
        "after_hours_flow_summary": after_hours_summary,
        "office_hours_flow_summary": office_hours_summary,
        "questions_or_unknowns": [],
        "notes": f"Extracted via rule-based engine from transcript. Source: demo call.",
    }

    memo["questions_or_unknowns"] = _build_questions_or_unknowns(memo)

    return memo


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def extract_memo(transcript: str, prefer_llm: bool = True) -> dict:
    """
    Extract a structured account memo from a call transcript.

    Args:
        transcript: Raw transcript text.
        prefer_llm: If True, attempt LLM extraction first with rule-based fallback.
                    If False, always use rule-based extraction.

    Returns:
        Account memo dict.
    """
    if prefer_llm and is_llm_available():
        return extract_with_llm(transcript)
    return extract_rule_based(transcript)
