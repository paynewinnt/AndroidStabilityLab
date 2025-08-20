# Execution Summary

- task_id: task_596b976db93641a9add989f18ca25fc8
- task_name: reboot_loop_smoke_com_hihonor_calculator_20250725_031142
- run_id: run_240cb27b06cc490686d4f4f6b680922c
- instance_id: instance_a7864f35e7654ba8b76622f2fc43819e
- device_id: 192.168.31.99:5555
- status: failed
- monitoring_error: none
- scenario_note: 重启循环模板第 1 轮等待设备恢复超时。
- issue_count: 1
- artifact_count: 1

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=failed, exit_reason=device_offline, retryable=True, retry_category=device_offline, note=重启循环模板第 1 轮等待设备恢复超时。

## Cleanup

- action=force_stop, reason=final scenario failure after 1 attempt(s), return_code=1, timed_out=False

## Issues

- [device_offline] 执行期间设备离线 (high)
  - summary: 重启循环模板第 1 轮等待设备恢复超时。

## Artifacts

- [execution_log] runtime/tasks/task_596b976db93641a9add989f18ca25fc8/runs/run_240cb27b06cc490686d4f4f6b680922c/executions/instance_a7864f35e7654ba8b76622f2fc43819e/devices/192_168_31_99_5555/artifacts/issue_c8563584aa0a48f1aa3669f36923dd0f/execution.log
  - issue_id: issue_c8563584aa0a48f1aa3669f36923dd0f
  - capture_status: success
  - size_bytes: 8723

## Artifact Capture Notes

- bugreport 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- logcat 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- traces 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- tombstone 抓取跳过：设备 192.168.31.99:5555 当前不可用。

## Scenario Result

```json
{
  "template_type": "reboot_loop",
  "iterations": [],
  "failed_loop": 1
}
```
