# Execution Summary

- task_id: task_0749e973f4524550967b73c74049f648
- task_name: cold_start_loop_midrun_disconnect_com_android_settings_20250719_203541
- run_id: run_bb48527ea5964384abcf58b67a980fe0
- instance_id: instance_ec1b5a573fbb4b5fb726ab7b486b449c
- device_id: 192.168.31.99:5555
- status: failed
- monitoring_error: none
- scenario_note: 冷启动循环第 2 轮启动失败。
- issue_count: 1
- artifact_count: 1

## Startup Summary

- configured_loops: 6
- completed_loops: 2
- successful_loops: 1
- average_wait_time_ms: 401.0
- min_wait_time_ms: 401
- max_wait_time_ms: 401
- startup_timeout_ms: 10000
- launch_target: com.android.settings/.HWSettings
- iteration 1: status=success, wait_time_ms=401, total_time_ms=389, this_time_ms=None
- iteration 2: status=failed, wait_time_ms=None, total_time_ms=None, this_time_ms=None

## Issues

- [startup_failure] 冷启动失败 (high)
  - summary: 第 2 轮 启动失败：return code 1

## Artifacts

- [execution_log] runtime/tasks/task_0749e973f4524550967b73c74049f648/runs/run_bb48527ea5964384abcf58b67a980fe0/executions/instance_ec1b5a573fbb4b5fb726ab7b486b449c/devices/192_168_31_99_5555/artifacts/issue_51c1c16ccd3846dd9066643fcebf5e06/execution.log
  - issue_id: issue_51c1c16ccd3846dd9066643fcebf5e06
  - capture_status: success
  - size_bytes: 594

## Artifact Capture Notes

- logcat 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- traces 抓取跳过：设备 192.168.31.99:5555 当前不可用。
- tombstone 抓取跳过：设备 192.168.31.99:5555 当前不可用。

## Scenario Result

```json
{
  "template_type": "cold_start_loop",
  "package_name": "com.android.settings",
  "process_name": "com.android.settings",
  "launch_target": "com.android.settings/.HWSettings",
  "command": [
    "adb",
    "-s",
    "192.168.31.99:5555",
    "shell",
    "am",
    "start",
    "-W",
    "-n",
    "com.android.settings/.HWSettings"
  ],
  "stdout_tail": "",
  "stderr_tail": "adb: device '192.168.31.99:5555' not found",
  "startup_failure": true,
  "startup_failure_kind": "startup_failure",
  "startup_failure_loop": 2,
  "startup_failure_reason": "return code 1",
  "startup_summary": {
    "configured_loops": 6,
    "completed_loops": 2,
    "successful_loops": 1,
    "failed_loop": 2,
    "timed_out_loop": null,
    "launch_wait_ms": 1000,
    "interval_ms": 2000,
    "startup_timeout_ms": 10000,
    "kill_before_launch": true,
    "launch_target": "com.android.settings/.HWSettings",
    "average_wait_time_ms": 401.0,
    "min_wait_time_ms": 401,
    "max_wait_time_ms": 401,
    "iterations": [
      {
        "iteration": 1,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 401,
        "total_time_ms": 389,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 389\nWaitTime: 401\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 2,
        "status": "failed",
        "return_code": 1,
        "wait_time_ms": null,
        "total_time_ms": null,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "",
        "stderr_tail": "adb: device '192.168.31.99:5555' not found"
      }
    ]
  }
}
```
