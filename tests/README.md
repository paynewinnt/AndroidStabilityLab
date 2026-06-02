# 测试说明

本文档只维护测试入口、测试分层和 smoke 使用口径。历史能力演进、验收结论和长篇说明应放到 `docs/计划/`、`docs/方案/` 或对应 runbook。

## 快速运行

从仓库根目录运行完整单元测试：

```bash
PYTHONPATH=. ./.venv/bin/python -m unittest discover -s tests -v
```

运行当前 Web Portal 相关回归：

```bash
PYTHONPATH=. ./.venv/bin/python -m pytest \
  tests/test_web_portal_read_only.py \
  tests/test_web_portal.py \
  tests/test_web_portal_device_pools.py \
  tests/test_web_quick_adb.py
```

运行指定测试文件：

```bash
PYTHONPATH=. ./.venv/bin/python -m pytest tests/test_task_service.py
```

## 测试分层

- `test_cli_*.py`：CLI parser、handler 和命令输出合同。
- `test_web_*.py`：Web 页面、JSON API、表单、只读入口和设备/ADB 页面。
- `test_*_service.py`：应用服务层，覆盖任务、执行、分析、准入、规则治理、outbox、runner 等业务链路。
- `test_*_runner.py`：场景 runner，包括 Monkey、冷启动、自定义自动化和设备循环。
- `test_monitoring_*.py` / `test_performance_*.py`：监控后端、趋势、阈值和性能风险。
- `test_app_errors.py` / `test_app_error_boundaries.py`：统一错误模型和边界响应。
- `tests/helpers/`：CLI/Web 测试数据、fake bundle 和断言辅助。

## Smoke 脚本

脚本位于 `scripts/`，用于本地或真机验收。先用 `bash -n` 检查脚本语法，再按需执行。

```bash
bash -n scripts/verify_v1_acceptance.sh
bash scripts/verify_v1_acceptance.sh

bash -n scripts/verify_cli_query_smoke.sh
bash scripts/verify_cli_query_smoke.sh --package-name com.example.app --device-id SERIAL --launch-activity .MainActivity

bash -n scripts/verify_web_portal_smoke.sh
bash scripts/verify_web_portal_smoke.sh
```

真机模板 smoke 需要 `adb` 可用，并传入真实 `package-name`、`device-id`、`launch-activity` 或 APK 路径。

## 文档边界

- 页面/API 清单以 `stability.web.manifest`、`/json-api`、`/api/manifest` 为准。
- README 只维护稳定入口，不维护完整 API 列表。
- 功能验收状态放在 `docs/Android Stability Lab未完成功能验收清单.md`。
- IM/飞书真实链路验收放在 `docs/运维/` 下的 runbook 和验收记录模板。
