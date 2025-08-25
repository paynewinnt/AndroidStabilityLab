# Android Stability Lab

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![入口](https://img.shields.io/badge/入口-CLI%20%2B%20Web-2d7d46.svg)](#快速开始)
[![测试](https://img.shields.io/badge/tests-pytest-0a7f3f.svg)](#测试)

[English](README.md) | 简体中文

Android Stability Lab 是一个本地优先的 Android 稳定性测试与分析工作台。它把设备发现、任务执行、证据采集、问题聚合、规则评审、无人值守巡检和轻量 Web 门户收口到一条可复现的工作流里。

当前推荐入口：

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

## 项目定位

这个项目适合用于：

- 本地稳定性任务执行和报告生成
- Android 真机或 TCP 设备的稳定性 smoke
- 问题聚合、版本/设备/场景对比和回归判断
- 规则回放、golden sample 验收、规则评审和基线审计
- 无人值守巡检、日报、周报和本地值班视图
- 团队内网演示、JSON/HTML/Markdown 产物共享

它当前不是完整企业级平台，不应直接理解为多租户 SaaS、完整 IAM、在线规则发布平台、团队级设备调度平台或生产级告警系统。

## 快速开始

### 环境要求

- Python 3.10+ 推荐
- `adb` 已加入 `PATH`
- 至少一台开启 USB 调试的 Android 设备，或一台可连接的 TCP 设备
- macOS 或 Linux shell 环境，用于运行仓库内 smoke 脚本

### 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
```

### 验证 CLI

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli --help
```

### 启动 Web 门户

```bash
PYTHONPATH=. ./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

访问：

- `http://127.0.0.1:8030/`
- `http://127.0.0.1:8030/health`

## 核心能力

- **执行闭环**：设备发现、任务定义、Run 创建、执行实例、日志、报告和异常产物。
- **场景 runner**：cold start loop、Monkey、安装卸载、前后台切换、重启、熄屏唤醒、设备轮转和自定义自动化。
- **监控采样**：内置 ADB 采样，并支持 SoloX 和 Perfetto 后端。
- **分析闭环**：Top Issue、问题组详情、版本/设备/场景对比、性能趋势和回归判断。
- **规则治理**：本地规则文件、规则 diff、规则 replay、golden suite、评审报告、基线晋升、回滚和审计。
- **无人值守**：周期巡检、设备补位、失败隔离、恢复探测、runner 心跳、日报和周报。
- **集成 outbox**：webhook 注册、事件投递、重试、dead-letter、worker 和本地 smoke。
- **本地 Web**：任务、性能、问题、runner、golden suite、准入和 JSON API 导航。

## 常用命令

```bash
# 设备
adb devices
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-devices --sync

# 任务与执行
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-task --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-run --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli execute-run --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-runs

# 分析与回归
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-top-issues --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli compare-issues --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli compare-performance-trends --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli judge-regression --help

# 规则与准入
PYTHONPATH=. ./.venv/bin/python -m stability.cli validate-analysis-rules
PYTHONPATH=. ./.venv/bin/python -m stability.cli replay-analysis-rules --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli verify-rule-replay-golden-samples --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli create-rule-review-report --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli list-admission-cases --help

# 无人值守
PYTHONPATH=. ./.venv/bin/python -m stability.cli configure-unattended-task --help
PYTHONPATH=. ./.venv/bin/python -m stability.cli patrol-unattended-tasks
PYTHONPATH=. ./.venv/bin/python -m stability.cli run-unattended-patrol-runner --help
```

## Web 页面

- `/`：首页摘要
- `/tasks`：任务和 Run 历史
- `/performance`：监控快照和 trace 链接
- `/issues`：Top Issue 聚合
- `/runner`：无人值守 runner 状态
- `/goldens`：golden suite 样本和 diff
- `/admission`：规则准入、基线、审计和对比
- `/json-api`：JSON API 导航

## 演示数据

仓库有意提交了一批演示数据，便于新 clone 后直接打开 Web 页面查看效果：

- `data/android_metrics.db`
- `data/android_metrics.db-shm`
- `data/android_metrics.db-wal`
- `runtime/admission_cases/`
- `runtime/analysis_*`
- `runtime/collaboration/`
- `runtime/platform_health/`
- `runtime/tasks/`
- `runtime/unattended_runner/`
- `runtime/apks/`

不会提交：

- `runtime/integration_outbox/webhooks.json`
- `.DS_Store`
- Python bytecode 和 cache 目录

公开 fork 前请重新检查 `data/` 和 `runtime/`，确认没有真实设备 ID、内网地址、token、组织内部日志或不应公开的 APK。

## 目录结构

```text
AndroidStabilityLab/
├── stability/                 # 主系统包
│   ├── app/                   # 应用服务
│   ├── application/           # 编排层
│   ├── artifact/              # 产物采集和证据解析
│   ├── cli/                   # CLI 入口和命令处理
│   ├── domain/                # 领域模型、枚举、错误和值对象
│   ├── execution/             # 执行计划、hook 和状态机
│   ├── infrastructure/        # ADB、监控、持久化和规则配置
│   ├── issue/                 # 问题检测
│   ├── repositories/          # 仓储实现
│   ├── scenario/              # 场景 runner
│   └── web/                   # 本地 Web 门户
├── config/                    # 本地 JSON 配置和规则
├── data/                      # 演示 SQLite 数据库和 WAL/SHM
├── docs/                      # 产品说明、计划和 runbook
├── runtime/                   # 演示报告、快照、runner 状态和产物
├── scripts/                   # smoke 和验收脚本
├── tests/                     # pytest 测试
└── requirements.txt           # 运行依赖
```

## 测试

从仓库根目录运行：

```bash
PYTHONPATH=. pytest -q
```

当前本地基线：

```text
447 passed, 12 subtests passed
```

常用 smoke：

```bash
bash scripts/verify_v1_acceptance.sh
bash scripts/verify_cli_query_smoke.sh
bash scripts/verify_web_portal_smoke.sh
```

## 安全说明

- 不要提交真实 webhook secret，`runtime/integration_outbox/webhooks.json` 已保留为本地未跟踪文件。
- `runtime/` 只应在复核后作为演示数据共享，里面可能包含设备 ID、内网地址、日志、APK 和报告。
- Web 门户默认按本地或可信内网使用设计，不应裸露到公网。
- 受信 header 身份只适合本地 SSO-like 接入，不等价于完整企业 IAM。
- IM/飞书链路必须完成真实 endpoint 验证后，才能作为生产告警链路使用。

## 贡献

欢迎贡献：

- 新的稳定性场景和 runner
- 更稳定的 ADB/监控适配
- 更准确的问题检测和证据解析
- 更小、更干净、更容易复现的演示数据
- 文档、示例和新手引导
- 不依赖私有设备的自动化测试

提交前建议运行：

```bash
PYTHONPATH=. pytest -q
```

## 许可证

公开发布前请补齐最终 `LICENSE` 文件，并让本节与许可证文件保持一致。
