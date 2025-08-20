# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_dc5da10ee6c948aabaca81df45beb567
- instance_id: instance_1c5e8a7d3ceb48209a0a2b7650c6ceec
- device_id: AFQJVB2211008014
- status: failed
- monitoring_error: none
- scenario_note: 前后台切换模板执行失败：设备 AFQJVB2211008014 当前不可用或未连接。
- issue_count: 1
- artifact_count: 2

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T03:46:56.049273",
  "persisted": true,
  "system": {
    "network_rx_total": 0.0,
    "network_tx_total": 0.0,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "perfetto_duration_ms": 0
  },
  "apps": [
    {
      "app_package": "com.hihonor.calculator",
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
      "captured_at": "2025-07-25T03:46:56.049322",
      "local_trace_path": "",
      "remote_trace_path": "/data/local/tmp/task_1385ed1c97994b14a3757ac52f929db3_instance_1c5e8a7d3ceb48209a0a2b7650c6ceec.perfetto-trace",
      "trace_size_bytes": null,
      "duration_ms": 0,
      "config_path": "",
      "stdout_tail": "",
      "stderr_tail": "enn/Develop/env/platform-tools/adb\n07-25 11:46:56.071 87307 16174134 I adb     : main.cpp:66 Running on Darwin 25.3.0 (arm64)\n07-25 11:46:56.071 87307 16174134 I adb     : main.cpp:66 \n07-25 11:46:56.600 87307 16174134 F adb     : main.cpp:165 could not install *smartsocket* listener: Operation not permitted\n\n* failed to start daemon\nadb: error: failed to get feature set: cannot connect to daemon\n",
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
- attempt 1: status=failed, exit_reason=device_offline, retryable=True, retry_category=device_offline, note=前后台切换模板执行失败：设备 AFQJVB2211008014 当前不可用或未连接。

## Cleanup

- action=force_stop, reason=final scenario failure after 1 attempt(s), return_code=1, timed_out=False

## Issues

- [device_offline] 执行期间设备离线 (high)
  - summary: 前后台切换模板执行失败：设备 AFQJVB2211008014 当前不可用或未连接。

## Artifacts

- [execution_log] runtime/tasks/task_1385ed1c97994b14a3757ac52f929db3/runs/run_dc5da10ee6c948aabaca81df45beb567/executions/instance_1c5e8a7d3ceb48209a0a2b7650c6ceec/devices/AFQJVB2211008014/artifacts/issue_587b04c0c2c54b25b26341ff3ed9eea6/execution.log
  - issue_id: issue_587b04c0c2c54b25b26341ff3ed9eea6
  - capture_status: success
  - size_bytes: 287
- [performance_snapshot] runtime/tasks/task_1385ed1c97994b14a3757ac52f929db3/runs/run_dc5da10ee6c948aabaca81df45beb567/executions/instance_1c5e8a7d3ceb48209a0a2b7650c6ceec/devices/AFQJVB2211008014/artifacts/issue_587b04c0c2c54b25b26341ff3ed9eea6/monitoring_snapshot.json
  - issue_id: issue_587b04c0c2c54b25b26341ff3ed9eea6
  - capture_status: success
  - size_bytes: 1707

## Artifact Capture Notes

- bugreport 抓取跳过：设备 AFQJVB2211008014 当前不可用。
- logcat 抓取跳过：设备 AFQJVB2211008014 当前不可用。
- traces 抓取跳过：设备 AFQJVB2211008014 当前不可用。
- tombstone 抓取跳过：设备 AFQJVB2211008014 当前不可用。

## Scenario Result

```json
{
  "template_type": "foreground_background_loop",
  "device_id": "AFQJVB2211008014"
}
```
