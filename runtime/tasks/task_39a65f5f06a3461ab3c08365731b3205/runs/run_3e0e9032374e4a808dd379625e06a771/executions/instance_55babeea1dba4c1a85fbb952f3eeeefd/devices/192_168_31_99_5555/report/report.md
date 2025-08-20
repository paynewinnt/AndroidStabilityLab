# Execution Summary

- task_id: task_39a65f5f06a3461ab3c08365731b3205
- task_name: Extended Artifacts Smoke Cold Start Timeout
- run_id: run_3e0e9032374e4a808dd379625e06a771
- instance_id: instance_55babeea1dba4c1a85fbb952f3eeeefd
- device_id: 192.168.31.99:5555
- status: failed
- monitoring_error: none
- scenario_note: 冷启动循环第 1 轮启动超时：启动耗时 278 ms，超过阈值 1 ms。
- issue_count: 1
- artifact_count: 5

## Startup Summary

- configured_loops: 1
- completed_loops: 1
- successful_loops: 0
- average_wait_time_ms: 278.0
- min_wait_time_ms: 278
- max_wait_time_ms: 278
- startup_timeout_ms: 1
- launch_target: com.hihonor.calculator/.Calculator
- iteration 1: status=timeout, wait_time_ms=278, total_time_ms=276, this_time_ms=None

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=failed, exit_reason=timeout, retryable=True, retry_category=startup_timeout, note=冷启动循环第 1 轮启动超时：启动耗时 278 ms，超过阈值 1 ms。

## Cleanup

- action=force_stop, reason=final scenario failure after 1 attempt(s), return_code=0, timed_out=False

## Issues

- [startup_timeout] 冷启动超时 (high)
  - summary: 冷启动循环第 1 轮启动超时：启动耗时 278 ms，超过阈值 1 ms。

## Artifacts

- [execution_log] runtime/tasks/task_39a65f5f06a3461ab3c08365731b3205/runs/run_3e0e9032374e4a808dd379625e06a771/executions/instance_55babeea1dba4c1a85fbb952f3eeeefd/devices/192_168_31_99_5555/artifacts/issue_c49affaf6d0742089884041a6b32a828/execution.log
  - issue_id: issue_c49affaf6d0742089884041a6b32a828
  - capture_status: success
  - size_bytes: 529
- [bugreport] runtime/tasks/task_39a65f5f06a3461ab3c08365731b3205/runs/run_3e0e9032374e4a808dd379625e06a771/executions/instance_55babeea1dba4c1a85fbb952f3eeeefd/devices/192_168_31_99_5555/artifacts/issue_c49affaf6d0742089884041a6b32a828/bugreport.txt
  - issue_id: issue_c49affaf6d0742089884041a6b32a828
  - capture_status: success
  - size_bytes: 451
- [dropbox] runtime/tasks/task_39a65f5f06a3461ab3c08365731b3205/runs/run_3e0e9032374e4a808dd379625e06a771/executions/instance_55babeea1dba4c1a85fbb952f3eeeefd/devices/192_168_31_99_5555/artifacts/issue_c49affaf6d0742089884041a6b32a828/dropbox.txt
  - issue_id: issue_c49affaf6d0742089884041a6b32a828
  - capture_status: success
  - size_bytes: 50599
- [dumpsys_meminfo] runtime/tasks/task_39a65f5f06a3461ab3c08365731b3205/runs/run_3e0e9032374e4a808dd379625e06a771/executions/instance_55babeea1dba4c1a85fbb952f3eeeefd/devices/192_168_31_99_5555/artifacts/issue_c49affaf6d0742089884041a6b32a828/meminfo.txt
  - issue_id: issue_c49affaf6d0742089884041a6b32a828
  - capture_status: success
  - size_bytes: 3034
- [logcat] runtime/tasks/task_39a65f5f06a3461ab3c08365731b3205/runs/run_3e0e9032374e4a808dd379625e06a771/executions/instance_55babeea1dba4c1a85fbb952f3eeeefd/devices/192_168_31_99_5555/artifacts/issue_c49affaf6d0742089884041a6b32a828/logcat.txt
  - issue_id: issue_c49affaf6d0742089884041a6b32a828
  - capture_status: success
  - size_bytes: 48333
  - metadata: captures=[{'mode': 'crash_buffer'}, {'mode': 'all_buffers'}]

## Artifact Capture Notes

- traces 抓取失败：未能读取候选文件 /data/anr/traces.txt, /data/anr/anr_2025-07-29-23-37-32-567。
- tombstone 抓取跳过：未发现可读取的 tombstone 文件。

## Scenario Result

```json
{
  "template_type": "cold_start_loop",
  "package_name": "com.hihonor.calculator",
  "process_name": "com.hihonor.calculator",
  "launch_target": "com.hihonor.calculator/.Calculator",
  "command": [
    "adb",
    "-s",
    "192.168.31.99:5555",
    "shell",
    "am",
    "start",
    "-W",
    "-n",
    "com.hihonor.calculator/.Calculator"
  ],
  "stdout_tail": "Starting: Intent { cmp=com.hihonor.calculator/.Calculator }\nStatus: ok\nLaunchState: COLD\nActivity: com.hihonor.calculator/.Calculator\nTotalTime: 276\nWaitTime: 278\nComplete",
  "stderr_tail": "",
  "startup_failure": true,
  "startup_failure_kind": "startup_timeout",
  "startup_failure_loop": 1,
  "startup_failure_reason": "startup timeout on loop 1",
  "startup_summary": {
    "configured_loops": 1,
    "completed_loops": 1,
    "successful_loops": 0,
    "failed_loop": null,
    "timed_out_loop": 1,
    "launch_wait_ms": 500,
    "interval_ms": 500,
    "startup_timeout_ms": 1,
    "kill_before_launch": true,
    "launch_target": "com.hihonor.calculator/.Calculator",
    "average_wait_time_ms": 278.0,
    "min_wait_time_ms": 278,
    "max_wait_time_ms": 278,
    "iterations": [
      {
        "iteration": 1,
        "status": "timeout",
        "return_code": 0,
        "wait_time_ms": 278,
        "total_time_ms": 276,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.hihonor.calculator/.Calculator",
        "stdout_tail": "Starting: Intent { cmp=com.hihonor.calculator/.Calculator }\nStatus: ok\nLaunchState: COLD\nActivity: com.hihonor.calculator/.Calculator\nTotalTime: 276\nWaitTime: 278\nComplete",
        "stderr_tail": "",
        "launch_attempts": 1,
        "recovered_after_disconnect": false
      }
    ]
  }
}
```
