# Baseline Audit Latest | device_offline_audit_retention_smoke

- audit_id: baseline_audit_latest_device_offline_audit_retention_smoke
- baseline_key: device_offline_audit_retention_smoke
- created_at: 2025-07-20T10:04:33.364062
- created_by: smoke_retention
- current_report: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke

## Summary

```json
{
  "baseline_key": "device_offline_audit_retention_smoke",
  "history_count": 4,
  "action_counts": {
    "set": 3,
    "promote": 1
  },
  "actor_counts": {
    "smoke_retention": 4
  },
  "distinct_report_count": 2,
  "comparison_linked_event_count": 1,
  "first_changed_at": "2025-07-20T10:04:32.505385",
  "last_changed_at": "2025-07-20T10:04:33.363819",
  "current_report_id": "review_report_4f2154c3b46a4fbdbaa2c56f52c2953e",
  "current_report_name": "Rule Review Report Smoke"
}
```

## Timeline

- [set] 2025-07-20T10:04:32.505385 | smoke_retention
  - from: n/a | n/a
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
- [promote] 2025-07-20T10:04:32.808507 | smoke_retention
  - from: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Promotion policy checks passed.
  - comparison_id: review_report_compare_4923ddce80cb411c9010c4ac52a7667c
  - policy_version: v1
- [set] 2025-07-20T10:04:33.087884 | smoke_retention
  - from: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
- [set] 2025-07-20T10:04:33.363819 | smoke_retention
  - from: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
