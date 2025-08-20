# Execution Summary

- task_id: task_97ea23bccb1b4773930a9a3261576260
- task_name: Extended Artifacts Smoke Cold Start Timeout
- run_id: run_c32c04baa7f040c984ef448957900c01
- instance_id: instance_c1964d6bc0914af4bf3091cf757bf147
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

- [execution_log] runtime/tasks/task_97ea23bccb1b4773930a9a3261576260/runs/run_c32c04baa7f040c984ef448957900c01/executions/instance_c1964d6bc0914af4bf3091cf757bf147/devices/192_168_31_99_5555/artifacts/issue_c82537bfdc59474e856d67ff6c142435/execution.log
  - issue_id: issue_c82537bfdc59474e856d67ff6c142435
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
