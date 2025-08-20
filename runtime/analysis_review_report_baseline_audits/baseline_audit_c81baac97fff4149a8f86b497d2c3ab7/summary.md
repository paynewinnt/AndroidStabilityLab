# Baseline Audit Smoke

- audit_id: baseline_audit_c81baac97fff4149a8f86b497d2c3ab7
- baseline_key: device_offline_audit_smoke
- created_at: 2025-07-20T09:27:31.459782
- created_by: smoke
- current_report: review_report_f0576b472d83419cb6bfb685a6c6ee7e | Rule Review Summary Smoke

## Summary

```json
{
  "baseline_key": "device_offline_audit_smoke",
  "history_count": 3,
  "action_counts": {
    "set": 1,
    "promote": 1,
    "rollback": 1
  },
  "actor_counts": {
    "smoke": 3
  },
  "distinct_report_count": 2,
  "comparison_linked_event_count": 1,
  "first_changed_at": "2025-07-20T09:27:19.038341",
  "last_changed_at": "2025-07-20T09:27:26.218177",
  "current_report_id": "review_report_f0576b472d83419cb6bfb685a6c6ee7e",
  "current_report_name": "Rule Review Summary Smoke"
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
