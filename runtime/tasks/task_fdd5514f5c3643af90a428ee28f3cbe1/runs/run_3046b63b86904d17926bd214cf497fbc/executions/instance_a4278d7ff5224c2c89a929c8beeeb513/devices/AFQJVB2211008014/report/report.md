# Execution Summary

- task_id: task_fdd5514f5c3643af90a428ee28f3cbe1
- task_name: Douyin Monkey Smoke
- run_id: run_3046b63b86904d17926bd214cf497fbc
- instance_id: instance_a4278d7ff5224c2c89a929c8beeeb513
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: Monkey 模板执行完成，共注入 240 个事件。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T20:20:19.898011",
  "persisted": true,
  "system": {
    "cpu_usage": 7.3,
    "cpu_user": 5.0,
    "cpu_breakdown": {
      "total": 7.3,
      "user": 5.0,
      "kernel": 2.2,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 1619.36,
    "memory_usage_percent": 71.59,
    "memory_percent": 71.59,
    "memory_system_used": 4080.79,
    "battery_level": 100.0,
    "network_rx_total": 39373.43,
    "network_tx_total": 3631.88,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "load_1min": 26.72,
    "load_5min": 23.74,
    "load_15min": 22.97
  },
  "apps": [
    {
      "app_package": "com.ss.android.ugc.aweme",
      "memory_pss": 1359.11,
      "memory_java": 189.61,
      "memory_native": 516.38,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 100.0,
      "top_memory_percent": 25.1,
      "top_memory_res_kb": 1363148.8,
      "app_info": {
        "package_name": "com.ss.android.ugc.aweme",
        "app_name": "com.ss.android.ugc.aweme"
      },
      "package_name": "com.ss.android.ugc.aweme"
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
  "stdout_tail": "oft.appmanager\n:Sending Touch (ACTION_DOWN): 0:(1039.0,1616.0)\n:Sending Touch (ACTION_UP): 0:(1042.1261,1681.2207)\n:Sending Touch (ACTION_DOWN): 0:(276.0,2111.0)\n:Sending Touch (ACTION_UP): 0:(277.92682,2118.4023)\n:Sending Trackball (ACTION_MOVE): 0:(3.0,-1.0)\n:Sending Touch (ACTION_DOWN): 0:(836.0,823.0)\n:Sending Touch (ACTION_UP): 0:(830.6686,821.1552)\n:Sending Trackball (ACTION_MOVE): 0:(-4.0,-3.0)\n:Sending Trackball (ACTION_MOVE): 0:(-4.0,1.0)\n:Sending Flip keyboardOpen=true\nGot IOException performing flipjava.io.FileNotFoundException: /dev/input/event0: open failed: EACCES (Permission denied)\n    // Injection Failed\n:Switch: #Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.ss.android.ugc.aweme/.splash.SplashActivity;end\n    // Allowing start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.ss.android.ugc.aweme/.splash.SplashActivity } in package com.ss.android.ugc.aweme\n:Sending Trackball (ACTION_MOVE): 0:(-3.0,-5.0)\n:Sending Touch (ACTION_DOWN): 0:(774.0,1132.0)\n:Sending Touch (ACTION_UP): 0:(717.9768,1084.4196)\n:Sending Touch (ACTION_DOWN): 0:(577.0,2141.0)\n    //[calendar_time:2025-07-26 04:20:15.043  system_uptime:90497786]\n    // Sending event #200\n:Sending Touch (ACTION_UP): 0:(575.9051,2124.1428)\n:Sending Touch (ACTION_DOWN): 0:(586.0,736.0)\n:Sending Touch (ACTION_UP): 0:(585.0876,753.168)\n:Sending Trackball (ACTION_MOVE): 0:(3.0,-3.0)\n:Sending Trackball (ACTION_MOVE): 0:(1.0,-1.0)\n:Sending Touch (ACTION_DOWN): 0:(917.0,1110.0)\n:Sending Touch (ACTION_UP): 0:(918.4502,1110.9977)\n:Sending Touch (ACTION_DOWN): 0:(520.0,2278.0)\n:Sending Touch (ACTION_UP): 0:(515.67267,2275.0842)\n:Sending Trackball (ACTION_MOVE): 0:(0.0,3.0)\nEvents injected: 240\n:Sending rotation degree=0, persist=false\n:Dropped: keys=0 pointers=0 trackballs=0 flips=2 rotations=0\n## Network stats: elapsed time=25530ms (0ms mobile, 0ms wifi, 25530ms not connected)\n// Monkey finished",
  "stderr_tail": "args: [-p, com.ss.android.ugc.aweme, --throttle, 300, --ignore-crashes, --ignore-timeouts, --ignore-security-exceptions, -v, 240]\n arg: \"-p\"\n arg: \"com.ss.android.ugc.aweme\"\n arg: \"--throttle\"\n arg: \"300\"\n arg: \"--ignore-crashes\"\n arg: \"--ignore-timeouts\"\n arg: \"--ignore-security-exceptions\"\n arg: \"-v\"\n arg: \"240\"\ndata=\"com.ss.android.ugc.aweme\"\narg=\"--throttle\" mCurArgData=\"null\" mNextArg=3 argwas=\"--throttle\" nextarg=\"300\"\ndata=\"300\"\narg=\"--ignore-crashes\" mCurArgData=\"null\" mNextArg=5 argwas=\"--ignore-crashes\" nextarg=\"--ignore-timeouts\"\narg=\"--ignore-timeouts\" mCurArgData=\"null\" mNextArg=6 argwas=\"--ignore-timeouts\" nextarg=\"--ignore-security-exceptions\"\narg=\"--ignore-security-exceptions\" mCurArgData=\"null\" mNextArg=7 argwas=\"--ignore-security-exceptions\" nextarg=\"-v\"",
  "command_attempts": 1,
  "recovered_after_disconnect": false,
  "template_type": "monkey",
  "return_code": 0,
  "events_injected": 240
}
```
