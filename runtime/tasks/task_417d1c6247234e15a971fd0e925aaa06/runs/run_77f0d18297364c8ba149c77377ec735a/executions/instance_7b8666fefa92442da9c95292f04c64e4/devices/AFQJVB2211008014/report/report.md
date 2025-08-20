# Execution Summary

- task_id: task_417d1c6247234e15a971fd0e925aaa06
- task_name: real_device_long_run_smoke_foreground_background_loop_com_hihonor_calculator_20250726_172938
- run_id: run_77f0d18297364c8ba149c77377ec735a
- instance_id: instance_7b8666fefa92442da9c95292f04c64e4
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 10 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-26T09:34:51.263943",
  "persisted": true,
  "system": {
    "cpu_usage": 11.0,
    "cpu_user": 6.5,
    "cpu_breakdown": {
      "total": 11.0,
      "user": 6.5,
      "kernel": 4.4,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 3274.94,
    "memory_usage_percent": 42.55,
    "memory_percent": 42.55,
    "memory_system_used": 2425.21,
    "battery_level": 100.0,
    "network_rx_total": 5910.9,
    "network_tx_total": 2722.92,
    "network_rx": 0,
    "network_tx": 0,
    "network": 0,
    "load_1min": 23.25,
    "load_5min": 23.24,
    "load_15min": 23.11
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "cpu_usage": 0.0,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
      "top_memory_percent": 0.9,
      "top_memory_res_kb": 55296.0,
      "app_info": {
        "package_name": "com.hihonor.calculator",
        "app_name": "com.hihonor.calculator"
      },
      "package_name": "com.hihonor.calculator"
    }
  ],
  "metadata": {
    "backend": "legacy_adb"
  }
}
```

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=success, exit_reason=completed, retryable=False, retry_category=completed, note=前后台切换模板执行完成，共执行 10 轮。

## Scenario Result

```json
{
  "template_type": "foreground_background_loop",
  "launch_target": "com.hihonor.calculator/.Calculator",
  "loop_summary": {
    "configured_loops": 10,
    "completed_loops": 10,
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
      },
      {
        "loop_index": 3,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 4,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 5,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 6,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 7,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 8,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 9,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 10,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      }
    ]
  }
}
```
