# Golden Suite Review Report Smoke

- report_id: review_report_22b7346274fd43009b876c39715355e9
- created_at: 2025-07-21T07:21:46.733212
- created_by: cli

## Summary

```json
{
  "snapshot_count": 1,
  "decision_counts": {
    "conditional_pass": 1
  },
  "policy_versions": [
    "v1"
  ],
  "candidate_paths": [
    "/tmp/asl_replay_rules.json"
  ],
  "baseline_paths": [
    "config/stability_rules.json"
  ],
  "changed_family_count_total": 0,
  "finding_count_total": 1,
  "high_risk_family_count": 0,
  "golden_suite_snapshot_count": 1,
  "golden_suite_passed_snapshot_count": 1,
  "golden_suite_failed_snapshot_count": 0,
  "golden_suite_case_count_total": 4,
  "golden_suite_passed_case_count_total": 4,
  "golden_suite_failed_case_count_total": 0,
  "golden_suite_versions": [
    "v1"
  ],
  "golden_suite_suite_paths": [
    "config/rule_replay_golden_samples.json"
  ]
}
```

## Golden Suite

```json
{
  "snapshot_count": 1,
  "passed_snapshot_count": 1,
  "failed_snapshot_count": 0,
  "case_count_total": 4,
  "passed_case_count_total": 4,
  "failed_case_count_total": 0,
  "versions": [
    "v1"
  ],
  "suite_paths": [
    "config/rule_replay_golden_samples.json"
  ]
}
```

## Filters

```json
{
  "snapshot_created_by": "golden_suite_report_smoke",
  "decision": null,
  "policy_version": null,
  "baseline_path": null,
  "candidate_path": null,
  "created_from": null,
  "created_to": null,
  "limit": 5
}
```

## Review Snapshots

- [conditional_pass] snapshot_d410b851c45444a1b51aa584ee53211b | Golden Suite Review Snapshot Smoke
  - created_at: 2025-07-21T07:21:38.898513
  - policy_version: v1
  - changed_family_count: 0
  - finding_count: 1
  - golden_suite: pass | cases=4 | failed=0 | version=v1
  - candidate_path: /tmp/asl_replay_rules.json
  - detail_path: runtime/analysis_snapshots/snapshot_d410b851c45444a1b51aa584ee53211b/snapshot.json

## High Risk Families

