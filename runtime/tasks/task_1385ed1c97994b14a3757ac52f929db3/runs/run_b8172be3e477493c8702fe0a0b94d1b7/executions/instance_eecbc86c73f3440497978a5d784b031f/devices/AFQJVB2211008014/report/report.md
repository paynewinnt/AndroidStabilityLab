# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_b8172be3e477493c8702fe0a0b94d1b7
- instance_id: instance_eecbc86c73f3440497978a5d784b031f
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 2 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T03:48:23.354838",
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
    "memory_system_available": 3258.7,
    "memory_usage_percent": 42.83,
    "memory_percent": 42.83,
    "memory_system_used": 2441.45,
    "battery_level": 100.0,
    "network_rx_total": 2121.06,
    "network_tx_total": 1001.68,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "load_1min": 23.57,
    "load_5min": 22.92,
    "load_15min": 22.83
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "memory_pss": 37.42,
      "memory_java": 2.78,
      "memory_native": 14.61,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
      "top_memory_percent": 1.6,
      "top_memory_res_kb": 93184.0,
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
