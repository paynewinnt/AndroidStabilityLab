# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_3647d2f97da64faa820931fd75bf97e8
- instance_id: instance_b053ff84bf454128945d56b3cf0809fc
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 2 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T04:02:48.982006",
  "persisted": true,
  "system": {
    "cpu_usage": 10.0,
    "cpu_user": 6.7,
    "cpu_breakdown": {
      "total": 10.0,
      "user": 6.7,
      "kernel": 3.3,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 3250.72,
    "memory_usage_percent": 42.97,
    "memory_percent": 42.97,
    "memory_system_used": 2449.43,
    "battery_level": 100.0,
    "network_rx_total": 2602.33,
    "network_tx_total": 1169.32,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "load_1min": 23.26,
    "load_5min": 23.17,
    "load_15min": 23.01,
    "perfetto_duration_ms": 0
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "cpu_usage": 0.0,
      "memory_pss": 43.63,
      "memory_java": 8.84,
      "memory_native": 14.59,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
      "top_memory_percent": 1.7,
      "top_memory_res_kb": 103424.0,
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
      "captured_at": "2025-07-25T04:02:48.982064",
      "local_trace_path": "",
      "remote_trace_path": "/data/local/tmp/task_1385ed1c97994b14a3757ac52f929db3_instance_b053ff84bf454128945d56b3cf0809fc.perfetto-trace",
      "capture_mode": "remote_file",
      "trace_size_bytes": null,
      "duration_ms": 0,
      "config_path": "",
      "stdout_tail": "",
      "stderr_tail": "-:19:7 error: No field named \"cpufreq_period_ms\" in proto SysStatsConfig\n      cpufreq_period_ms: 1000\n      ^~~~~~~~~~~~~~~~~ \n[845.200] perfetto_cmd.cc:522     The trace config is invalid, bailing out.\n",
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
