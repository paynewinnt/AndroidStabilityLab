# Top Issues Snapshot Smoke

- snapshot_id: snapshot_62acba7e4e3741b28dbc631031c434c9
- snapshot_type: top_issues
- created_at: 2025-07-20T03:27:31.662945
- created_by: cli

## Filters

```json
{
  "package_name": "com.hihonor.calculator",
  "limit": 5,
  "min_side_issue_groups": 1,
  "significant_occurrence_delta": 1,
  "significant_affected_run_delta": 1,
  "significant_affected_device_delta": 1,
  "significant_affected_scenario_delta": 1
}
```

## Rule Versions

```json
{
  "fingerprint_rule_versions": [
    "v1"
  ]
}
```

## Summary

```json
{
  "top_issue_count": 2,
  "first_issue_title": "冷启动超时"
}
```

## Payload

```json
{
  "filters": {
    "package_name": "com.hihonor.calculator",
    "limit": 5,
    "min_side_issue_groups": 1,
    "significant_occurrence_delta": 1,
    "significant_affected_run_delta": 1,
    "significant_affected_device_delta": 1,
    "significant_affected_scenario_delta": 1
  },
  "top_issue_count": 2,
  "issues": [
    {
      "fingerprint": "ifp_21f743637f19c1d4",
      "rule_version": "v1",
      "fingerprint_components": {
        "issue_type": "startup_timeout",
        "package_name": "com.hihonor.calculator",
        "process_name": "",
        "scenario_name": "cold_start_loop",
        "title_key": "",
        "raw_key": ""
      },
      "issue_type": "startup_timeout",
      "title": "冷启动超时",
      "severity": "high",
      "first_seen_at": "2025-07-19T15:04:03.686731",
      "last_seen_at": "2025-07-19T15:30:08.286882",
      "occurrence_count": 5,
      "affected_run_count": 5,
      "affected_device_count": 1,
      "affected_scenario_count": 1,
      "affected_version_count": 0,
      "affected_packages": [
        "com.hihonor.calculator"
      ],
      "affected_devices": [
        "192.168.31.99:5555"
      ],
      "affected_scenarios": [
        "cold_start_loop"
      ],
      "affected_versions": [],
      "sample_event_ids": [
        "issue_c68df91c129b4b229e884bc51c03a058",
        "issue_b21bbf7feb5b4e819f123755e5fcf0de",
        "issue_d2863e5aef714dafb5d5e157ddb6e5ce",
        "issue_2d476c41a6dd49a690bd36dff40d7992",
        "issue_22bfaf463358414288338cb09b73fcf3"
      ],
      "score": 310.0,
      "score_breakdown": {
        "severity": 250.0,
        "occurrence_count": 50.0,
        "affected_device_count": 5.0,
        "affected_scenario_count": 5.0
      }
    },
    {
      "fingerprint": "ifp_9cc12c0642a31dce",
      "rule_version": "v1",
      "fingerprint_components": {
        "issue_type": "device_offline",
        "package_name": "com.hihonor.calculator",
        "process_name": "",
        "scenario_name": "cold_start_loop",
        "title_key": "",
        "raw_key": ""
      },
      "issue_type": "device_offline",
      "title": "执行期间设备离线",
      "severity": "high",
      "first_seen_at": "2025-07-19T15:19:09.973984",
      "last_seen_at": "2025-07-19T15:19:09.973984",
      "occurrence_count": 1,
      "affected_run_count": 1,
      "affected_device_count": 1,
      "affected_scenario_count": 1,
      "affected_version_count": 0,
      "affected_packages": [
        "com.hihonor.calculator"
      ],
      "affected_devices": [
        "192.168.31.99:5555"
      ],
      "affected_scenarios": [
        "cold_start_loop"
      ],
      "affected_versions": [],
      "sample_event_ids": [
        "issue_af9cc47ca1fd47ddbd4bc6d25cda27cf"
      ],
      "score": 270.0,
      "score_breakdown": {
        "severity": 250.0,
        "occurrence_count": 10.0,
        "affected_device_count": 5.0,
        "affected_scenario_count": 5.0
      }
    }
  ]
}
```
