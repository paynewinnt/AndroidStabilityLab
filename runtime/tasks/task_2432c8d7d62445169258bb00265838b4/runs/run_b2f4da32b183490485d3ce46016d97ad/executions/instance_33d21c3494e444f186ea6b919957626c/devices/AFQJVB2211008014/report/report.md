# Execution Summary

- task_id: task_2432c8d7d62445169258bb00265838b4
- task_name: real_device_long_run_smoke_foreground_background_loop_com_hihonor_calculator_20250726_173505
- run_id: run_b2f4da32b183490485d3ce46016d97ad
- instance_id: instance_33d21c3494e444f186ea6b919957626c
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 10 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-26T09:58:03.719533",
  "persisted": true,
  "system": {
    "cpu_usage": 11.0,
    "cpu_user": 7.0,
    "cpu_breakdown": {
      "total": 11.0,
      "user": 7.0,
      "kernel": 4.7,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 3335.12,
    "memory_usage_percent": 41.49,
    "memory_percent": 41.49,
    "memory_system_used": 2365.03,
    "battery_level": 100.0,
    "network_rx_total": 6606.64,
    "network_tx_total": 3110.03,
    "network_rx": 0,
    "network_tx": 0,
    "network": 0,
    "load_1min": 24.06,
    "load_5min": 24.14,
    "load_15min": 23.72
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "cpu_usage": 2.1,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
      "top_memory_percent": 0.9,
      "top_memory_res_kb": 56320.0,
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
