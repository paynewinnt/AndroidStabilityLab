# Baseline Audit Latest | device_offline_audit_auto_smoke

- audit_id: baseline_audit_latest_device_offline_audit_auto_smoke
- baseline_key: device_offline_audit_auto_smoke
- created_at: 2025-07-20T09:32:08.512149
- created_by: smoke_auto
- current_report: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke

## Summary

```json
{
  "baseline_key": "device_offline_audit_auto_smoke",
  "history_count": 3,
  "action_counts": {
    "set": 1,
    "promote": 1,
    "rollback": 1
  },
  "actor_counts": {
    "smoke_auto": 3
  },
  "distinct_report_count": 2,
  "comparison_linked_event_count": 1,
  "first_changed_at": "2025-07-20T09:32:02.178969",
  "last_changed_at": "2025-07-20T09:32:08.512041",
  "current_report_id": "review_report_f0576b472d83419cb6bfb685a6c6ee7e",
  "current_report_name": "Rule Review Summary Smoke"
}
```

## Timeline

- [set] 2025-07-20T09:32:02.178969 | smoke_auto
  - from: n/a | n/a
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
- [promote] 2025-07-20T09:32:05.745652 | smoke_auto
  - from: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Promotion policy checks passed.
  - comparison_id: review_report_compare_0b6bafaf854c475abb9a7f962311b07d
  - policy_version: v1
- [rollback] 2025-07-20T09:32:08.512041 | smoke_auto
  - from: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Rolled back baseline to report review_report_f0576b472d83419cb6bfb685a6c6ee7e.
  - comparison_id: n/a
  - policy_version: n/a
