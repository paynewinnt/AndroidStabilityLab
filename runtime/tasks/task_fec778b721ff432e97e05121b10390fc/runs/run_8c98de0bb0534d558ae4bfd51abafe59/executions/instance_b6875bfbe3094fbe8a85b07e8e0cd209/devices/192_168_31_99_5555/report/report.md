# Execution Summary

- task_id: task_fec778b721ff432e97e05121b10390fc
- task_name: monkey_smoke_com_hihonor_calculator_20250719_215838
- run_id: run_8c98de0bb0534d558ae4bfd51abafe59
- instance_id: instance_b6875bfbe3094fbe8a85b07e8e0cd209
- device_id: 192.168.31.99:5555
- status: success
- monitoring_error: none
- scenario_note: Monkey 模板执行完成，共注入 300 个事件。

## Execution Attempts

- retry_count: 0
- max_attempts: 1
- strategy: classified
- attempt 1: status=success, exit_reason=completed, retryable=False, retry_category=completed, note=Monkey 模板执行完成，共注入 300 个事件。

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
  "stdout_tail": "ending Touch (ACTION_UP): 0:(1006.9496,712.04346)\n:Sending Trackball (ACTION_MOVE): 0:(1.0,-2.0)\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n:Sending Touch (ACTION_DOWN): 0:(294.0,457.0)\n:Sending Touch (ACTION_UP): 0:(240.61864,452.69885)\n:Sending Touch (ACTION_DOWN): 0:(294.0,326.0)\n:Sending Touch (ACTION_UP): 0:(268.2258,326.98953)\n:Sending Touch (ACTION_DOWN): 0:(1631.0,639.0)\n:Sending Touch (ACTION_UP): 0:(1630.9883,638.7151)\n:Sending Trackball (ACTION_MOVE): 0:(-2.0,1.0)\n:Sending Trackball (ACTION_MOVE): 0:(3.0,-1.0)\n:Sending Touch (ACTION_DOWN): 0:(1394.0,557.0)\n:Sending Touch (ACTION_UP): 0:(1388.374,548.89294)\n:Sending Trackball (ACTION_MOVE): 0:(0.0,-3.0)\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n    //[calendar_time:2025-07-19 21:58:49.953  system_uptime:565439222]\n    // Sending event #200\n    //[calendar_time:2025-07-19 21:58:50.055  system_uptime:565439325]\n    // Sending event #200\n:Sending Trackball (ACTION_MOVE): 0:(3.0,-3.0)\n:Sending Touch (ACTION_DOWN): 0:(733.0,789.0)\n:Sending Touch (ACTION_UP): 0:(747.0114,791.8333)\n:Sending Trackball (ACTION_MOVE): 0:(3.0,-3.0)\n:Sending Trackball (ACTION_UP): 0:(0.0,0.0)\n:Sending Touch (ACTION_DOWN): 0:(350.0,1525.0)\n:Sending Touch (ACTION_UP): 0:(346.91833,1534.8271)\n:Sending Touch (ACTION_DOWN): 0:(194.0,1509.0)\n:Sending Touch (ACTION_UP): 0:(204.74509,1509.5002)\n:Sending Trackball (ACTION_MOVE): 0:(2.0,-2.0)\n:Sending Trackball (ACTION_MOVE): 0:(1.0,4.0)\n:Sending Touch (ACTION_DOWN): 0:(736.0,686.0)\n:Sending Touch (ACTION_UP): 0:(758.32025,694.5196)\n:Sending Touch (ACTION_DOWN): 0:(864.0,2251.0)\n:Sending Touch (ACTION_UP): 0:(810.6849,2237.1882)\n:Sending Touch (ACTION_DOWN): 0:(736.0,257.0)\n:Sending Touch (ACTION_UP): 0:(781.5245,302.07172)\n:Sending Trackball (ACTION_MOVE): 0:(-4.0,1.0)\nEvents injected: 300\n:Sending rotation degree=0, persist=false\n:Dropped: keys=0 pointers=0 trackballs=0 flips=1 rotations=0\n## Network stats: elapsed time=8611ms (0ms mobile, 0ms wifi, 8611ms not connected)\n// Monkey finished",
  "stderr_tail": "args: [-p, com.hihonor.calculator, --throttle, 100, --ignore-crashes, --ignore-timeouts, --ignore-security-exceptions, -v, 300]\n arg: \"-p\"\n arg: \"com.hihonor.calculator\"\n arg: \"--throttle\"\n arg: \"100\"\n arg: \"--ignore-crashes\"\n arg: \"--ignore-timeouts\"\n arg: \"--ignore-security-exceptions\"\n arg: \"-v\"\n arg: \"300\"\ndata=\"com.hihonor.calculator\"\narg=\"--throttle\" mCurArgData=\"null\" mNextArg=3 argwas=\"--throttle\" nextarg=\"100\"\ndata=\"100\"\narg=\"--ignore-crashes\" mCurArgData=\"null\" mNextArg=5 argwas=\"--ignore-crashes\" nextarg=\"--ignore-timeouts\"\narg=\"--ignore-timeouts\" mCurArgData=\"null\" mNextArg=6 argwas=\"--ignore-timeouts\" nextarg=\"--ignore-security-exceptions\"\narg=\"--ignore-security-exceptions\" mCurArgData=\"null\" mNextArg=7 argwas=\"--ignore-security-exceptions\" nextarg=\"-v\"",
  "command_attempts": 1,
  "recovered_after_disconnect": false,
  "template_type": "monkey",
  "return_code": 0,
  "events_injected": 300
}
```
