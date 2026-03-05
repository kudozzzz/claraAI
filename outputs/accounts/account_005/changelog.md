# Changelog — account_005

**Generated:** 2026-03-05T09:16:14Z
**Account:** TotalFire Protection Inc.

## Summary

- Version: v1 (demo) → v2 (post-onboarding)
- Total memo field changes: 13
- Total spec field changes: 12
- Conflicts resolved: 1

## Account Memo Changes

- **CHANGED** `call_transfer_rules.business_hours_transfer_number`
  - Before: `None`
  - After:  `972-555-0190`
- **CHANGED** `call_transfer_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `20`
- **CHANGED** `emergency_definition`
  - Before: `['Active sprinkler discharge', 'Fire alarm panel trouble signal', 'Kitchen hood/suppression discharge or activation', 'Active water damage']`
  - After:  `['Active sprinkler discharge', 'Fire alarm panel trouble signal', 'Kitchen hood/suppression discharge or activation', 'Active water damage', 'Fire alarm panel activation', 'CO detector / carbon monoxide alarm activation', 'Suppression system discharge at data center or server room']`
- **CHANGED** `emergency_routing_rules.fallback_message`
  - Before: `We will have someone call you back shortly`
  - After:  `We will call you back within 10 minutes`
- **CHANGED** `emergency_routing_rules.primary_transfer_number`
  - Before: `None`
  - After:  `972-555-0200`
- **CHANGED** `emergency_routing_rules.secondary_transfer_number`
  - Before: `None`
  - After:  `972-555-0211`
- **CHANGED** `emergency_routing_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `20`
- **CHANGED** `integration_constraints`
  - Before: `['Never mention ServiceTrade to callers — internal use only', 'Do not create kitchen hood suppression jobs in ServiceTrade from field techs']`
  - After:  `['Never mention ServiceTrade to callers — internal use only', 'Do not create kitchen hood suppression jobs in ServiceTrade from field techs', 'Do not create sprinkler jobs in ServiceTrade from field techs']`
- **CHANGED** `non_emergency_routing_rules.info_to_collect`
  - Before: `['name', 'callback_number', 'residential_or_commercial']`
  - After:  `['name', 'callback_number', 'residential_or_commercial', 'site_address', 'brief_description', 'company_name', 'location_market']`
- **CHANGED** `notes`
  - Before: `Extracted via rule-based engine from transcript. Source: demo call.`
  - After:  `Extracted via rule-based engine from transcript. Source: demo call. | Updated from onboarding call on 2026-03-05. 1 field(s) updated.`
- **CHANGED** `questions_or_unknowns`
  - Before: `['Emergency on-call primary phone number not specified', 'Transfer timeout/retry settings not specified', 'Business hours main transfer number not specified']`
  - After:  `[]`
- **CHANGED** `services_supported`
  - Before: `['Fire Sprinkler', 'Fire Alarm', 'Inspection Scheduling', 'Annual Inspection', 'Certification', 'Kitchen Hood', 'Hood Suppression']`
  - After:  `['Fire Sprinkler', 'Fire Alarm', 'Inspection Scheduling', 'Annual Inspection', 'Certification', 'Kitchen Hood', 'Hood Suppression', 'Co Detector']`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Agent Spec Changes

- **CHANGED** `call_transfer_protocol.business_hours.timeout_seconds`
  - Before: `None`
  - After:  `20`
- **CHANGED** `call_transfer_protocol.business_hours.transfer_number`
  - Before: `None`
  - After:  `972-555-0190`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.primary_transfer_number`
  - Before: `None`
  - After:  `972-555-0200`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.secondary_transfer_number`
  - Before: `None`
  - After:  `972-555-0211`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.timeout_seconds`
  - Before: `None`
  - After:  `20`
- **CHANGED** `fallback_protocol.all_transfers_failed.message_to_caller`
  - Before: `We will have someone call you back shortly`
  - After:  `We will call you back within 10 minutes`
- **CHANGED** `key_variables.business_hours_transfer_number`
  - Before: `None`
  - After:  `972-555-0190`
- **CHANGED** `key_variables.emergency_callback_commitment`
  - Before: `We will have someone call you back shortly`
  - After:  `We will call you back within 10 minutes`
- **CHANGED** `key_variables.emergency_routing_primary`
  - Before: `None`
  - After:  `972-555-0200`
- **CHANGED** `key_variables.emergency_routing_secondary`
  - Before: `None`
  - After:  `972-555-0211`
- **CHANGED** `key_variables.emergency_transfer_timeout_seconds`
  - Before: `None`
  - After:  `20`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Resolved Conflicts

- **Field:** `fallback_message`
  - Demo value: `We will have someone call you back shortly`
  - Onboarding value: `We will call you back within 10 minutes`
  - Resolution: onboarding_value_applied

## Remaining Open Questions

_All questions resolved._