# Execution Summary

- task_id: task_0aae5f86ad1942bab107d05f56e14fc2
- task_name: Monkey Stage3 Smoke
- run_id: run_a0d485eb673442d2b0641fbcff76fa9a
- instance_id: instance_df0ad3b5d547422ebda48b2c952a5f54
- device_id: dev-a
- status: failed
- monitoring_error: none
- scenario_note: Monkey 模板执行失败：设备 dev-a 当前不可用或未连接。
- issue_count: 1
- artifact_count: 1

## Issues

- [device_offline] 执行期间设备离线 (high)
  - summary: Monkey 模板执行失败：设备 dev-a 当前不可用或未连接。

## Artifacts

- [execution_log] runtime/tasks/task_0aae5f86ad1942bab107d05f56e14fc2/runs/run_a0d485eb673442d2b0641fbcff76fa9a/executions/instance_df0ad3b5d547422ebda48b2c952a5f54/devices/dev-a/artifacts/issue_698ee60fe47144859fed907cd6ffb582/execution.log
  - issue_id: issue_698ee60fe47144859fed907cd6ffb582

## Scenario Result

```json
{
  "device_id": "dev-a",
  "package_name": "com.example.demo"
}
```
