# Baseline Audit Latest | golden_suite_visibility_smoke

- audit_id: baseline_audit_latest_golden_suite_visibility_smoke
- baseline_key: golden_suite_visibility_smoke
- created_at: 2025-07-21T07:29:41.604260
- created_by: cli
- current_report: review_report_22b7346274fd43009b876c39715355e9 | Golden Suite Review Report Smoke

## Summary

```json
{
  "baseline_key": "golden_suite_visibility_smoke",
  "history_count": 2,
  "action_counts": {
    "set": 1,
    "promote": 1
  },
  "actor_counts": {
    "cli": 2
  },
  "distinct_report_count": 2,
  "comparison_linked_event_count": 1,
  "first_changed_at": "2025-07-21T07:21:46.736805",
  "last_changed_at": "2025-07-21T07:21:54.671795",
  "current_report_id": "review_report_22b7346274fd43009b876c39715355e9",
  "current_report_name": "Golden Suite Review Report Smoke",
  "current_report_golden_suite": {
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
}
```

## Current Report Golden Suite

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

## Timeline

- [set] 2025-07-21T07:21:46.736805 | cli
  - from: n/a | n/a
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
- [promote] 2025-07-21T07:21:54.671795 | cli
  - from: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - to: review_report_22b7346274fd43009b876c39715355e9 | Golden Suite Review Report Smoke
  - reason: Promotion policy checks passed.
  - comparison_id: review_report_compare_ad1f750765d04bfe83073f2481309566
  - policy_version: v1
