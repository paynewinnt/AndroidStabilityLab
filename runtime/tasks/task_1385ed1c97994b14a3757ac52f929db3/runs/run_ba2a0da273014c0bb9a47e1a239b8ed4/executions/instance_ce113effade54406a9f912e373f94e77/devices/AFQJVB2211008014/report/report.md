# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_ba2a0da273014c0bb9a47e1a239b8ed4
- instance_id: instance_ce113effade54406a9f912e373f94e77
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 2 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T03:48:29.129677",
  "persisted": true,
  "system": {
    "cpu_usage": 6.5,
    "cpu_user": 4.5,
    "cpu_breakdown": {
      "total": 6.5,
      "user": 4.5,
      "kernel": 2.0,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 3259.68,
    "memory_usage_percent": 42.81,
    "memory_percent": 42.81,
    "memory_system_used": 2440.47,
    "battery_level": 100.0,
    "network_rx_total": 2199.13,
    "network_tx_total": 1030.7,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "load_1min": 23.6,
    "load_5min": 22.94,
    "load_15min": 22.83
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "memory_pss": 43.67,
      "memory_java": 8.83,
      "memory_native": 14.62,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 2.6,
      "top_memory_percent": 1.7,
      "top_memory_res_kb": 102400.0,
      "app_info": {
        "package_name": "com.hihonor.calculator",
        "app_name": "com.hihonor.calculator"
      },
      "package_name": "com.hihonor.calculator"
    }
  ],
  "metadata": {
    "backend": "legacy_adb",
    "profile_name": "solox",
    "warnings": [
      "metrics backend 'solox' unavailable, falling back to legacy_adb: SoloX Python package is unavailable. Install it with `pip install -U solox`."
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
