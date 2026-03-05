# Changelog — account_004

**Generated:** 2026-03-05T09:16:14Z
**Account:** ShieldGuard Security Systems

## Summary

- Version: v1 (demo) → v2 (post-onboarding)
- Total memo field changes: 11
- Total spec field changes: 10
- Conflicts resolved: 0

## Account Memo Changes

- **CHANGED** `call_transfer_rules.business_hours_transfer_number`
  - Before: `None`
  - After:  `206-555-0134`
- **CHANGED** `call_transfer_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `emergency_definition`
  - Before: `['Active alarm activation not confirmed as false alarm', 'Active alarm going off']`
  - After:  `['Active alarm activation not confirmed as false alarm', 'Active alarm going off', 'Fire alarm panel activation', 'Intruder visible on video/camera surveillance', 'Physical damage to security equipment suggesting break-in attempt', 'Fire alarm activation at a monitored site', 'Active alarm not confirmed as false alarm']`
- **CHANGED** `emergency_routing_rules.primary_transfer_number`
  - Before: `None`
  - After:  `206-555-0156`
- **CHANGED** `emergency_routing_rules.secondary_transfer_number`
  - Before: `None`
  - After:  `206-555-0178`
- **CHANGED** `emergency_routing_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `non_emergency_routing_rules.info_to_collect`
  - Before: `['name', 'callback_number', 'residential_or_commercial']`
  - After:  `['name', 'callback_number', 'residential_or_commercial', 'site_address', 'company_name']`
- **CHANGED** `notes`
  - Before: `Extracted via rule-based engine from transcript. Source: demo call.`
  - After:  `Extracted via rule-based engine from transcript. Source: demo call. | Updated from onboarding call on 2026-03-05. 0 field(s) updated.`
- **CHANGED** `questions_or_unknowns`
  - Before: `['Emergency on-call primary phone number not specified', 'Transfer timeout/retry settings not specified', 'Business hours main transfer number not specified']`
  - After:  `[]`
- **CHANGED** `services_supported`
  - Before: `['Burglar Alarm', 'Access Control', 'Video Surveillance', 'Security System']`
  - After:  `['Burglar Alarm', 'Access Control', 'Video Surveillance', 'Security System', 'Fire Alarm']`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Agent Spec Changes

- **CHANGED** `call_transfer_protocol.business_hours.timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `call_transfer_protocol.business_hours.transfer_number`
  - Before: `None`
  - After:  `206-555-0134`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.primary_transfer_number`
  - Before: `None`
  - After:  `206-555-0156`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.secondary_transfer_number`
  - Before: `None`
  - After:  `206-555-0178`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `key_variables.business_hours_transfer_number`
  - Before: `None`
  - After:  `206-555-0134`
- **CHANGED** `key_variables.emergency_routing_primary`
  - Before: `None`
  - After:  `206-555-0156`
- **CHANGED** `key_variables.emergency_routing_secondary`
  - Before: `None`
  - After:  `206-555-0178`
- **CHANGED** `key_variables.emergency_transfer_timeout_seconds`
  - Before: `None`
  - After:  `30`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Remaining Open Questions

_All questions resolved._