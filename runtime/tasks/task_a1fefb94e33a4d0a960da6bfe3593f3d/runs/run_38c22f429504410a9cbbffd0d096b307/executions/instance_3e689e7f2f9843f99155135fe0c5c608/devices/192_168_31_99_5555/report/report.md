# Execution Summary

- task_id: task_a1fefb94e33a4d0a960da6bfe3593f3d
- task_name: cold_start_loop_multi_device_smoke_com_android_settings_20250719_202617
- run_id: run_38c22f429504410a9cbbffd0d096b307
- instance_id: instance_3e689e7f2f9843f99155135fe0c5c608
- device_id: 192.168.31.99:5555
- status: success
- monitoring_error: none
- scenario_note: 冷启动循环执行完成，共执行 3 轮，平均启动耗时 116.0 ms。

## Startup Summary

- configured_loops: 3
- completed_loops: 3
- successful_loops: 3
- average_wait_time_ms: 116.0
- min_wait_time_ms: 10
- max_wait_time_ms: 305
- startup_timeout_ms: 10000
- launch_target: com.android.settings/.HWSettings
- iteration 1: status=success, wait_time_ms=33, total_time_ms=0, this_time_ms=None
- iteration 2: status=success, wait_time_ms=10, total_time_ms=0, this_time_ms=None
- iteration 3: status=success, wait_time_ms=305, total_time_ms=301, this_time_ms=None

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
  "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: WARM\nActivity: com.android.settings/.HWSettings\nTotalTime: 301\nWaitTime: 305\nComplete",
  "stderr_tail": "",
  "startup_summary": {
    "configured_loops": 3,
    "completed_loops": 3,
    "successful_loops": 3,
    "failed_loop": null,
    "timed_out_loop": null,
    "launch_wait_ms": 1000,
    "interval_ms": 1000,
    "startup_timeout_ms": 10000,
    "kill_before_launch": true,
    "launch_target": "com.android.settings/.HWSettings",
    "average_wait_time_ms": 116.0,
    "min_wait_time_ms": 10,
    "max_wait_time_ms": 305,
    "iterations": [
      {
        "iteration": 1,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 33,
        "total_time_ms": 0,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nWarning: Activity not started, intent has been delivered to currently running top-most instance.\nStatus: ok\nLaunchState: UNKNOWN (0)\nActivity: com.android.settings/.HWSettings\nTotalTime: 0\nWaitTime: 33\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 2,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 10,
        "total_time_ms": 0,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nWarning: Activity not started, intent has been delivered to currently running top-most instance.\nStatus: ok\nLaunchState: UNKNOWN (0)\nActivity: com.android.settings/.HWSettings\nTotalTime: 0\nWaitTime: 10\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 3,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 305,
        "total_time_ms": 301,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: WARM\nActivity: com.android.settings/.HWSettings\nTotalTime: 301\nWaitTime: 305\nComplete",
        "stderr_tail": ""
      }
    ]
  }
}
```
