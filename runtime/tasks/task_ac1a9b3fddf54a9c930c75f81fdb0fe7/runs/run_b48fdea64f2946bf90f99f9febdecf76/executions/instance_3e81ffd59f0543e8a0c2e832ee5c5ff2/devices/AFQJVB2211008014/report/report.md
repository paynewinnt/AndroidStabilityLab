# Execution Summary

- task_id: task_ac1a9b3fddf54a9c930c75f81fdb0fe7
- task_name: Douyin Monkey Smoke
- run_id: run_b48fdea64f2946bf90f99f9febdecf76
- instance_id: instance_3e81ffd59f0543e8a0c2e832ee5c5ff2
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: Monkey 模板执行完成，共注入 5 个事件。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-19T10:54:35.352900",
  "persisted": false,
  "system": {
    "cpu_usage": 6.4,
    "cpu_user": 4.2,
    "cpu_breakdown": {
      "total": 6.4,
      "user": 4.2,
      "kernel": 2.1,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 2454.7,
    "memory_usage_percent": 56.94,
    "memory_percent": 56.94,
    "memory_system_used": 3245.45,
    "battery_level": 100.0,
    "network_rx_total": 80622.92,
    "network_tx_total": 7962.95,
    "network": 0.0,
    "network_rx": 0.0,
    "network_tx": 0.0,
    "load_1min": 23.81,
    "load_5min": 23.57,
    "load_15min": 23.49
  },
  "apps": [
    {
      "app_package": "com.ss.android.ugc.aweme",
      "memory_pss": 595.31,
      "memory_java": 109.53,
      "memory_native": 83.51,
      "power_consumption": 3900.0,
      "top_cpu_usage": 186.0,
      "top_memory_percent": 11.1,
      "top_memory_res_kb": 648192.0,
      "app_info": {
        "package_name": "com.ss.android.ugc.aweme",
        "app_name": "com.ss.android.ugc.aweme"
      }
    }
  ]
}
```

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
    "500",
    "--ignore-crashes",
    "--ignore-timeouts",
    "--ignore-security-exceptions",
    "-v",
    "5"
  ],
  "return_code": 0,
  "events_injected": 5,
  "stdout_tail": "bash arg: -p\n  bash arg: com.ss.android.ugc.aweme\n  bash arg: --throttle\n  bash arg: 500\n  bash arg: --ignore-crashes\n  bash arg: --ignore-timeouts\n  bash arg: --ignore-security-exceptions\n  bash arg: -v\n  bash arg: 5\n:Monkey: seed=1776704011672 count=5\n:AllowPackage: com.ss.android.ugc.aweme\n:IncludeCategory: android.intent.category.LAUNCHER\n:IncludeCategory: android.intent.category.MONKEY\n// Event percentages:\n//   0: 15.0%\n//   1: 10.0%\n//   2: 2.0%\n//   3: 15.0%\n//   4: -0.0%\n//   5: -0.0%\n//   6: 25.0%\n//   7: 15.0%\n//   8: 2.0%\n//   9: 2.0%\n//   10: 1.0%\n//   11: 13.0%\n:Switch: #Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.ss.android.ugc.aweme/.splash.SplashActivity;end\n    // Allowing start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.ss.android.ugc.aweme/.splash.SplashActivity } in package com.ss.android.ugc.aweme\n:Switch: #Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.ss.android.ugc.aweme/.splash.SplashActivity;end\n    // Allowing start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.ss.android.ugc.aweme/.splash.SplashActivity } in package com.ss.android.ugc.aweme\n:Sending Trackball (ACTION_MOVE): 0:(-4.0,0.0)\nEvents injected: 5\n:Sending rotation degree=0, persist=false\n:Dropped: keys=0 pointers=0 trackballs=0 flips=0 rotations=0\n## Network stats: elapsed time=4495ms (0ms mobile, 0ms wifi, 4495ms not connected)\n// Monkey finished",
  "stderr_tail": "args: [-p, com.ss.android.ugc.aweme, --throttle, 500, --ignore-crashes, --ignore-timeouts, --ignore-security-exceptions, -v, 5]\n arg: \"-p\"\n arg: \"com.ss.android.ugc.aweme\"\n arg: \"--throttle\"\n arg: \"500\"\n arg: \"--ignore-crashes\"\n arg: \"--ignore-timeouts\"\n arg: \"--ignore-security-exceptions\"\n arg: \"-v\"\n arg: \"5\"\ndata=\"com.ss.android.ugc.aweme\"\narg=\"--throttle\" mCurArgData=\"null\" mNextArg=3 argwas=\"--throttle\" nextarg=\"500\"\ndata=\"500\"\narg=\"--ignore-crashes\" mCurArgData=\"null\" mNextArg=5 argwas=\"--ignore-crashes\" nextarg=\"--ignore-timeouts\"\narg=\"--ignore-timeouts\" mCurArgData=\"null\" mNextArg=6 argwas=\"--ignore-timeouts\" nextarg=\"--ignore-security-exceptions\"\narg=\"--ignore-security-exceptions\" mCurArgData=\"null\" mNextArg=7 argwas=\"--ignore-security-exceptions\" nextarg=\"-v\"",
  "template_type": "monkey"
}
```
