# Execution Summary

- task_id: task_cea4fb16a2f542119768a9e81431cf8d
- task_name: Extended Artifacts Smoke Cold Start Timeout
- run_id: run_aee68549d5814b18b6f8d01fbfbe3761
- instance_id: instance_14580099b43447fda4ebc28eb30f193c
- device_id: 192.168.31.99:5555
- status: failed
- monitoring_error: none
- scenario_note: 冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。
- issue_count: 1
- artifact_count: 1

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=failed, exit_reason=device_offline, retryable=True, retry_category=device_offline, note=冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。

## Cleanup

- action=force_stop, reason=final scenario failure after 1 attempt(s), return_code=1, timed_out=False

## Issues

- [device_offline] 执行期间设备离线 (high)
  - summary: 冷启动循环执行失败：设备 192.168.31.99:5555 当前不可用或未连接。

## Artifacts

- [execution_log] runtime/tasks/task_cea4fb16a2f542119768a9e81431cf8d/runs/run_aee68549d5814b18b6f8d01fbfbe3761/executions/instance_14580099b43447fda4ebc28eb30f193c/devices/192_168_31_99_5555/artifacts/issue_7a7fc4dfbf6d42968d659dd2b09379f9/execution.log
  - issue_id: issue_7a7fc4dfbf6d42968d659dd2b09379f9
  - capture_status: success
  - size_bytes: 289

## Artifact Capture Notes

- bugreport 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- logcat 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- traces 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- tombstone 抓取跳过：设备 192.168.31.99:5555 当前不可用。

## Scenario Result

```json
{
  "device_id": "192.168.31.99:5555",
  "package_name": "com.hihonor.calculator",
  "template_type": "cold_start_loop"
}
```
