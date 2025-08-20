# Rule Review Report Smoke

- report_id: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e
- created_at: 2025-07-20T08:45:41.881697
- created_by: review_report_smoke

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
  "high_risk_family_count": 3
}
```

## Filters

```json
{
  "snapshot_created_by": "review_smoke",
  "decision": null,
  "policy_version": null,
  "baseline_path": null,
  "candidate_path": null,
  "created_from": null,
  "created_to": null,
  "limit": 10
}
```

## Review Snapshots

- [conditional_pass] snapshot_c8db4b56f28f4a6c9da41f6dd7e7d5fb | Rule Review Smoke
  - created_at: 2025-07-20T08:34:07.798607
  - policy_version: v1
  - changed_family_count: 3
  - finding_count: 1
  - candidate_path: /tmp/asl_replay_rules.json
  - detail_path: runtime/analysis_snapshots/snapshot_c8db4b56f28f4a6c9da41f6dd7e7d5fb/snapshot.json

## High Risk Families

- [conditional_pass] fingerprint_changed | device_offline | 执行期间设备离线 | snapshots=1 | total_occurrences=3
- [conditional_pass] fingerprint_changed | device_offline | 执行期间设备离线 | snapshots=1 | total_occurrences=2
- [conditional_pass] fingerprint_changed | device_offline | 执行期间设备离线 | snapshots=1 | total_occurrences=1
