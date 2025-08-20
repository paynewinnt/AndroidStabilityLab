# Rule Review Smoke

- snapshot_id: snapshot_c8db4b56f28f4a6c9da41f6dd7e7d5fb
- snapshot_type: review
- created_at: 2025-07-20T08:34:07.798607
- created_by: review_smoke

## Scope

- baseline_path: config/stability_rules.json
- candidate_path: /tmp/asl_replay_rules.json

## Filters

```json
{
  "issue_type": "device_offline"
}
```

## Rule Versions

```json
{
  "policy_version": "v1",
  "baseline_fingerprint_rule_version": "v1",
  "candidate_fingerprint_rule_version": "v1"
}
```

## Source Refs

```json
{
  "task_ids": [
    "task_0aae5f86ad1942bab107d05f56e14fc2",
    "task_97ea23bccb1b4773930a9a3261576260",
    "task_b914b5f708a54fc08175afa28358cd54",
    "task_cea4fb16a2f542119768a9e81431cf8d"
  ],
  "run_ids": [
    "run_35dd1bd2734b4c77b67e18853fd3668c",
    "run_9f6fa582bfa2497f8ef4269372edd056",
    "run_a0d485eb673442d2b0641fbcff76fa9a",
    "run_aee68549d5814b18b6f8d01fbfbe3761",
    "run_c32c04baa7f040c984ef448957900c01"
  ],
  "instance_ids": [
    "instance_14580099b43447fda4ebc28eb30f193c",
    "instance_b7629e04c92241a4ba55e1fc2b1207c8",
    "instance_c1964d6bc0914af4bf3091cf757bf147",
    "instance_dde860bb2e9b4f66aa53ba288532518e",
    "instance_df0ad3b5d547422ebda48b2c952a5f54"
  ],
  "device_ids": [
    "192.168.31.99:5555",
    "dev-a"
  ],
  "report_paths": [
    "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_35dd1bd2734b4c77b67e18853fd3668c/executions/instance_dde860bb2e9b4f66aa53ba288532518e/devices/dev-a/report/report.md",
    "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/report/report.md",
    "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/report/report.md",
    "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/report/report.md",
    "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/report/report.md"
  ],
  "execution_log_paths": [
    "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_35dd1bd2734b4c77b67e18853fd3668c/executions/instance_dde860bb2e9b4f66aa53ba288532518e/devices/dev-a/logs/execution.log",
    "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/logs/execution.log",
    "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/logs/execution.log",
    "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/logs/execution.log",
    "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/logs/execution.log"
  ],
  "artifact_paths": [
    "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/artifacts/issue_698ee60fe47144859fed907cd6ffb582/execution.log",
    "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/artifacts/issue_c82537bfdc59474e856d67ff6c142435/execution.log",
    "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/artifacts/issue_165ebe78222049b785b21c90cb05dd40/execution.log",
    "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/artifacts/issue_7a7fc4dfbf6d42968d659dd2b09379f9/execution.log"
  ],
  "summary": {
    "task_count": 4,
    "run_count": 5,
    "instance_count": 5,
    "device_count": 2,
    "report_count": 5,
    "execution_log_count": 5,
    "artifact_count": 4
  }
}
```

## Summary

```json
{
  "decision": "conditional_pass",
  "family_count": 3,
  "changed_family_count": 3,
  "finding_count": 1,
  "change_summary": {
    "fingerprint_changed": 3
  }
}
```

## Payload

```json
{
  "decision": "conditional_pass",
  "policy_version": "v1",
  "policy_path": "config/rule_review_policy.json",
  "baseline_path": "config/stability_rules.json",
  "candidate_path": "/tmp/asl_replay_rules.json",
  "baseline_rule_version": "v1",
  "candidate_rule_version": "v1",
  "filters": {
    "task_id": "",
    "run_status": "",
    "template_type": "",
    "version": "",
    "package_name": "",
    "device_id": "",
    "issue_type": "device_offline",
    "created_from": "",
    "created_to": ""
  },
  "family_count": 3,
  "changed_family_count": 3,
  "change_summary": {
    "fingerprint_changed": 3
  },
  "issue_type_change_summary": {
    "device_offline": {
      "fingerprint_changed": 3
    }
  },
  "findings": [
    {
      "level": "warning",
      "scope": "global",
      "issue_type": "",
      "change_type": "fingerprint_changed",
      "observed_count": 3,
      "threshold": 3,
      "message": "Global change_type=fingerprint_changed observed 3, reaching warning threshold 3."
    }
  ],
  "reasons": [
    "Global change_type=fingerprint_changed observed 3, reaching warning threshold 3."
  ],
  "baseline_valid": true,
  "candidate_valid": true,
  "baseline_errors": [],
  "candidate_errors": [],
  "families": [
    {
      "comparison_key": "{\"issue_type\": \"device_offline\", \"package_name\": \"com.hihonor.calculator\", \"process_name\": \"\", \"scenario_name\": \"cold_start_loop\", \"title\": \"执行期间设备离线\"}",
      "issue_type": "device_offline",
      "package_name": "com.hihonor.calculator",
      "process_name": "",
      "scenario_name": "cold_start_loop",
      "title": "执行期间设备离线",
      "change_type": "fingerprint_changed",
      "left_group_count": 1,
      "right_group_count": 1,
      "left_occurrence_count": 3,
      "right_occurrence_count": 3,
      "left_fingerprints": [
        "ifp_9cc12c0642a31dce"
      ],
      "right_fingerprints": [
        "ifp_50ddcb294dba84e1"
      ],
      "left_sample_event_ids": [
        "issue_c82537bfdc59474e856d67ff6c142435",
        "issue_7a7fc4dfbf6d42968d659dd2b09379f9"
      ],
      "right_sample_event_ids": [
        "issue_c82537bfdc59474e856d67ff6c142435",
        "issue_7a7fc4dfbf6d42968d659dd2b09379f9"
      ],
      "left_sample_events": [
        {
          "event_id": "issue_c82537bfdc59474e856d67ff6c142435",
          "run_id": "run_c32c04baa7f040c984ef448957900c01",
          "task_id": "task_97ea23bccb1b4773930a9a3261576260",
          "task_name": "Extended Artifacts Smoke Cold Start Timeout",
          "instance_id": "instance_c1964d6bc0914af4bf3091cf757bf147",
          "device_id": "192.168.31.99:5555",
          "package_name": "com.hihonor.calculator",
          "scenario_name": "cold_start_loop",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-20T06:27:07.722234",
          "summary": "冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/report/report.md",
          "execution_log_path": "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/artifacts/issue_c82537bfdc59474e856d67ff6c142435/execution.log"
          ],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:192.168.31.99:5555",
            "issue_metadata": {
              "device_id": "192.168.31.99:5555",
              "package_name": "com.hihonor.calculator",
              "template_type": "cold_start_loop"
            }
          }
        },
        {
          "event_id": "issue_7a7fc4dfbf6d42968d659dd2b09379f9",
          "run_id": "run_aee68549d5814b18b6f8d01fbfbe3761",
          "task_id": "task_cea4fb16a2f542119768a9e81431cf8d",
          "task_name": "Extended Artifacts Smoke Cold Start Timeout",
          "instance_id": "instance_14580099b43447fda4ebc28eb30f193c",
          "device_id": "192.168.31.99:5555",
          "package_name": "com.hihonor.calculator",
          "scenario_name": "cold_start_loop",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-20T06:26:00.252911",
          "summary": "冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/report/report.md",
          "execution_log_path": "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/artifacts/issue_7a7fc4dfbf6d42968d659dd2b09379f9/execution.log"
          ],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:192.168.31.99:5555",
            "issue_metadata": {
              "device_id": "192.168.31.99:5555",
              "package_name": "com.hihonor.calculator",
              "template_type": "cold_start_loop"
            }
          }
        }
      ],
      "right_sample_events": [
        {
          "event_id": "issue_c82537bfdc59474e856d67ff6c142435",
          "run_id": "run_c32c04baa7f040c984ef448957900c01",
          "task_id": "task_97ea23bccb1b4773930a9a3261576260",
          "task_name": "Extended Artifacts Smoke Cold Start Timeout",
          "instance_id": "instance_c1964d6bc0914af4bf3091cf757bf147",
          "device_id": "192.168.31.99:5555",
          "package_name": "com.hihonor.calculator",
          "scenario_name": "cold_start_loop",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-20T06:27:07.722234",
          "summary": "冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/report/report.md",
          "execution_log_path": "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/artifacts/issue_c82537bfdc59474e856d67ff6c142435/execution.log"
          ],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:192.168.31.99:5555",
            "issue_metadata": {
              "device_id": "192.168.31.99:5555",
              "package_name": "com.hihonor.calculator",
              "template_type": "cold_start_loop"
            }
          }
        },
        {
          "event_id": "issue_7a7fc4dfbf6d42968d659dd2b09379f9",
          "run_id": "run_aee68549d5814b18b6f8d01fbfbe3761",
          "task_id": "task_cea4fb16a2f542119768a9e81431cf8d",
          "task_name": "Extended Artifacts Smoke Cold Start Timeout",
          "instance_id": "instance_14580099b43447fda4ebc28eb30f193c",
          "device_id": "192.168.31.99:5555",
          "package_name": "com.hihonor.calculator",
          "scenario_name": "cold_start_loop",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-20T06:26:00.252911",
          "summary": "冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/report/report.md",
          "execution_log_path": "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/artifacts/issue_7a7fc4dfbf6d42968d659dd2b09379f9/execution.log"
          ],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:192.168.31.99:5555",
            "issue_metadata": {
              "device_id": "192.168.31.99:5555",
              "package_name": "com.hihonor.calculator",
              "template_type": "cold_start_loop"
            }
          }
        }
      ],
      "notes": [
        "The candidate rule changed fingerprint identities for this family."
      ]
    },
    {
      "comparison_key": "{\"issue_type\": \"device_offline\", \"package_name\": \"com.example.demo\", \"process_name\": \"\", \"scenario_name\": \"monkey\", \"title\": \"执行期间设备离线\"}",
      "issue_type": "device_offline",
      "package_name": "com.example.demo",
      "process_name": "",
      "scenario_name": "monkey",
      "title": "执行期间设备离线",
      "change_type": "fingerprint_changed",
      "left_group_count": 1,
      "right_group_count": 1,
      "left_occurrence_count": 2,
      "right_occurrence_count": 2,
      "left_fingerprints": [
        "ifp_7132016ac7d158a8"
      ],
      "right_fingerprints": [
        "ifp_f4164891f8415147"
      ],
      "left_sample_event_ids": [
        "issue_698ee60fe47144859fed907cd6ffb582",
        "issue_840860e1f385413296345c0022485b4b"
      ],
      "right_sample_event_ids": [
        "issue_698ee60fe47144859fed907cd6ffb582",
        "issue_840860e1f385413296345c0022485b4b"
      ],
      "left_sample_events": [
        {
          "event_id": "issue_698ee60fe47144859fed907cd6ffb582",
          "run_id": "run_a0d485eb673442d2b0641fbcff76fa9a",
          "task_id": "task_0aae5f86ad1942bab107d05f56e14fc2",
          "task_name": "Monkey Stage3 Smoke",
          "instance_id": "instance_df0ad3b5d547422ebda48b2c952a5f54",
          "device_id": "dev-a",
          "package_name": "com.example.demo",
          "scenario_name": "monkey",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-19T11:03:46.754703",
          "summary": "Monkey 模板执行失败：设备 dev-a 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/report/report.md",
          "execution_log_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/artifacts/issue_698ee60fe47144859fed907cd6ffb582/execution.log"
          ],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:dev-a",
            "issue_metadata": {
              "device_id": "dev-a",
              "package_name": "com.example.demo"
            }
          }
        },
        {
          "event_id": "issue_840860e1f385413296345c0022485b4b",
          "run_id": "run_35dd1bd2734b4c77b67e18853fd3668c",
          "task_id": "task_0aae5f86ad1942bab107d05f56e14fc2",
          "task_name": "Monkey Stage3 Smoke",
          "instance_id": "instance_dde860bb2e9b4f66aa53ba288532518e",
          "device_id": "dev-a",
          "package_name": "com.example.demo",
          "scenario_name": "monkey",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-19T10:59:04.236180",
          "summary": "Monkey 模板执行失败：设备 dev-a 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_35dd1bd2734b4c77b67e18853fd3668c/executions/instance_dde860bb2e9b4f66aa53ba288532518e/devices/dev-a/report/report.md",
          "execution_log_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_35dd1bd2734b4c77b67e18853fd3668c/executions/instance_dde860bb2e9b4f66aa53ba288532518e/devices/dev-a/logs/execution.log",
          "artifact_paths": [],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:dev-a",
            "issue_metadata": {
              "device_id": "dev-a",
              "package_name": "com.example.demo"
            }
          }
        }
      ],
      "right_sample_events": [
        {
          "event_id": "issue_698ee60fe47144859fed907cd6ffb582",
          "run_id": "run_a0d485eb673442d2b0641fbcff76fa9a",
          "task_id": "task_0aae5f86ad1942bab107d05f56e14fc2",
          "task_name": "Monkey Stage3 Smoke",
          "instance_id": "instance_df0ad3b5d547422ebda48b2c952a5f54",
          "device_id": "dev-a",
          "package_name": "com.example.demo",
          "scenario_name": "monkey",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-19T11:03:46.754703",
          "summary": "Monkey 模板执行失败：设备 dev-a 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/report/report.md",
          "execution_log_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/artifacts/issue_698ee60fe47144859fed907cd6ffb582/execution.log"
          ],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:dev-a",
            "issue_metadata": {
              "device_id": "dev-a",
              "package_name": "com.example.demo"
            }
          }
        },
        {
          "event_id": "issue_840860e1f385413296345c0022485b4b",
          "run_id": "run_35dd1bd2734b4c77b67e18853fd3668c",
          "task_id": "task_0aae5f86ad1942bab107d05f56e14fc2",
          "task_name": "Monkey Stage3 Smoke",
          "instance_id": "instance_dde860bb2e9b4f66aa53ba288532518e",
          "device_id": "dev-a",
          "package_name": "com.example.demo",
          "scenario_name": "monkey",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-19T10:59:04.236180",
          "summary": "Monkey 模板执行失败：设备 dev-a 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_35dd1bd2734b4c77b67e18853fd3668c/executions/instance_dde860bb2e9b4f66aa53ba288532518e/devices/dev-a/report/report.md",
          "execution_log_path": "runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_35dd1bd2734b4c77b67e18853fd3668c/executions/instance_dde860bb2e9b4f66aa53ba288532518e/devices/dev-a/logs/execution.log",
          "artifact_paths": [],
          "metadata": {
            "run_status": "failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:dev-a",
            "issue_metadata": {
              "device_id": "dev-a",
              "package_name": "com.example.demo"
            }
          }
        }
      ],
      "notes": [
        "The candidate rule changed fingerprint identities for this family."
      ]
    },
    {
      "comparison_key": "{\"issue_type\": \"device_offline\", \"package_name\": \"com.android.settings\", \"process_name\": \"\", \"scenario_name\": \"cold_start_loop\", \"title\": \"执行期间设备离线\"}",
      "issue_type": "device_offline",
      "package_name": "com.android.settings",
      "process_name": "",
      "scenario_name": "cold_start_loop",
      "title": "执行期间设备离线",
      "change_type": "fingerprint_changed",
      "left_group_count": 1,
      "right_group_count": 1,
      "left_occurrence_count": 1,
      "right_occurrence_count": 1,
      "left_fingerprints": [
        "ifp_8b7ecfbe05a8b9d2"
      ],
      "right_fingerprints": [
        "ifp_0c55f871e68eba71"
      ],
      "left_sample_event_ids": [
        "issue_165ebe78222049b785b21c90cb05dd40"
      ],
      "right_sample_event_ids": [
        "issue_165ebe78222049b785b21c90cb05dd40"
      ],
      "left_sample_events": [
        {
          "event_id": "issue_165ebe78222049b785b21c90cb05dd40",
          "run_id": "run_9f6fa582bfa2497f8ef4269372edd056",
          "task_id": "task_b914b5f708a54fc08175afa28358cd54",
          "task_name": "cold_start_loop_failure_smoke_20250719_202930",
          "instance_id": "instance_b7629e04c92241a4ba55e1fc2b1207c8",
          "device_id": "192.168.31.99:5555",
          "package_name": "com.android.settings",
          "scenario_name": "cold_start_loop",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-19T12:29:33.292322",
          "summary": "冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/report/report.md",
          "execution_log_path": "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/artifacts/issue_165ebe78222049b785b21c90cb05dd40/execution.log"
          ],
          "metadata": {
            "run_status": "partial_failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:192.168.31.99:5555",
            "issue_metadata": {
              "device_id": "192.168.31.99:5555",
              "package_name": "com.android.settings",
              "template_type": "cold_start_loop"
            }
          }
        }
      ],
      "right_sample_events": [
        {
          "event_id": "issue_165ebe78222049b785b21c90cb05dd40",
          "run_id": "run_9f6fa582bfa2497f8ef4269372edd056",
          "task_id": "task_b914b5f708a54fc08175afa28358cd54",
          "task_name": "cold_start_loop_failure_smoke_20250719_202930",
          "instance_id": "instance_b7629e04c92241a4ba55e1fc2b1207c8",
          "device_id": "192.168.31.99:5555",
          "package_name": "com.android.settings",
          "scenario_name": "cold_start_loop",
          "issue_type": "device_offline",
          "severity": "high",
          "detected_at": "2025-07-19T12:29:33.292322",
          "summary": "冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。",
          "report_path": "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/report/report.md",
          "execution_log_path": "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/logs/execution.log",
          "artifact_paths": [
            "runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/artifacts/issue_165ebe78222049b785b21c90cb05dd40/execution.log"
          ],
          "metadata": {
            "run_status": "partial_failed",
            "instance_status": "failed",
            "result_level": "unknown",
            "exit_reason": "device_offline",
            "issue_title": "执行期间设备离线",
            "process_name": "",
            "raw_key": "device_offline:192.168.31.99:5555",
            "issue_metadata": {
              "device_id": "192.168.31.99:5555",
              "package_name": "com.android.settings",
              "template_type": "cold_start_loop"
            }
          }
        }
      ],
      "notes": [
        "The candidate rule changed fingerprint identities for this family."
      ]
    }
  ]
}
```
