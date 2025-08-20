# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_0f1985f7850f42b78748c23f7bf48cd3
- instance_id: instance_6fec6962bb514576a10c6fc491d42218
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 2 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T03:48:34.818844",
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
    "memory_system_available": 3246.66,
    "memory_usage_percent": 43.04,
    "memory_percent": 43.04,
    "memory_system_used": 2453.49,
    "battery_level": 100.0,
    "network_rx_total": 2234.96,
    "network_tx_total": 1055.32,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "load_1min": 23.9,
    "load_5min": 23.03,
    "load_15min": 22.86,
    "perfetto_duration_ms": 0
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "memory_pss": 43.81,
      "memory_java": 8.89,
      "memory_native": 14.71,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
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
    "backend": "perfetto",
    "profile_name": "perfetto",
    "trace_artifact_path": "",
    "normalized_stats": {
      "trace_status": "pull_failed",
      "trace_size_bytes": null,
      "duration_ms": 0
    },
    "best_effort_degraded": true,
    "perfetto": {
      "trace_status": "pull_failed",
      "captured_at": "2025-07-25T03:48:34.818890",
      "local_trace_path": "",
      "remote_trace_path": "/data/local/tmp/task_1385ed1c97994b14a3757ac52f929db3_instance_6fec6962bb514576a10c6fc491d42218.perfetto-trace",
      "trace_size_bytes": null,
      "duration_ms": 0,
      "config_path": "",
      "stdout_tail": "",
      "stderr_tail": "adb: error: failed to stat remote object '/data/local/tmp/task_1385ed1c97994b14a3757ac52f929db3_instance_6fec6962bb514576a10c6fc491d42218.perfetto-trace': No such file or directory\n",
      "best_effort_degraded": true,
      "degraded_reason": "trace pull failed after best-effort capture"
    },
    "artifacts": []
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
