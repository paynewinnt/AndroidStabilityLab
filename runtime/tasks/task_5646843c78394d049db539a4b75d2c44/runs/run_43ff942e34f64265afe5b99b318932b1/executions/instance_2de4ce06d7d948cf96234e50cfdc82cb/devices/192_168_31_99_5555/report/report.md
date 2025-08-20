# Execution Summary

- task_id: task_5646843c78394d049db539a4b75d2c44
- task_name: monkey_midrun_disconnect_com_hihonor_calculator_20250719_211747
- run_id: run_43ff942e34f64265afe5b99b318932b1
- instance_id: instance_2de4ce06d7d948cf96234e50cfdc82cb
- device_id: 192.168.31.99:5555
- status: success
- monitoring_error: none
- scenario_note: Monkey 模板执行完成，共注入 300 个事件。

## Scenario Result

```json
{
  "command": [
    "adb",
    "-s",
    "192.168.31.99:5555",
    "shell",
    "monkey",
    "-p",
    "com.hihonor.calculator",
    "--throttle",
    "100",
    "--ignore-crashes",
    "--ignore-timeouts",
    "--ignore-security-exceptions",
    "-v",
    "300"
  ],
  "stdout_tail": "/[calendar_time:2025-07-19 21:18:01.794  system_uptime:562991063]\n    // Sending event #200\n    //[calendar_time:2025-07-19 21:18:01.895  system_uptime:562991164]\n    // Sending event #200\n:Sending Touch (ACTION_DOWN): 0:(1552.0,29.0)\n:Sending Touch (ACTION_UP): 0:(1561.1866,30.15243)\n:Sending Trackball (ACTION_MOVE): 0:(-4.0,-2.0)\n:Sending Touch (ACTION_DOWN): 0:(1508.0,531.0)\n:Sending Touch (ACTION_UP): 0:(1500.9348,526.5973)\n:Sending Touch (ACTION_DOWN): 0:(2181.0,797.0)\n:Sending Touch (ACTION_UP): 0:(2204.5132,831.6047)\n:Sending Touch (ACTION_DOWN): 0:(2141.0,791.0)\n:Sending Touch (ACTION_UP): 0:(2141.598,786.6838)\n    // Rejecting start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.hihonor.mms/com.android.mms.ui.ConversationList } in package com.hihonor.mms\n:Sending Trackball (ACTION_MOVE): 0:(-5.0,3.0)\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n:Sending Trackball (ACTION_MOVE): 0:(2.0,-1.0)\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n:Sending Touch (ACTION_DOWN): 0:(822.0,1049.0)\n:Sending Touch (ACTION_UP): 0:(815.41675,1049.0248)\n:Sending Trackball (ACTION_MOVE): 0:(-2.0,3.0)\n:Sending Trackball (ACTION_MOVE): 0:(-2.0,2.0)\n    // Rejecting start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.hihonor.email/com.android.email.activity.Welcome } in package com.hihonor.email\n:Switch: #Intent;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;launchFlags=0x10200000;component=com.hihonor.calculator/.Calculator;end\n    // Allowing start of Intent { act=android.intent.action.MAIN cat=[android.intent.category.LAUNCHER] cmp=com.hihonor.calculator/.Calculator } in package com.hihonor.calculator\n:Sending Touch (ACTION_DOWN): 0:(923.0,160.0)\nEvents injected: 300\n:Sending rotation degree=0, persist=false\n:Dropped: keys=0 pointers=0 trackballs=0 flips=1 rotations=0\n## Network stats: elapsed time=9596ms (0ms mobile, 0ms wifi, 9596ms not connected)\n// Monkey finished",
  "stderr_tail": "args: [-p, com.hihonor.calculator, --throttle, 100, --ignore-crashes, --ignore-timeouts, --ignore-security-exceptions, -v, 300]\n arg: \"-p\"\n arg: \"com.hihonor.calculator\"\n arg: \"--throttle\"\n arg: \"100\"\n arg: \"--ignore-crashes\"\n arg: \"--ignore-timeouts\"\n arg: \"--ignore-security-exceptions\"\n arg: \"-v\"\n arg: \"300\"\ndata=\"com.hihonor.calculator\"\narg=\"--throttle\" mCurArgData=\"null\" mNextArg=3 argwas=\"--throttle\" nextarg=\"100\"\ndata=\"100\"\narg=\"--ignore-crashes\" mCurArgData=\"null\" mNextArg=5 argwas=\"--ignore-crashes\" nextarg=\"--ignore-timeouts\"\narg=\"--ignore-timeouts\" mCurArgData=\"null\" mNextArg=6 argwas=\"--ignore-timeouts\" nextarg=\"--ignore-security-exceptions\"\narg=\"--ignore-security-exceptions\" mCurArgData=\"null\" mNextArg=7 argwas=\"--ignore-security-exceptions\" nextarg=\"-v\"",
  "command_attempts": 2,
  "recovered_after_disconnect": true,
  "template_type": "monkey",
  "return_code": 0,
  "events_injected": 300
}
```
