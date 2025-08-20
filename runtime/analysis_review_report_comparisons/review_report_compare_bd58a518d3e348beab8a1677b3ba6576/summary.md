# Golden Suite Compare Smoke

- comparison_id: review_report_compare_bd58a518d3e348beab8a1677b3ba6576
- created_at: 2025-07-21T07:29:02.702087
- created_by: cli
- left_report: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
- right_report: review_report_22b7346274fd43009b876c39715355e9 | Golden Suite Review Report Smoke

## Summary

```json
{
  "left_report_id": "review_report_4f2154c3b46a4fbdbaa2c56f52c2953e",
  "right_report_id": "review_report_22b7346274fd43009b876c39715355e9",
  "left_created_at": "2025-07-20T08:45:41.881697",
  "right_created_at": "2025-07-21T07:21:46.733212",
  "snapshot_count_delta": 0,
  "changed_family_count_total_delta": -3,
  "finding_count_total_delta": 0,
  "high_risk_family_count_delta": -3,
  "left_golden_suite": {
    "snapshot_count": 0,
    "passed_snapshot_count": 0,
    "failed_snapshot_count": 0,
    "case_count_total": 0,
    "passed_case_count_total": 0,
    "failed_case_count_total": 0,
    "versions": [],
    "suite_paths": []
  },
  "right_golden_suite": {
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
  },
  "golden_suite_snapshot_count_delta": 1,
  "golden_suite_passed_snapshot_count_delta": 1,
  "golden_suite_failed_snapshot_count_delta": 0,
  "golden_suite_case_count_total_delta": 4,
  "golden_suite_passed_case_count_total_delta": 4,
  "golden_suite_failed_case_count_total_delta": 0,
  "decision_count_deltas": {
    "conditional_pass": 0
  },
  "family_delta_counts": {
    "removed": 3
  }
}
```

## Golden Suite

### Left

```json
{
  "snapshot_count": 0,
  "passed_snapshot_count": 0,
  "failed_snapshot_count": 0,
  "case_count_total": 0,
  "passed_case_count_total": 0,
  "failed_case_count_total": 0,
  "versions": [],
  "suite_paths": []
}
```

### Right

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

## Family Diffs

- [removed] fingerprint_changed | device_offline | 执行期间设备离线 | left_occurrences=3 | right_occurrences=0
- [removed] fingerprint_changed | device_offline | 执行期间设备离线 | left_occurrences=2 | right_occurrences=0
- [removed] fingerprint_changed | device_offline | 执行期间设备离线 | left_occurrences=1 | right_occurrences=0
