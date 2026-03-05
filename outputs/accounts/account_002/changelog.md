# Changelog — account_002

**Generated:** 2026-03-05T09:16:14Z
**Account:** CoolBreeze HVAC Services

## Summary

- Version: v1 (demo) → v2 (post-onboarding)
- Total memo field changes: 12
- Total spec field changes: 11
- Conflicts resolved: 0

## Account Memo Changes

- **CHANGED** `business_hours.days`
  - Before: `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']`
  - After:  `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']`
- **CHANGED** `call_transfer_rules.business_hours_transfer_number`
  - Before: `None`
  - After:  `602-555-0180`
- **CHANGED** `call_transfer_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `25`
- **CHANGED** `emergency_definition`
  - Before: `['No cooling during extreme heat conditions', 'Commercial HVAC complete failure', 'Heating system completely out (especially below 32°F)', 'No heat with outdoor temperature below 32°F']`
  - After:  `['No cooling during extreme heat conditions', 'Commercial HVAC complete failure', 'Heating system completely out (especially below 32°F)', 'No heat with outdoor temperature below 32°F', 'No A/C in extreme heat (residential — senior citizens or families with small children)', 'Refrigeration failure at restaurant or food storage facility', 'HVAC/cooling/heating failure at medical facility']`
- **CHANGED** `emergency_routing_rules.primary_transfer_number`
  - Before: `None`
  - After:  `602-555-0213`
- **CHANGED** `emergency_routing_rules.secondary_transfer_number`
  - Before: `None`
  - After:  `602-555-0287`
- **CHANGED** `emergency_routing_rules.transfer_timeout_seconds`
  - Before: `None`
  - After:  `25`
- **CHANGED** `non_emergency_routing_rules.info_to_collect`
  - Before: `['name', 'callback_number', 'site_address', 'residential_or_commercial']`
  - After:  `['name', 'callback_number', 'site_address', 'residential_or_commercial', 'brief_description', 'equipment_model']`
- **CHANGED** `notes`
  - Before: `Extracted via rule-based engine from transcript. Source: demo call.`
  - After:  `Extracted via rule-based engine from transcript. Source: demo call. | Updated from onboarding call on 2026-03-05. 0 field(s) updated.`
- **CHANGED** `questions_or_unknowns`
  - Before: `['Emergency on-call primary phone number not specified', 'Transfer timeout/retry settings not specified', 'Business hours main transfer number not specified']`
  - After:  `[]`
- **CHANGED** `services_supported`
  - Before: `['Hvac', 'Heating', 'Cooling', 'Ventilation']`
  - After:  `['Hvac', 'Heating', 'Cooling', 'Ventilation', 'Refrigeration']`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Agent Spec Changes

- **CHANGED** `call_transfer_protocol.business_hours.timeout_seconds`
  - Before: `None`
  - After:  `25`
- **CHANGED** `call_transfer_protocol.business_hours.transfer_number`
  - Before: `None`
  - After:  `602-555-0180`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.primary_transfer_number`
  - Before: `None`
  - After:  `602-555-0213`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.secondary_transfer_number`
  - Before: `None`
  - After:  `602-555-0287`
- **CHANGED** `call_transfer_protocol.emergency_after_hours.timeout_seconds`
  - Before: `None`
  - After:  `25`
- **CHANGED** `key_variables.business_hours_days`
  - Before: `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']`
  - After:  `['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']`
- **CHANGED** `key_variables.business_hours_transfer_number`
  - Before: `None`
  - After:  `602-555-0180`
- **CHANGED** `key_variables.emergency_routing_primary`
  - Before: `None`
  - After:  `602-555-0213`
- **CHANGED** `key_variables.emergency_routing_secondary`
  - Before: `None`
  - After:  `602-555-0287`
- **CHANGED** `key_variables.emergency_transfer_timeout_seconds`
  - Before: `None`
  - After:  `25`
- **CHANGED** `version`
  - Before: `v1`
  - After:  `v2`

## Remaining Open Questions

_All questions resolved._