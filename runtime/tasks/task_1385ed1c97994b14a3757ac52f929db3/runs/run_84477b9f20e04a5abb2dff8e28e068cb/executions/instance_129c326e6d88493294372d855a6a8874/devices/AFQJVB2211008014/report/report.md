# Execution Summary

- task_id: task_1385ed1c97994b14a3757ac52f929db3
- task_name: 前后台切换_20250725_114552
- run_id: run_84477b9f20e04a5abb2dff8e28e068cb
- instance_id: instance_129c326e6d88493294372d855a6a8874
- device_id: AFQJVB2211008014
- status: failed
- monitoring_error: none
- scenario_note: 前后台切换模板执行失败：设备 AFQJVB2211008014 当前不可用或未连接。
- issue_count: 1
- artifact_count: 2

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T03:46:32.699929",
  "persisted": true,
  "system": {
    "network_rx_total": 0.0,
    "network_tx_total": 0.0,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0
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
    "backend": "legacy_adb"
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

- [execution_log] runtime/tasks/task_1385ed1c97994b14a3757ac52f929db3/runs/run_84477b9f20e04a5abb2dff8e28e068cb/executions/instance_129c326e6d88493294372d855a6a8874/devices/AFQJVB2211008014/artifacts/issue_4601fff6f80c4b9288a4ca8acf745dce/execution.log
  - issue_id: issue_4601fff6f80c4b9288a4ca8acf745dce
  - capture_status: success
  - size_bytes: 287
- [performance_snapshot] runtime/tasks/task_1385ed1c97994b14a3757ac52f929db3/runs/run_84477b9f20e04a5abb2dff8e28e068cb/executions/instance_129c326e6d88493294372d855a6a8874/devices/AFQJVB2211008014/artifacts/issue_4601fff6f80c4b9288a4ca8acf745dce/monitoring_snapshot.json
  - issue_id: issue_4601fff6f80c4b9288a4ca8acf745dce
  - capture_status: success
  - size_bytes: 506

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
