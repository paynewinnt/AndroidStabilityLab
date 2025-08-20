# Execution Summary

- task_id: task_711f95fb7be74bda83fa7d53f17e69b4
- task_name: perfetto_full_metrics_1min_com_hihonor_calculator_20250727
- run_id: run_176e3c4350c24e21bdd062cf05101f55
- instance_id: instance_6c4aab22a8104e1387907f2ad054a85c
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 12 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-27T13:22:19.733944",
  "persisted": true,
  "system": {
    "cpu_usage": 5.4,
    "cpu_user": 2.8,
    "cpu_breakdown": {
      "total": 5.4,
      "user": 2.8,
      "kernel": 2.6,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 3667.93,
    "memory_usage_percent": 35.65,
    "memory_percent": 35.65,
    "memory_system_used": 2032.21,
    "battery_level": 100.0,
    "network_rx_total": 10920.48,
    "network_tx_total": 5043.01,
    "network_rx": 0,
    "network_tx": 0,
    "network": 0,
    "load_1min": 23.52,
    "load_5min": 22.97,
    "load_15min": 22.66,
    "perfetto_duration_ms": 0
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "cpu_usage": 2.0,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
      "top_memory_percent": 1.3,
      "top_memory_res_kb": 78848.0,
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
      "captured_at": "2025-07-27T13:20:35.382223",
      "local_trace_path": "",
      "remote_trace_path": "/data/local/tmp/task_711f95fb7be74bda83fa7d53f17e69b4_instance_6c4aab22a8104e1387907f2ad054a85c.perfetto-trace",
      "capture_mode": "remote_file",
      "trace_size_bytes": null,
      "duration_ms": 0,
      "config_path": "",
      "stdout_tail": "",
      "stderr_tail": "-:49:3 error: No field named \"network_packet_trace_config\" in proto DataSource\n  network_packet_trace_config {\n  ^~~~~~~~~~~~~~~~~~~~~~~~~~~ \n-:50:5 error: No field named \"poll_ms\" in proto DataSource\n    poll_ms: 5000\n    ^~~~~~~ \n[302.797] perfetto_cmd.cc:522     The trace config is invalid, bailing out.\n",
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
- attempt 1: status=success, exit_reason=completed, retryable=False, retry_category=completed, note=前后台切换模板执行完成，共执行 12 轮。

## Scenario Result

```json
{
  "template_type": "foreground_background_loop",
  "launch_target": "com.hihonor.calculator/.Calculator",
  "loop_summary": {
    "configured_loops": 12,
    "completed_loops": 12,
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
      },
      {
        "loop_index": 11,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      },
      {
        "loop_index": 12,
        "status": "completed",
        "launch_attempts": 1,
        "background_attempts": 1,
        "recovered_after_disconnect": false
      }
    ]
  }
}
```
