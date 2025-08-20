# Execution Summary

- task_id: task_7ef38f9955d94aefb5965bb23454bd97
- task_name: web_standby_wake_smoke_com_hihonor_calculator_20250725_031111
- run_id: run_5f035175a61842c4854f5972900a081e
- instance_id: instance_b0f1766e5a7c40b8a3534f0284d979ba
- device_id: 192.168.31.99:5555
- status: success
- monitoring_error: none
- scenario_note: 待机唤醒循环模板执行完成，共执行 1 轮。

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=success, exit_reason=completed, retryable=False, retry_category=completed, note=待机唤醒循环模板执行完成，共执行 1 轮。

## Scenario Result

```json
{
  "template_type": "standby_wake_loop",
  "loop_summary": {
    "configured_loops": 1,
    "completed_loops": 1,
    "iterations": [
      {
        "loop_index": 1,
        "status": "completed",
        "unlock_attempted": false
      }
    ]
  }
}
```
