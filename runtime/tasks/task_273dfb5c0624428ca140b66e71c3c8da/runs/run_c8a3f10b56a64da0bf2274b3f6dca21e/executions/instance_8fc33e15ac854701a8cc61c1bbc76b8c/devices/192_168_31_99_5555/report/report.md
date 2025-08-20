# Execution Summary

- task_id: task_273dfb5c0624428ca140b66e71c3c8da
- task_name: foreground_background_loop_smoke_com_hihonor_calculator_20250725_024111
- run_id: run_c8a3f10b56a64da0bf2274b3f6dca21e
- instance_id: instance_8fc33e15ac854701a8cc61c1bbc76b8c
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
