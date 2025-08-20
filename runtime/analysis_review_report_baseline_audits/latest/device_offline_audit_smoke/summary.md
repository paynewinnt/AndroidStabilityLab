# Baseline Audit Latest | device_offline_audit_smoke

- audit_id: baseline_audit_latest_device_offline_audit_smoke
- baseline_key: device_offline_audit_smoke
- created_at: 2025-07-20T09:31:53.415138
- created_by: smoke_auto
- current_report: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke

## Summary

```json
{
  "baseline_key": "device_offline_audit_smoke",
  "history_count": 4,
  "action_counts": {
    "set": 1,
    "promote": 2,
    "rollback": 1
  },
  "actor_counts": {
    "smoke": 3,
    "smoke_auto": 1
  },
  "distinct_report_count": 2,
  "comparison_linked_event_count": 2,
  "first_changed_at": "2025-07-20T09:27:19.038341",
  "last_changed_at": "2025-07-20T09:31:53.414910",
  "current_report_id": "review_report_4f2154c3b46a4fbdbaa2c56f52c2953e",
  "current_report_name": "Rule Review Report Smoke"
}
```

## Timeline

- [set] 2025-07-20T09:27:19.038341 | smoke
  - from: n/a | n/a
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Baseline pointer was updated manually.
  - comparison_id: n/a
  - policy_version: n/a
- [promote] 2025-07-20T09:27:23.228337 | smoke
  - from: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Promotion policy checks passed.
  - comparison_id: review_report_compare_69b8b2e4dd464b3d837c2e097cc35434
  - policy_version: v1
- [rollback] 2025-07-20T09:27:26.218177 | smoke
  - from: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - to: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - reason: Rolled back baseline to report review_report_f0576b472d83419cb6bfb685a6c6ee7e.
  - comparison_id: n/a
  - policy_version: n/a
- [promote] 2025-07-20T09:31:53.414910 | smoke_auto
  - from: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke
  - to: review_report_4f2154c3b46a4fbdbaa2c56f52c2953e | Rule Review Report Smoke
  - reason: Promotion policy checks passed.
  - comparison_id: review_report_compare_7cf0c7e5ab434fbdb4e4816d35fad6be
  - policy_version: v1
