# Execution Summary

- task_id: task_4ba4c2782d8648ff84c8b7d14e39f50e
- task_name: cold_start_loop_midrun_disconnect_com_android_settings_20250719_204315
- run_id: run_1527b88eac91431ab00290bc10135f58
- instance_id: instance_7616d11612774cababd7e9b63665738f
- device_id: 192.168.31.161:38393
- status: success
- monitoring_error: none
- scenario_note: 冷启动循环执行完成，共执行 6 轮，平均启动耗时 475.67 ms。

## Startup Summary

- configured_loops: 6
- completed_loops: 6
- successful_loops: 6
- average_wait_time_ms: 475.67
- min_wait_time_ms: 446
- max_wait_time_ms: 551
- startup_timeout_ms: 10000
- launch_target: com.android.settings/.HWSettings
- iteration 1: status=success, wait_time_ms=551, total_time_ms=548, this_time_ms=None
- iteration 2: status=success, wait_time_ms=455, total_time_ms=451, this_time_ms=None
- iteration 3: status=success, wait_time_ms=460, total_time_ms=457, this_time_ms=None
- iteration 4: status=success, wait_time_ms=457, total_time_ms=453, this_time_ms=None
- iteration 5: status=success, wait_time_ms=446, total_time_ms=441, this_time_ms=None
- iteration 6: status=success, wait_time_ms=485, total_time_ms=482, this_time_ms=None

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
    "192.168.31.161:38393",
    "shell",
    "am",
    "start",
    "-W",
    "-n",
    "com.android.settings/.HWSettings"
  ],
  "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 482\nWaitTime: 485\nComplete",
  "stderr_tail": "",
  "startup_summary": {
    "configured_loops": 6,
    "completed_loops": 6,
    "successful_loops": 6,
    "failed_loop": null,
    "timed_out_loop": null,
    "launch_wait_ms": 1000,
    "interval_ms": 2000,
    "startup_timeout_ms": 10000,
    "kill_before_launch": true,
    "launch_target": "com.android.settings/.HWSettings",
    "average_wait_time_ms": 475.67,
    "min_wait_time_ms": 446,
    "max_wait_time_ms": 551,
    "iterations": [
      {
        "iteration": 1,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 551,
        "total_time_ms": 548,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 548\nWaitTime: 551\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 2,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 455,
        "total_time_ms": 451,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 451\nWaitTime: 455\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 3,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 460,
        "total_time_ms": 457,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 457\nWaitTime: 460\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 4,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 457,
        "total_time_ms": 453,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 453\nWaitTime: 457\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 5,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 446,
        "total_time_ms": 441,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 441\nWaitTime: 446\nComplete",
        "stderr_tail": ""
      },
      {
        "iteration": 6,
        "status": "success",
        "return_code": 0,
        "wait_time_ms": 485,
        "total_time_ms": 482,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.android.settings/.HWSettings",
        "stdout_tail": "Starting: Intent { cmp=com.android.settings/.HWSettings }\nStatus: ok\nLaunchState: COLD\nActivity: com.android.settings/.HWSettings\nTotalTime: 482\nWaitTime: 485\nComplete",
        "stderr_tail": ""
      }
    ]
  }
}
```
