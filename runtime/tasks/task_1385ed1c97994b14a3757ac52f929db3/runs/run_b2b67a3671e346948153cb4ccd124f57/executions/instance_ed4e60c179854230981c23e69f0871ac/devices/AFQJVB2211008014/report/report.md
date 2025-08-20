# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_b2b67a3671e346948153cb4ccd124f57
- instance_id: instance_ed4e60c179854230981c23e69f0871ac
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 2 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T04:04:49.132781",
  "persisted": true,
  "system": {
    "timestamp": "2025-07-25T04:04:49.132781",
    "cpu_usage": 14.46,
    "battery_level": 100.0,
    "battery_temperature": 27.8
  },
  "apps": [
    {
      "package_name": "com.hihonor.calculator",
      "timestamp": "2025-07-25T04:04:49.132781",
      "cpu_usage": 0.0,
      "memory_pss": 43.35,
      "rx_bytes": 0.0,
      "tx_bytes": 0.0,
      "fps": 0.0,
      "jank_frames": 0.0
    }
  ],
  "metadata": {
    "backend": "solox",
    "profile_name": "solox",
    "raw_targets": [
      "cpu",
      "memory",
      "network",
      "fps",
      "battery"
    ]
  }
}
```

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
