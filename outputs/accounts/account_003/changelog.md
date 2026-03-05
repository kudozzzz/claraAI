# Changelog — account_003

**Generated:** 2026-03-05T09:16:14Z
**Account:** Apex Electrical Services

## Summary

- Version: v1 (demo) → v2 (post-onboarding)
- Total memo field changes: 10
- Total spec field changes: 10
- Conflicts resolved: 0

## Account Memo Changes

- **CHANGED** `call_transfer_rules.business_hours_transfer_number`
  - Before: `None`
  - After:  `312-555-0140`
- **CHANGED** `call_transfer_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `emergency_definition`
  - Before: `['Total or building-wide power failure', 'Sparking, burning smell, or electrical fire risk', 'Generator failure at critical facility (hospital, data center)', 'Generator failure at a critical facility']`
  - After:  `['Total or building-wide power failure', 'Sparking, burning smell, or electrical fire risk', 'Generator failure at critical facility (hospital, data center)', 'Generator failure at a critical facility', 'Electric shock or energized equipment malfunction with safety risk']`
- **CHANGED** `emergency_routing_rules.primary_transfer_number`
  - Before: `None`
  - After:  `312-555-0167`
- **CHANGED** `emergency_routing_rules.secondary_transfer_number`
  - Before: `None`
  - After:  `312-555-0189`
- **CHANGED** `emergency_routing_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `non_emergency_routing_rules.info_to_collect`
  - Before: `['name', 'callback_number', 'brief_description', 'residential_or_commercial']`
  - After:  `['name', 'callback_number', 'brief_description', 'residential_or_commercial', 'site_address', 'company_name']`
- **CHANGED** `notes`
  - Before: `Extracted via rule-based engine from transcript. Source: demo call.`
  - After:  `Extracted via rule-based engine from transcript. Source: demo call. | Updated from onboarding call on 2026-03-05. 0 field(s) updated.`
- **CHANGED** `questions_or_unknowns`
  - Before: `['Emergency on-call primary phone number not specified', 'Transfer timeout/retry settings not specified', 'Business hours main transfer number not specified']`
  - After:  `[]`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Agent Spec Changes

- **CHANGED** `call_transfer_protocol.business_hours.timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `call_transfer_protocol.business_hours.transfer_number`
  - Before: `None`
  - After:  `312-555-0140`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.primary_transfer_number`
  - Before: `None`
  - After:  `312-555-0167`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.secondary_transfer_number`
  - Before: `None`
  - After:  `312-555-0189`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `key_variables.business_hours_transfer_number`
  - Before: `None`
  - After:  `312-555-0140`
- **CHANGED** `key_variables.emergency_routing_primary`
  - Before: `None`
  - After:  `312-555-0167`
- **CHANGED** `key_variables.emergency_routing_secondary`
  - Before: `None`
  - After:  `312-555-0189`
- **CHANGED** `key_variables.emergency_transfer_timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Remaining Open Questions

_All questions resolved._