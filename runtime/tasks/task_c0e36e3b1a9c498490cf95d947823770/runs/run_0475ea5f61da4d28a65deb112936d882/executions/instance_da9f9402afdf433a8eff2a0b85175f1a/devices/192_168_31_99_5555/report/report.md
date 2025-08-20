# Execution Summary

- task_id: task_c0e36e3b1a9c498490cf95d947823770
- task_name: CLI Query Smoke Cold Start Timeout
- run_id: run_0475ea5f61da4d28a65deb112936d882
- instance_id: instance_da9f9402afdf433a8eff2a0b85175f1a
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

- [execution_log] runtime/tasks/task_c0e36e3b1a9c498490cf95d947823770/runs/run_0475ea5f61da4d28a65deb112936d882/executions/instance_da9f9402afdf433a8eff2a0b85175f1a/devices/192_168_31_99_5555/artifacts/issue_af9cc47ca1fd47ddbd4bc6d25cda27cf/execution.log
  - issue_id: issue_af9cc47ca1fd47ddbd4bc6d25cda27cf
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
