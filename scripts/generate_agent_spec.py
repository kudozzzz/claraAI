from typing import Any
from scripts.utils import get_logger, now_iso

logger = get_logger(__name__)



# System prompt template

def _build_system_prompt(memo: dict) -> str:
    """Generate the Clara agent system prompt from memo data."""
    company = memo.get("company_name", "the company")
    bh = memo.get("business_hours", {})
    days = bh.get("days", [])
    start = bh.get("start", "N/A")
    end = bh.get("end", "N/A")
    tz = bh.get("timezone", "local time")
    address = memo.get("office_address") or "contact us during business hours for address"

    emergency_list = memo.get("emergency_definition", [])
    emergency_text = "\n".join(f"  - {e}" for e in emergency_list) if emergency_list else "  - Active emergency as described by caller"

    routing = memo.get("emergency_routing_rules", {})
    primary_num = routing.get("primary_transfer_number", "[on-call number]")
    secondary_num = routing.get("secondary_transfer_number")
    timeout = routing.get("transfer_timeout_seconds", 30)
    fallback_msg = routing.get("fallback_message", "We will have someone call you back shortly")
    max_attempts = routing.get("max_attempts", 2)

    transfer_rules = memo.get("call_transfer_rules", {})
    biz_transfer_num = transfer_rules.get("business_hours_transfer_number", "[main office number]")
    biz_timeout = transfer_rules.get("transfer_timeout_seconds", 30)
    busy_fallback = transfer_rules.get("busy_fallback", "take_message")

    non_emerg = memo.get("non_emergency_routing_rules", {})
    callback_promise = non_emerg.get("callback_promise", "the next business day")
    collect_fields = non_emerg.get("info_to_collect", ["name", "callback_number"])
    collect_text = ", ".join(collect_fields)

    constraints = memo.get("integration_constraints", [])
    constraint_text = "\n".join(f"  - {c}" for c in constraints) if constraints else "  - None specified"

    days_str = ", ".join(days) if days else "Monday through Friday"

    # Busy fallback sentence
    if busy_fallback == "take_message":
        busy_fallback_sentence = "If the transfer is unsuccessful or the line is busy, politely take a message and inform the caller someone will call them back within 2 hours."
    elif busy_fallback == "voicemail":
        busy_fallback_sentence = "If the transfer is unsuccessful, transfer the caller to voicemail and let them know they can leave a message."
    else:
        busy_fallback_sentence = "If the transfer is unsuccessful, take a message and inform the caller someone will follow up."

    secondary_transfer_block = ""
    if secondary_num:
        secondary_transfer_block = f"""
  - If primary transfer to {primary_num} is not answered within {timeout} seconds:
    → Attempt transfer to secondary on-call: {secondary_num}
  - If secondary also does not answer within {timeout} seconds:
    → DO NOT transfer to voicemail.
    → Tell the caller: "{fallback_msg}. I have your information and our team will call you back."
    → Log the call as a PRIORITY emergency."""
    else:
        secondary_transfer_block = f"""
  - If transfer to {primary_num} is not answered within {timeout} seconds:
    → DO NOT transfer to voicemail.
    → Tell the caller: "{fallback_msg}. I have your information and our team will call you back."
    → Log the call as a PRIORITY emergency."""

    prompt = f"""You are Clara, the AI receptionist for {company}.
You are helpful, calm, professional, and empathetic — especially during stressful situations.
You handle incoming calls and route them appropriately.

CRITICAL RULES:
- Do NOT mention any internal software tools or systems (e.g., ServiceTrade, ServiceTitan, FieldEdge, Zendesk) to callers.
- Do NOT ask for more information than is needed for routing.
- Do NOT promise specific response times unless confirmed: use only stated commitments.
- Do NOT send emergency calls to voicemail under any circumstance.
- ALWAYS collect caller name and callback number for any message.

BUSINESS HOURS:
- Days: {days_str}
- Hours: {start} to {end} ({tz})
- Office address: {address}

SERVICES PROVIDED:
{chr(10).join(f"  - {s}" for s in memo.get("services_supported", ["General service"]))}

EMERGENCY DEFINITIONS — these situations require IMMEDIATE routing:
{emergency_text}

INTEGRATION / TOOL CONSTRAINTS:
{constraint_text}

BUSINESS HOURS CALL FLOW

When the call is received during business hours ({start}–{end}, {days_str}):

1. GREET:
   "Thank you for calling {company}. This is Clara. How can I help you today?"

2. UNDERSTAND PURPOSE:
   Listen to the caller's reason for calling.
   If they mention an emergency situation (see EMERGENCY DEFINITIONS above), switch to EMERGENCY FLOW.

3. COLLECT INFORMATION:
   Ask for their name: "May I have your name please?"
   Ask for their callback number: "And the best number to reach you?"

4. TRANSFER:
   Say: "Let me connect you with our team now."
   [TRANSFER to {biz_transfer_num}]
   Transfer timeout: {biz_timeout} seconds.

5. TRANSFER FAIL PROTOCOL:
   {busy_fallback_sentence}

6. CLOSE:
   "Is there anything else I can help you with?"
   If no: "Thank you for calling {company}. Have a great day!"


AFTER-HOURS CALL FLOW

When the call is received outside of business hours:

1. GREET:
   "Thank you for calling {company}. You've reached our after-hours line. This is Clara. How can I help you?"

2. DETERMINE PURPOSE:
   Listen to the caller's reason for calling.

3. ASSESS EMERGENCY:
   Ask: "Is this an emergency situation?"
   
   EMERGENCY situations include:
{emergency_text}

4A. IF EMERGENCY:
   Say: "I understand — let me get your information right away so we can help you immediately."
   
   Collect in this order (do not skip):
   a) "What is your name?"
   b) "What is the best callback number for you?"
   c) "What is the address of the site or location?"
   d) "Can you briefly describe what's happening?"
   
   Then say: "I'm connecting you to our on-call team right now."
   [ATTEMPT TRANSFER to {primary_num}]
{secondary_transfer_block}

4B. IF NON-EMERGENCY:
   Say: "I understand. Our office is open {days_str} from {start} to {end} {tz}. I'll make sure the right person calls you back {callback_promise}."
   
   Collect:
   - Name
   - Callback number
   - {collect_text}
   
   Say: "I've noted your information. Someone from our team will follow up with you {callback_promise}."

5. CLOSE:
   "Is there anything else I can help you with?"
   If no: "Thank you for calling {company}. Someone will be in touch soon."


EMERGENCY CALL TRANSFER PROTOCOL

- Attempt transfer to primary on-call: {primary_num}
  Timeout: {timeout} seconds, max {max_attempts} attempts
{secondary_transfer_block}

AFTER FAILED TRANSFER — FALLBACK PROTOCOL:
1. Do NOT hang up without giving the caller a commitment.
2. Confirm you have their name, callback number, and site address.
3. Say: "{fallback_msg}. Your information has been recorded and our team has been notified."
4. Ask: "Is there anything else I can do for you right now?"

NEVER:
- Suggest the caller call back later
- Transfer emergencies to voicemail
- Leave a caller without a human commitment when transfers fail
"""

    return prompt.strip()



# Agent spec generator


def generate_agent_spec(memo: dict, version: str = "v1") -> dict:
    """
    Generate a Retell Agent Draft Spec from an account memo.

    Args:
        memo: Structured account memo dict.
        version: "v1" (from demo) or "v2" (after onboarding).

    Returns:
        Retell agent spec dict.
    """
    logger.info("Generating agent spec v=%s for account=%s", version, memo.get("account_id"))

    bh = memo.get("business_hours", {})
    routing = memo.get("emergency_routing_rules", {})
    transfer = memo.get("call_transfer_rules", {})

    system_prompt = _build_system_prompt(memo)

    spec: dict[str, Any] = {
        "agent_name": f"Clara — {memo.get('company_name', 'Service Company')}",
        "version": version,
        "created_at": now_iso(),
        "voice_style": {
            "provider": "retell",
            "voice_id": "11labs-Adriana",
            "tone": "warm, professional, empathetic",
            "language": "en-US",
            "speaking_rate": 1.0,
        },
        "system_prompt": system_prompt,
        "key_variables": {
            "timezone": bh.get("timezone", "America/Chicago"),
            "business_hours_days": bh.get("days", []),
            "business_hours_start": bh.get("start"),
            "business_hours_end": bh.get("end"),
            "office_address": memo.get("office_address"),
            "company_name": memo.get("company_name"),
            "emergency_routing_primary": routing.get("primary_transfer_number"),
            "emergency_routing_secondary": routing.get("secondary_transfer_number"),
            "emergency_transfer_timeout_seconds": routing.get("transfer_timeout_seconds", 30),
            "business_hours_transfer_number": transfer.get("business_hours_transfer_number"),
            "emergency_callback_commitment": routing.get("fallback_message"),
        },
        "tool_invocation_placeholders": [
            {
                "tool": "transfer_call",
                "description": "Transfer the active call to the specified phone number",
                "parameters": {
                    "destination_number": "string — the phone number to transfer to",
                    "transfer_reason": "string — brief reason for transfer (for logging)"
                },
                "note": "Do NOT mention this tool to the caller"
            },
            {
                "tool": "log_message",
                "description": "Log caller information and message for follow-up",
                "parameters": {
                    "caller_name": "string",
                    "caller_number": "string",
                    "caller_address": "string or null",
                    "message": "string — caller's message",
                    "priority": "emergency | high | normal",
                    "call_type": "emergency | non_emergency | unknown"
                },
                "note": "Do NOT mention this tool to the caller"
            },
            {
                "tool": "check_business_hours",
                "description": "Check if current time is within business hours",
                "parameters": {
                    "timezone": "string — IANA timezone",
                    "business_hours_start": "string — HH:MM",
                    "business_hours_end": "string — HH:MM",
                    "business_days": "list of day names"
                },
                "note": "Do NOT mention this tool to the caller"
            }
        ],
        "call_transfer_protocol": {
            "business_hours": {
                "transfer_number": transfer.get("business_hours_transfer_number"),
                "timeout_seconds": transfer.get("transfer_timeout_seconds", 30),
                "max_retries": transfer.get("max_retries", 1),
                "on_failure": transfer.get("busy_fallback", "take_message"),
            },
            "emergency_after_hours": {
                "primary_transfer_number": routing.get("primary_transfer_number"),
                "secondary_transfer_number": routing.get("secondary_transfer_number"),
                "timeout_seconds": routing.get("transfer_timeout_seconds", 30),
                "max_attempts": routing.get("max_attempts", 2),
                "fallback_action": "log_priority_message_and_commit_callback",
            }
        },
        "fallback_protocol": {
            "all_transfers_failed": {
                "action": "take_message_and_commit",
                "message_to_caller": routing.get("fallback_message", "Someone from our team will call you back shortly"),
                "log_priority": "emergency",
                "must_collect_before_hanging_up": ["caller_name", "callback_number", "site_address"],
            },
            "never_do": [
                "Transfer emergency call to voicemail",
                "Hang up without giving human commitment when transfers fail",
                "Promise response time not specified in configuration",
                "Mention internal software tools to callers"
            ]
        },
        "retell_import_instructions": {
            "step_1": "Log in to your Retell account at https://app.retell.ai",
            "step_2": "Navigate to 'Agents' → 'Create New Agent'",
            "step_3": "Set Agent Name to the value in agent_name field above",
            "step_4": "Select voice from Voice Library matching voice_style.voice_id",
            "step_5": "Paste the contents of system_prompt into the 'System Prompt' field",
            "step_6": "Configure call transfer numbers from call_transfer_protocol",
            "step_7": "Set language to en-US",
            "step_8": "Save and test with a sample call"
        }
    }

    return spec
