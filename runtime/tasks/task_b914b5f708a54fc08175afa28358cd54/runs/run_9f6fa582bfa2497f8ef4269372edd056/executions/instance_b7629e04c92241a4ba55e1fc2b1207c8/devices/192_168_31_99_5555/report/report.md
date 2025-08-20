# Execution Summary

- task_id: task_b914b5f708a54fc08175afa28358cd54
- task_name: cold_start_loop_failure_smoke_20250719_202930
- run_id: run_9f6fa582bfa2497f8ef4269372edd056
- instance_id: instance_b7629e04c92241a4ba55e1fc2b1207c8
- device_id: 192.168.31.99:5555
- status: failed
- monitoring_error: none
- scenario_note: 冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。
- issue_count: 1
- artifact_count: 1

## Issues

- [device_offline] 执行期间设备离线 (high)
  - summary: 冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。

## Artifacts

- [execution_log] runtime/tasks/task_b914b5f708a54fc08175afa28358cd54/runs/run_9f6fa582bfa2497f8ef4269372edd056/executions/instance_b7629e04c92241a4ba55e1fc2b1207c8/devices/192_168_31_99_5555/artifacts/issue_165ebe78222049b785b21c90cb05dd40/execution.log
  - issue_id: issue_165ebe78222049b785b21c90cb05dd40
  - capture_status: success
  - size_bytes: 176

## Artifact Capture Notes

- logcat 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- traces 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- tombstone 抓取跳过：设备 192.168.31.99:5555 当前不可用。

## Scenario Result

```json
{
  "device_id": "192.168.31.99:5555",
  "package_name": "com.android.settings",
  "template_type": "cold_start_loop"
}
```
