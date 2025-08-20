# Golden Suite Visibility Smoke

- report_id: review_report_204b95477c7041b08a21720e91d1e0b8
- created_at: 2025-07-21T07:21:15.090883
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
  "changed_family_count_total": 3,
  "finding_count_total": 1,
  "high_risk_family_count": 3,
  "golden_suite_snapshot_count": 0,
  "golden_suite_passed_snapshot_count": 0,
  "golden_suite_failed_snapshot_count": 0,
  "golden_suite_case_count_total": 0,
  "golden_suite_passed_case_count_total": 0,
  "golden_suite_failed_case_count_total": 0,
  "golden_suite_versions": [],
  "golden_suite_suite_paths": []
}
```

## Golden Suite

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

## Filters

```json
{
  "snapshot_created_by": null,
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

- [conditional_pass] snapshot_c8db4b56f28f4a6c9da41f6dd7e7d5fb | Rule Review Smoke
  - created_at: 2025-07-20T08:34:07.798607
  - policy_version: v1
  - changed_family_count: 3
  - finding_count: 1
  - golden_suite: n/a | cases=0 | failed=0 | version=n/a
  - candidate_path: /tmp/asl_replay_rules.json
  - detail_path: runtime/analysis_snapshots/snapshot_c8db4b56f28f4a6c9da41f6dd7e7d5fb/snapshot.json

## High Risk Families

- [conditional_pass] fingerprint_changed | device_offline | 执行期间设备离线 | snapshots=1 | total_occurrences=3
- [conditional_pass] fingerprint_changed | device_offline | 执行期间设备离线 | snapshots=1 | total_occurrences=2
- [conditional_pass] fingerprint_changed | device_offline | 执行期间设备离线 | snapshots=1 | total_occurrences=1
