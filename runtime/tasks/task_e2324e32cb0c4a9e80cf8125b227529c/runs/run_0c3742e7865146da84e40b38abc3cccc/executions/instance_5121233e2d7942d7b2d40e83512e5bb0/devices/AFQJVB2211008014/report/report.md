# Execution Summary

- task_id: task_e2324e32cb0c4a9e80cf8125b227529c
- task_name: perfetto_compat_full_metrics_1min_com_hihonor_calculator_20250727
- run_id: run_0c3742e7865146da84e40b38abc3cccc
- instance_id: instance_5121233e2d7942d7b2d40e83512e5bb0
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: 前后台切换模板执行完成，共执行 12 轮。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-27T13:28:39.526596",
  "persisted": true,
  "system": {
    "cpu_usage": 5.5,
    "cpu_user": 2.7,
    "cpu_breakdown": {
      "total": 5.5,
      "user": 2.7,
      "kernel": 2.7,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 3578.07,
    "memory_usage_percent": 37.23,
    "memory_percent": 37.23,
    "memory_system_used": 2122.07,
    "battery_level": 100.0,
    "network_rx_total": 11011.97,
    "network_tx_total": 5073.67,
    "network_rx": 0,
    "network_tx": 0,
    "network": 0,
    "load_1min": 22.85,
    "load_5min": 22.81,
    "load_15min": 22.67,
    "perfetto_trace_size_bytes": 188680,
    "perfetto_duration_ms": 0
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
      "cpu_usage": 1.7,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 0.0,
      "top_memory_percent": 1.3,
      "top_memory_res_kb": 77824.0,
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
    "trace_artifact_path": "runtime/tasks/task_e2324e32cb0c4a9e80cf8125b227529c/runs/run_0c3742e7865146da84e40b38abc3cccc/executions/instance_5121233e2d7942d7b2d40e83512e5bb0/devices/AFQJVB2211008014/monitoring/task_e2324e32cb0c4a9e80cf8125b227529c_instance_5121233e2d7942d7b2d40e83512e5bb0.perfetto-trace",
    "normalized_stats": {
      "trace_status": "captured",
      "trace_size_bytes": 188680,
      "duration_ms": 0
    },
    "best_effort_degraded": false,
    "perfetto": {
      "trace_status": "captured",
      "captured_at": "2025-07-27T13:26:54.960547",
      "local_trace_path": "runtime/tasks/task_e2324e32cb0c4a9e80cf8125b227529c/runs/run_0c3742e7865146da84e40b38abc3cccc/executions/instance_5121233e2d7942d7b2d40e83512e5bb0/devices/AFQJVB2211008014/monitoring/task_e2324e32cb0c4a9e80cf8125b227529c_instance_5121233e2d7942d7b2d40e83512e5bb0.perfetto-trace",
      "remote_trace_path": "/data/local/tmp/task_e2324e32cb0c4a9e80cf8125b227529c_instance_5121233e2d7942d7b2d40e83512e5bb0.perfetto-trace",
      "capture_mode": "stdout_fallback",
      "trace_size_bytes": 188680,
      "duration_ms": 0,
      "config_path": "",
      "stdout_tail": "captured perfetto stdout",
      "stderr_tail": "[682.482] perfetto_cmd.cc:940     Failed to open /data/local/tmp/task_e2324e32cb0c4a9e80cf8125b227529c_instance_5121233e2d7942d7b2d40e83512e5bb0.perfetto-trace. If you get permission denied in /data/misc/perfetto-traces, the file might have been created by another user, try deleting it first. (errno: 13, Permission denied)\n",
      "best_effort_degraded": false,
      "degraded_reason": "remote trace pull failed; captured trace from stdout fallback"
    },
    "artifacts": [
      {
        "artifact_type": "perfetto_trace",
        "file_path": "runtime/tasks/task_e2324e32cb0c4a9e80cf8125b227529c/runs/run_0c3742e7865146da84e40b38abc3cccc/executions/instance_5121233e2d7942d7b2d40e83512e5bb0/devices/AFQJVB2211008014/monitoring/task_e2324e32cb0c4a9e80cf8125b227529c_instance_5121233e2d7942d7b2d40e83512e5bb0.perfetto-trace",
        "capture_reason": "perfetto trace sidecar",
        "capture_message": "captured",
        "metadata": {
          "backend": "perfetto",
          "remote_trace_path": "/data/local/tmp/task_e2324e32cb0c4a9e80cf8125b227529c_instance_5121233e2d7942d7b2d40e83512e5bb0.perfetto-trace",
          "trace_size_bytes": 188680
        }
      }
    ]
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
