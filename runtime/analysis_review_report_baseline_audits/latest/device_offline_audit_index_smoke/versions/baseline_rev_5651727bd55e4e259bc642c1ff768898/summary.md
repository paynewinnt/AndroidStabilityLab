# Baseline Audit Latest | device_offline_audit_index_smoke

- audit_id: baseline_audit_latest_device_offline_audit_index_smoke
- baseline_key: device_offline_audit_index_smoke
- created_at: 2025-07-20T09:59:11.683052
- created_by: smoke_index
- current_report: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke

## Summary

```json
{
  "baseline_key": "device_offline_audit_index_smoke",
  "history_count": 2,
  "action_counts": {
    "set": 1,
    "promote": 1
  },
  "actor_counts": {
    "smoke_index": 2
  },
  "distinct_report_count": 2,
  "comparison_linked_event_count": 1,
  "first_changed_at": "2025-07-20T09:59:07.665004",
  "last_changed_at": "2025-07-20T09:59:11.682887",
  "current_report_id": "review_report_4f2154c3b46a4fbdbaa2c56f52c2953e",
  "current_report_name": "Rule Review Report Smoke"
}
```

## Timeline

- [set] 2025-07-20T09:59:07.665004 | smoke_index
  - from: n/a | n/a
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
- [promote] 2025-07-20T09:59:11.682887 | smoke_index
  - from: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Promotion policy checks passed.
  - comparison_id: review_report_compare_9d090291ec524d80aadcb3686948ae79
  - policy_version: v1
