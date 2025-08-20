# Execution Summary

- task_id: task_fdd5514f5c3643af90a428ee28f3cbe1
- task_name: Douyin Monkey Smoke
- run_id: run_5f69cf976de64c958ec20c038b40b4ae
- instance_id: instance_d25674511a434c1399ccdcba57c7869b
- device_id: AFQJVB2211008014
- status: success
- monitoring_error: none
- scenario_note: Monkey 模板执行完成，共注入 240 个事件。

## Monitoring Snapshot

```json
{
  "timestamp": "2025-07-25T20:32:28.574987",
  "persisted": true,
  "system": {
    "cpu_usage": 6.9,
    "cpu_user": 4.3,
    "cpu_breakdown": {
      "total": 6.9,
      "user": 4.3,
      "kernel": 2.5,
      "iowait": 0.0,
      "softirq": 0.0
    },
    "memory_system_total": 5700.15,
    "memory_system_available": 1613.32,
    "memory_usage_percent": 71.7,
    "memory_percent": 71.7,
    "memory_system_used": 4086.83,
    "battery_level": 100.0,
    "network_rx_total": 46591.38,
    "network_tx_total": 3847.95,
    "network_rx": 4587.58,
    "network_tx": 203.64,
    "network": 4791.22,
    "load_1min": 28.47,
    "load_5min": 25.01,
    "load_15min": 23.99
  },
  "apps": [
    {
      "app_package": "com.ss.android.ugc.aweme",
      "memory_pss": 1970.57,
      "memory_java": 293.55,
      "memory_native": 765.38,
      "power_consumption": 3900.0,
      "wakelock_count": 1,
      "top_cpu_usage": 131.0,
      "top_memory_percent": 34.7,
      "top_memory_res_kb": 1992294.4,
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
  "stdout_tail": "ON_DOWN): 0:(759.0,883.0)\n:Sending Touch (ACTION_UP): 0:(736.98724,878.528)\n:Switch: #Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.ss.android.ugc.aweme/.splash.SplashActivity;end\n    // Allowing start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.ss.android.ugc.aweme/.splash.SplashActivity } in package com.ss.android.ugc.aweme\n:Sending Trackball (ACTION_MOVE): 0:(0.0,1.0)\n    // Allowing start of Intent { dat=snssdk1128://detail pkg=com.ss.android.ugc.aweme cmp=com.ss.android.ugc.aweme/.detail.ui.DetailActivity } in package com.ss.android.ugc.aweme\n:Sending Trackball (ACTION_MOVE): 0:(1.0,-1.0)\n    // Allowing start of Intent { cmp=com.ss.android.ugc.aweme/.account.business.login.DYLoginActivity } in package com.ss.android.ugc.aweme\n:Sending Touch (ACTION_DOWN): 0:(631.0,875.0)\n:Sending Touch (ACTION_UP): 0:(624.4641,893.84143)\n:Sending Trackball (ACTION_MOVE): 0:(3.0,-3.0)\n    //[calendar_time:2025-07-26 04:32:15.068  system_uptime:91217811]\n    // Sending event #200\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n:Sending Touch (ACTION_DOWN): 0:(1057.0,382.0)\n:Sending Touch (ACTION_UP): 0:(1031.2039,387.41873)\n:Sending Touch (ACTION_DOWN): 0:(676.0,1947.0)\n:Sending Touch (ACTION_UP): 0:(668.7536,1947.4984)\n    // Allowing start of Intent { cmp=com.ss.android.ugc.aweme/.search.activity.SearchResultActivity } in package com.ss.android.ugc.aweme\n    // activityResuming(com.ss.android.ugc.aweme)\n:Sending Touch (ACTION_DOWN): 0:(527.0,427.0)\n:Sending Touch (ACTION_UP): 0:(512.5184,413.24484)\n:Sending Touch (ACTION_DOWN): 0:(997.0,1089.0)\n:Sending Touch (ACTION_UP): 0:(1018.7999,1087.3739)\n:Sending Touch (ACTION_DOWN): 0:(42.0,396.0)\nEvents injected: 240\n:Sending rotation degree=0, persist=false\n:Dropped: keys=0 pointers=0 trackballs=0 flips=0 rotations=0\n## Network stats: elapsed time=31484ms (0ms mobile, 0ms wifi, 31484ms not connected)\n// Monkey finished",
  "stderr_tail": "args: [-p, com.ss.android.ugc.aweme, --throttle, 300, --ignore-crashes, --ignore-timeouts, --ignore-security-exceptions, -v, 240]\n arg: \"-p\"\n arg: \"com.ss.android.ugc.aweme\"\n arg: \"--throttle\"\n arg: \"300\"\n arg: \"--ignore-crashes\"\n arg: \"--ignore-timeouts\"\n arg: \"--ignore-security-exceptions\"\n arg: \"-v\"\n arg: \"240\"\ndata=\"com.ss.android.ugc.aweme\"\narg=\"--throttle\" mCurArgData=\"null\" mNextArg=3 argwas=\"--throttle\" nextarg=\"300\"\ndata=\"300\"\narg=\"--ignore-crashes\" mCurArgData=\"null\" mNextArg=5 argwas=\"--ignore-crashes\" nextarg=\"--ignore-timeouts\"\narg=\"--ignore-timeouts\" mCurArgData=\"null\" mNextArg=6 argwas=\"--ignore-timeouts\" nextarg=\"--ignore-security-exceptions\"\narg=\"--ignore-security-exceptions\" mCurArgData=\"null\" mNextArg=7 argwas=\"--ignore-security-exceptions\" nextarg=\"-v\"",
  "command_attempts": 1,
  "recovered_after_disconnect": false,
  "template_type": "monkey",
  "return_code": 0,
  "events_injected": 240
}
```
