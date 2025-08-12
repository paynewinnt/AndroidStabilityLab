# Android Stability Lab V1验收清单

本文档面向 `V1` 版本验收，目标是把“应该检查什么”与“如何一键执行”统一到同一份清单里。

## 1. 入口

默认安全回归入口：

```bash
bash scripts/verify_v1_acceptance.sh
```

该入口默认只执行本地安全项：

- `unittest discover`
- `compileall`
- smoke 脚本语法检查
- `stability.cli` 帮助与查询命令健全性检查
- `list-devices` / `show-device` / `list-tasks` / `show-task` / `list-runs` / `show-run` 的最小链路验证

如果需要把真机 smoke 一并纳入一次验收，可显式追加对应 flag：

```bash
bash scripts/verify_v1_acceptance.sh \
  --run-extended-artifacts-smoke \
  --run-cli-query-smoke \
  --run-monkey-smoke \
  --run-cold-start-smoke \
  --run-cold-start-multi-device-smoke \
  --run-cold-start-midrun-disconnect-smoke \
  --run-foreground-background-smoke \
  --run-web-foreground-background-smoke \
  --run-install-uninstall-smoke \
  --run-web-install-uninstall-smoke \
  --run-reboot-smoke \
  --run-web-reboot-smoke \
  --run-standby-wake-smoke \
  --run-web-standby-wake-smoke \
  --run-monkey-midrun-disconnect-smoke \
  --cold-start-package com.example.app \
  --cold-start-launch-activity .MainActivity \
  --cold-start-device-id SERIAL_A \
  --cold-start-device-id SERIAL_B \
  --cold-start-disconnect-device-id SERIAL_A \
  --foreground-background-package com.example.app \
  --foreground-background-launch-activity .MainActivity \
  --foreground-background-device-id SERIAL_A \
  --install-uninstall-package com.example.app \
  --install-uninstall-apk-path /path/app.apk \
  --install-uninstall-device-id SERIAL_A \
  --reboot-package com.example.app \
  --reboot-device-id SERIAL_A \
  --standby-wake-package com.example.app \
  --standby-wake-device-id SERIAL_A \
  --monkey-package com.example.app \
  --monkey-device-id SERIAL_OR_HOST_PORT
```

## 2. 前置条件

- `adb` 已在 `PATH` 中可用
- `./.venv/bin/python` 或 `python3` 可用
- 若执行真机 smoke，目标设备已在线且目标包可安全测试
- 若要验证 `show-run`，持久化库中至少已有一个 run；若没有，脚本会保留 `list-runs` 检查并跳过 `show-run`

## 3. Must 验收项

以下项目应全部通过，`V1` 才视为达到可验收状态。

### 3.1 本地基线

- `unittest discover -s tests -v` 通过
- `compileall stability tests` 通过
- 现有 smoke 脚本 `bash -n` 语法检查通过
- `python -m stability.cli --help`、`list-devices --help`、`show-device --help`、`list-tasks --help`、`show-task --help`、`list-runs --help`、`show-run --help` 可用
- `python -m stability.cli list-devices` 与 `list-tasks` 可返回合法 JSON
- 若库中已有设备，`python -m stability.cli show-device --device-id ...` 可返回设备详情
- 若需要读取最新设备状态，`python -m stability.cli list-devices --sync` 与 `show-device --sync` 可在查询前完成一次全量 `adb` 同步；`list-devices --sync-device SERIAL` 与 `show-device --sync-target-only` 可只刷新目标设备
- 若库中已有 task，`python -m stability.cli show-task --task-id ...` 可返回任务详情
- `python -m stability.cli list-runs --limit 1` 可返回合法 JSON
- 若库中已有 run，`python -m stability.cli show-run --run-id ...` 可返回 run 详情、实例明细、`report_path` 与执行日志路径

### 3.2 功能主链

- 可创建任务并生成执行实例
- `Monkey` 与 `冷启动循环` 模板可执行
- 基础异常可形成 issue 记录
- issue 触发后可抓取最小证据
- 执行结束后可输出统一 `Markdown + HTML` 报告
- 历史查询最小入口可查看设备、任务、run 摘要及对应详情

### 3.3 稳定性主链

- 多设备并发执行可完成且无明显阻塞性问题
- `stop_on_failure` 可取消未开始实例
- `execute-run` 失败重试只对可恢复错误生效
- `cold_start_loop` 支持 TCP 设备在每轮前与启动失败/超时后的单次重连重试
- `Monkey` 支持 TCP 设备在启动前离线与命令失败/超时后的单次重连重试

## 4. 建议真机验收项

以下项目建议至少保留一份最新通过记录。

### 4.1 冷启动单设备成功链

命令：

```bash
bash scripts/verify_cold_start_loop_smoke.sh --package-name PACKAGE --device-id SERIAL --launch-activity .MainActivity
```

通过标准：

- 脚本退出码为 `0`
- 输出包含 `task_id`、`run_id`、`report_path`
- `report_path` 指向的报告文件存在

### 4.2 CLI 查询与报告/证据链

命令：

```bash
bash scripts/verify_cli_query_smoke.sh --package-name PACKAGE --device-id SERIAL --launch-activity .MainActivity
```

通过标准：

- 脚本退出码为 `0`
- `show-device --sync` 与 `list-devices --sync` 可成功返回
- `list-tasks`、`show-task`、过滤后的 `list-runs`、`show-run` 可成功返回
- `run_status=failed`，用于稳定触发 `startup_timeout`
- `report.md` 与 `report.html` 都存在
- `bugreport.txt` 已被真实抓取，且报告中包含对应引用

### 4.3 扩展证据链

命令：

```bash
bash scripts/verify_extended_artifacts_smoke.sh --package-name PACKAGE --device-id SERIAL --launch-activity .MainActivity
```

通过标准：

- 脚本退出码为 `0`
- `run_status=failed`，用于稳定触发 `startup_timeout`
- `bugreport.txt`、`dropbox.txt`、`meminfo.txt` 三类证据在同一条 issue 证据目录下真实落盘
- `report.md` 与 `report.html` 都包含这三类证据引用

### 4.4 Monkey 单设备成功链

命令：

```bash
bash scripts/verify_monkey_smoke.sh --package-name PACKAGE --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- `run_status=success`
- 唯一实例为 `success`
- `report_path` 与 `execution.log` 存在

### 4.5 冷启动双设备并发成功链

命令：

```bash
bash scripts/verify_cold_start_loop_multi_device_smoke.sh --package-name PACKAGE --device-id SERIAL_A --device-id SERIAL_B --launch-activity .MainActivity
```

通过标准：

- `run_status` 为成功态
- `instance_status_counts` 与设备数匹配
- `report_paths` 完整返回

### 4.6 冷启动中途掉线恢复链

命令：

```bash
bash scripts/verify_cold_start_loop_midrun_disconnect_smoke.sh \
  --package-name PACKAGE \
  --disconnect-device-id SERIAL_A \
  --device-id SERIAL_A \
  --device-id SERIAL_B \
  --launch-activity .MainActivity
```

通过标准：

- `run_status=success`
- 断开目标实例最终仍为 `success`
- 执行日志中可看到 reconnect/retry 痕迹

### 4.7 前后台切换单设备成功链

命令：

```bash
bash scripts/verify_foreground_background_loop_smoke.sh --package-name PACKAGE --device-id SERIAL --launch-activity .MainActivity
```

通过标准：

- 脚本退出码为 `0`
- CLI 链路完整完成 `create-task`、`create-run`、`execute-run`
- `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.8 Web 任务大厅前后台切换成功链

命令：

```bash
bash scripts/verify_web_tasks_foreground_background_smoke.sh --package-name PACKAGE --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 先访问 `/tasks` 并确认页面包含创建任务、创建 Run、执行 Run 三个表单 action
- 通过 `/tasks/actions/create-task` 创建 `foreground_background_loop` 任务
- 通过 `/tasks/actions/create-run` 生成 Run
- 通过 `/tasks/actions/execute-run` 触发执行
- `/api/runs/<run_id>` 返回 `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.9 安装卸载循环成功链

命令：

```bash
bash scripts/verify_install_uninstall_loop_smoke.sh --package-name PACKAGE --apk-path /path/app.apk --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 默认先执行 `adb install -r APK` 作为覆盖安装预置
- CLI 链路完整完成 `create-task`、`create-run`、`execute-run`
- `task_params.apk_path` 被正确保存
- `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.10 Web 任务大厅安装卸载循环成功链

命令：

```bash
bash scripts/verify_web_tasks_install_uninstall_smoke.sh --package-name PACKAGE --apk-path /path/app.apk --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 先访问 `/tasks` 并确认页面包含三个任务 action
- 通过 `/tasks/actions/create-task` 创建 `install_uninstall_loop` 任务
- 通过 `/tasks/actions/create-run` 生成 Run
- 通过 `/tasks/actions/execute-run` 触发执行
- `/api/runs/<run_id>` 返回 `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.11 重启循环成功链

命令：

```bash
bash scripts/verify_reboot_loop_smoke.sh --package-name PACKAGE --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 设备被真实 `adb reboot` 后能重新回到可用状态
- `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.12 Web 任务大厅重启循环成功链

命令：

```bash
bash scripts/verify_web_tasks_reboot_loop_smoke.sh --package-name PACKAGE --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 通过 `/tasks` 页面 action 创建 `reboot_loop` 任务、Run 并触发执行
- 设备被真实 `adb reboot` 后能重新回到可用状态
- `/api/runs/<run_id>` 返回 `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.13 息屏唤醒循环成功链

命令：

```bash
bash scripts/verify_standby_wake_loop_smoke.sh --package-name PACKAGE --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 设备完成真实息屏、唤醒和可选解锁按键事件
- `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.14 Web 任务大厅息屏唤醒循环成功链

命令：

```bash
bash scripts/verify_web_tasks_standby_wake_smoke.sh --package-name PACKAGE --device-id SERIAL
```

通过标准：

- 脚本退出码为 `0`
- 通过 `/tasks` 页面 action 创建 `standby_wake_loop` 任务、Run 并触发执行
- `/api/runs/<run_id>` 返回 `run_status=success`
- 唯一实例为 `success`
- `report_path` 指向的报告文件存在

### 4.15 Monkey 中途掉线恢复链

命令：

```bash
bash scripts/verify_monkey_midrun_disconnect_smoke.sh --package-name PACKAGE --device-id HOST:PORT
```

通过标准：

- `run_status=success`
- `execution.log` 中包含 `reconnect recovered command path`

## 5. 输出物

`scripts/verify_v1_acceptance.sh` 会在 `/tmp/android_stability_lab_v1_acceptance_<timestamp>` 下输出：

- 每一步的 `stdout` / `stderr`
- `summary.md`

验收结论建议至少保留：

- 最新一份 `summary.md`
- 真机 smoke 的 `task_id` / `run_id`
- 关键 `report.md` 与 `execution.log` 路径

## 6. 通过结论

满足以下条件时，可判定 `V1` 达到可验收状态：

- `Must` 验收项全部通过
- 至少保留一组最新真机 smoke 通过记录
- 当前已知剩余问题不影响 `V1` 的执行闭环可信度
