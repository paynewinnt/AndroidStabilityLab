# Execution Summary

- task_id: task_a56bc0adedf84be89d886f530fbc7347
- task_name: CLI Query Smoke Cold Start Timeout
- run_id: run_c6468d0ae8134a228df48c80c8d288f0
- instance_id: instance_38ef2a3182d14c17ab5481f4e803ad27
- device_id: 192.168.31.99:5555
- status: failed
- monitoring_error: none
- scenario_note: 冷启动循环第 1 轮启动超时：启动耗时 256 ms，超过阈值 1 ms。
- issue_count: 1
- artifact_count: 3

## Startup Summary

- configured_loops: 1
- completed_loops: 1
- successful_loops: 0
- average_wait_time_ms: 256.0
- min_wait_time_ms: 256
- max_wait_time_ms: 256
- startup_timeout_ms: 1
- launch_target: com.hihonor.calculator/.Calculator
- iteration 1: status=timeout, wait_time_ms=256, total_time_ms=253, this_time_ms=None

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=failed, exit_reason=timeout, retryable=True, retry_category=startup_timeout, note=冷启动循环第 1 轮启动超时：启动耗时 256 ms，超过阈值 1 ms。

## Cleanup

- action=force_stop, reason=final scenario failure after 1 attempt(s), return_code=0, timed_out=False

## Issues

- [startup_timeout] 冷启动超时 (high)
  - summary: 冷启动循环第 1 轮启动超时：启动耗时 256 ms，超过阈值 1 ms。

## Artifacts

- [execution_log] runtime/tasks/task_a56bc0adedf84be89d886f530fbc7347/runs/run_c6468d0ae8134a228df48c80c8d288f0/executions/instance_38ef2a3182d14c17ab5481f4e803ad27/devices/192_168_31_99_5555/artifacts/issue_b21bbf7feb5b4e819f123755e5fcf0de/execution.log
  - issue_id: issue_b21bbf7feb5b4e819f123755e5fcf0de
  - capture_status: success
  - size_bytes: 529
- [bugreport] runtime/tasks/task_a56bc0adedf84be89d886f530fbc7347/runs/run_c6468d0ae8134a228df48c80c8d288f0/executions/instance_38ef2a3182d14c17ab5481f4e803ad27/devices/192_168_31_99_5555/artifacts/issue_b21bbf7feb5b4e819f123755e5fcf0de/bugreport.txt
  - issue_id: issue_b21bbf7feb5b4e819f123755e5fcf0de
  - capture_status: success
  - size_bytes: 451
- [logcat] runtime/tasks/task_a56bc0adedf84be89d886f530fbc7347/runs/run_c6468d0ae8134a228df48c80c8d288f0/executions/instance_38ef2a3182d14c17ab5481f4e803ad27/devices/192_168_31_99_5555/artifacts/issue_b21bbf7feb5b4e819f123755e5fcf0de/logcat.txt
  - issue_id: issue_b21bbf7feb5b4e819f123755e5fcf0de
  - capture_status: success
  - size_bytes: 46578
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
  "stdout_tail": "Starting: Intent { cmp=com.hihonor.calculator/.Calculator }\nStatus: ok\nLaunchState: COLD\nActivity: com.hihonor.calculator/.Calculator\nTotalTime: 253\nWaitTime: 256\nComplete",
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
    "average_wait_time_ms": 256.0,
    "min_wait_time_ms": 256,
    "max_wait_time_ms": 256,
    "iterations": [
      {
        "iteration": 1,
        "status": "timeout",
        "return_code": 0,
        "wait_time_ms": 256,
        "total_time_ms": 253,
        "this_time_ms": null,
        "status_text": "ok",
        "launch_target": "com.hihonor.calculator/.Calculator",
        "stdout_tail": "Starting: Intent { cmp=com.hihonor.calculator/.Calculator }\nStatus: ok\nLaunchState: COLD\nActivity: com.hihonor.calculator/.Calculator\nTotalTime: 253\nWaitTime: 256\nComplete",
        "stderr_tail": "",
        "launch_attempts": 1,
        "recovered_after_disconnect": false
      }
    ]
  }
}
```
