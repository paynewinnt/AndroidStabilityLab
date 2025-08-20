# Execution Summary

- task_id: task_798adf9a0acb497a9efdb40e9805b5b4
- task_name: web_foreground_background_smoke_com_hihonor_calculator_20250725_025257
- run_id: run_1209f30a96844e5ea2270f9a32618785
- instance_id: instance_edb14d34009b4edab44cea63865a913e
- device_id: 192.168.31.99:5555
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 2 轮。

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=success, exit_reason=completed, retryable=False, retry_category=completed, note=前后台切换模板执行完成，共执行 2 轮。

## Scenario Result

```json
{
  "template_type": "foreground_background_loop",
  "launch_target": "com.hihonor.calculator/.Calculator",
  "loop_summary": {
    "configured_loops": 2,
    "completed_loops": 2,
    "iterations": [
      {
        "loop_index": 1,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 2,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      }
    ]
  }
}
```
