# Golden Suite Review Snapshot Smoke

- snapshot_id: snapshot_d410b851c45444a1b51aa584ee53211b
- snapshot_type: review
- created_at: 2025-07-21T07:21:38.898513
- created_by: golden_suite_report_smoke

## Scope

- baseline_path: config/stability_rules.json
- candidate_path: /tmp/asl_replay_rules.json

## Filters

```json
{
  "package_name": "com.example.app"
}
```

## Rule Versions

```json
{
  "policy_version": "v1",
  "baseline_fingerprint_rule_version": "v1",
  "candidate_fingerprint_rule_version": "v1"
}
```

## Source Refs

```json
{
  "task_ids": [],
  "run_ids": [],
  "instance_ids": [],
  "device_ids": [],
  "report_paths": [],
  "execution_log_paths": [],
  "artifact_paths": [],
  "summary": {
    "task_count": 0,
    "run_count": 0,
    "instance_count": 0,
    "device_count": 0,
    "report_count": 0,
    "execution_log_count": 0,
    "artifact_count": 0
  }
}
```

## Summary

```json
{
  "decision": "conditional_pass",
  "family_count": 0,
  "changed_family_count": 0,
  "finding_count": 1,
  "change_summary": {}
}
```

## Payload

```json
{
  "decision": "conditional_pass",
  "policy_version": "v1",
  "policy_path": "config/rule_review_policy.json",
  "baseline_path": "config/stability_rules.json",
  "candidate_path": "/tmp/asl_replay_rules.json",
  "baseline_rule_version": "v1",
  "candidate_rule_version": "v1",
  "filters": {
    "task_id": "",
    "run_status": "",
    "template_type": "",
    "version": "",
    "package_name": "com.example.app",
    "device_id": "",
    "issue_type": "",
    "created_from": "",
    "created_to": ""
  },
  "family_count": 0,
  "changed_family_count": 0,
  "change_summary": {},
  "issue_type_change_summary": {},
  "findings": [
    {
      "level": "warning",
      "scope": "coverage",
      "issue_type": "",
      "change_type": "insufficient_family_count",
      "observed_count": 0,
      "threshold": 1,
      "message": "Replay only covered 0 issue families, below the minimum required 1."
    }
  ],
  "reasons": [
    "Replay only covered 0 issue families, below the minimum required 1."
  ],
  "baseline_valid": true,
  "candidate_valid": true,
  "baseline_errors": [],
  "candidate_errors": [],
  "golden_suite": {
    "suite_path": "config/rule_replay_golden_samples.json",
    "suite_version": "v1",
    "case_count": 4,
    "passed_case_count": 4,
    "failed_case_count": 0,
    "passed": true,
    "cases": [
      {
        "case_id": "crash_regroup_ignore_raw_key",
        "description": "Crash families with different raw keys should merge when candidate ignores raw_key for crash.",
        "passed": true,
        "mismatches": []
      },
      {
        "case_id": "anr_regroup_ignore_raw_key",
        "description": "ANR families with different raw keys should merge when candidate ignores raw_key for anr.",
        "passed": true,
        "mismatches": []
      },
      {
        "case_id": "startup_timeout_regroup_matches_default_ignore",
        "description": "Startup timeout families should merge when candidate follows the default ignore_raw_key behavior.",
        "passed": true,
        "mismatches": []
      },
      {
        "case_id": "device_offline_fingerprint_changed_without_regroup",
        "description": "Device-offline fingerprint should change even when the family count stays grouped 1-to-1.",
        "passed": true,
        "mismatches": []
      }
    ]
  },
  "families": []
}
```
