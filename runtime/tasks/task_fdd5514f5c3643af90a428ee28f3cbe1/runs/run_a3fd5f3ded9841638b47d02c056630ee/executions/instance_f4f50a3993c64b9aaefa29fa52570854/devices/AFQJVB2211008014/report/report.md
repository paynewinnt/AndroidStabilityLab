# Execution Summary

- task_id: task_fdd5514f5c3643af90a428ee28f3cbe1
- task_name: Douyin Monkey Smoke
- run_id: run_a3fd5f3ded9841638b47d02c056630ee
- instance_id: instance_f4f50a3993c64b9aaefa29fa52570854
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: Monkey 模板执行完成，共注入 240 个事件。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T20:44:00.040205",
  "persisted": true,
  "system": {
    "cpu_usage": 7.5,
    "cpu_user": 4.6,
    "cpu_breakdown": {
      "total": 7.5,
      "user": 4.6,
      "kernel": 2.7,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 2418.73,
    "memory_usage_percent": 57.57,
    "memory_percent": 57.57,
    "memory_system_used": 3281.42,
    "battery_level": 100.0,
    "network_rx_total": 71929.14,
    "network_tx_total": 5437.46,
    "network_rx": 0,
    "network_tx": 0,
    "network": 0,
    "load_1min": 22.6,
    "load_5min": 23.55,
    "load_15min": 23.84
  },
  "apps": [
    {
      "app_package": "com.ss.android.ugc.aweme",
      "memory_pss": 1004.44,
      "memory_java": 192.02,
      "memory_native": 221.96,
      "frame_count": 396.0,
      "jank_frames": 76.0,
      "jank_percent": 19.19,
      "gpu_p50_ms": 4.0,
      "gpu_p90_ms": 6.0,
      "gpu_p95_ms": 6.0,
      "gpu_p99_ms": 8.0,
      "fps": 2.4,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 25.0,
      "top_memory_percent": 18.7,
      "top_memory_res_kb": 1048576.0,
      "app_info": {
        "package_name": "com.ss.android.ugc.aweme",
        "app_name": "com.ss.android.ugc.aweme"
      },
      "package_name": "com.ss.android.ugc.aweme"
    }
  ],
  "metadata": {
    "backend": "legacy_adb",
    "profile_name": "solox",
    "warnings": [
      "metrics backend 'solox' unavailable, falling back to legacy_adb: no process found"
    ]
  }
}
```

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=success, exit_reason=completed, retryable=False, retry_category=completed, note=Monkey 模板执行完成，共注入 240 个事件。

## Scenario Result

```json
{
  "command": [
    "adb",
    "-s",
    "AFQJVB2211008014",
    "shell",
    "monkey",
    "-p",
    "com.ss.android.ugc.aweme",
    "--throttle",
    "300",
    "--ignore-crashes",
    "--ignore-timeouts",
    "--ignore-security-exceptions",
    "-v",
    "240"
  ],
  "stdout_tail": "nding Touch (ACTION_DOWN): 0:(756.0,1678.0)\n:Sending Touch (ACTION_UP): 0:(770.79254,1686.4343)\n:Sending Touch (ACTION_DOWN): 0:(140.0,1677.0)\n:Sending Touch (ACTION_UP): 0:(237.30716,1545.6959)\n:Sending Touch (ACTION_DOWN): 0:(664.0,2262.0)\n:Sending Touch (ACTION_UP): 0:(609.26917,2221.7253)\n:Sending Flip keyboardOpen=false\nGot IOException performing flipjava.io.FileNotFoundException: /dev/input/event0: open failed: EACCES (Permission denied)\n    // Injection Failed\n:Sending Touch (ACTION_DOWN): 0:(683.0,373.0)\n:Sending Touch (ACTION_UP): 0:(667.07367,339.36963)\n    // activityResuming(com.ss.android.ugc.aweme)\n:Sending Trackball (ACTION_MOVE): 0:(-1.0,2.0)\n:Sending Trackball (ACTION_MOVE): 0:(1.0,-1.0)\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n:Sending Touch (ACTION_DOWN): 0:(749.0,135.0)\n:Sending Touch (ACTION_UP): 0:(739.95135,185.69653)\n    // Allowing start of Intent { cmp=com.ss.android.ugc.aweme/.profile.ui.ProfileCoverPreviewActivity } in package com.ss.android.ugc.aweme\n:Sending Touch (ACTION_DOWN): 0:(698.0,229.0)\n:Sending Touch (ACTION_UP): 0:(711.4158,233.95119)\n    // activityResuming(com.ss.android.ugc.aweme)\n:Sending Trackball (ACTION_MOVE): 0:(0.0,-1.0)\n:Sending Trackball (ACTION_MOVE): 0:(-2.0,-1.0)\n    //[calendar_time:2025-07-26 04:43:53.386  system_uptime:91916129]\n    // Sending event #200\n:Sending Touch (ACTION_DOWN): 0:(141.0,1586.0)\n:Sending Touch (ACTION_UP): 0:(81.650635,1612.5552)\n:Sending Touch (ACTION_DOWN): 0:(55.0,2124.0)\n:Sending Touch (ACTION_UP): 0:(61.036884,2118.469)\n:Sending Touch (ACTION_DOWN): 0:(576.0,827.0)\n:Sending Touch (ACTION_UP): 0:(544.16144,785.9566)\n:Sending Touch (ACTION_DOWN): 0:(100.0,1758.0)\n:Sending Touch (ACTION_UP): 0:(34.902996,1773.5239)\n:Sending Trackball (ACTION_MOVE): 0:(1.0,2.0)\nEvents injected: 240\n:Sending rotation degree=0, persist=false\n:Dropped: keys=0 pointers=0 trackballs=0 flips=1 rotations=0\n## Network stats: elapsed time=18915ms (0ms mobile, 0ms wifi, 18915ms not connected)\n// Monkey finished",
  "stderr_tail": "args: [-p, com.ss.android.ugc.aweme, --throttle, 300, --ignore-crashes, --ignore-timeouts, --ignore-security-exceptions, -v, 240]\n arg: \"-p\"\n arg: \"com.ss.android.ugc.aweme\"\n arg: \"--throttle\"\n arg: \"300\"\n arg: \"--ignore-crashes\"\n arg: \"--ignore-timeouts\"\n arg: \"--ignore-security-exceptions\"\n arg: \"-v\"\n arg: \"240\"\ndata=\"com.ss.android.ugc.aweme\"\narg=\"--throttle\" mCurArgData=\"null\" mNextArg=3 argwas=\"--throttle\" nextarg=\"300\"\ndata=\"300\"\narg=\"--ignore-crashes\" mCurArgData=\"null\" mNextArg=5 argwas=\"--ignore-crashes\" nextarg=\"--ignore-timeouts\"\narg=\"--ignore-timeouts\" mCurArgData=\"null\" mNextArg=6 argwas=\"--ignore-timeouts\" nextarg=\"--ignore-security-exceptions\"\narg=\"--ignore-security-exceptions\" mCurArgData=\"null\" mNextArg=7 argwas=\"--ignore-security-exceptions\" nextarg=\"-v\"",
  "command_attempts": 1,
  "recovered_after_disconnect": false,
  "template_type": "monkey",
  "return_code": 0,
  "events_injected": 240
}
```
