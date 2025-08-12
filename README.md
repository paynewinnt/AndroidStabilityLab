# Android Stability Lab

[![Python](https://img.shields.io/badge/Python-3.7%2B-blue.svg)](https://www.python.org/)
[![Entry](https://img.shields.io/badge/Entry-CLI%20%2B%20Web-2d7d46.svg)](#当前推荐入口)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

`Android Stability Lab` 是一个面向 Android 稳定性场景的本地优先测试与分析工作台，当前推荐围绕 `stability/` 体系使用，重点覆盖：

- 稳定性任务执行与报告输出
- 问题聚合、回归对比与规则治理
- 无人值守巡检、日/周报和本地 Web 门户
- `golden suite` 样本库、规则准入基线审计和本地报告/JSON/产物共享

> 当前推荐入口是 `stability/`：`python -m stability.cli` 和 `serve-web` 是优先使用方式。

当前阶段口径：`V1 / V2` 主链已基本闭环，`V3` 最小流程闭环已落地。后续重点是生产化治理、真实平台适配、长稳产品化、规则/证据精度和长时运行可靠性。

部署与共享口径：默认本地部署、本地执行、自看自用；需要共享时，优先通过本地 Web、报告、JSON、HTML/Markdown、分析快照、规则评审报告、准入对比和附件产物导出完成。当前不应理解为完整多租户平台、完整 IAM、完整在线规则发布平台或完整审批流已经完成。

P0 边界口径：本仓库当前按“本地优先平台”收口，`serve-web`、JSON API、outbox/worker、受信 header SSO、规则准入和长稳 runner 都应先被理解为本地或团队内网共享能力。凡是依赖外部真实平台、长时运行或真实设备结果的能力，必须完成对应真实验收并留下可复核记录后，才允许写成“已完成真实链路”。

必须真实验收后才算完成的能力包括：

- 外部通知、CI 回写、缺陷系统和提测平台对接：本地 mock/smoke 只证明出站合同和 worker 可运行，不能替代真实 endpoint 验收。
- IM/飞书通知链路：必须按 runbook 完成本地 smoke、真实 2 小时试运行和真实 24 小时长时联调；未跑满 24 小时前，不写成真实通知链路已完成。
- 长稳任务产品化：必须至少使用真实设备完成一轮执行，并能在 `/tasks`、`/runner`、`/performance` 和日报/周报里串起任务、轮次、设备、结果和产物。
- 设备池治理：必须能在轮次记录、runner 历史、巡检摘要或日报/周报中复核断连、失败、重试、隔离和恢复探测记录，才算完成本地无人值守调度闭环。
- 高级异常识别和性能风险阈值：没有真实样本标定、多证据确认或结构化解析前，只按启发式/规则式初步识别验收，不按生产级智能诊断或 AI 根因诊断验收。
- SSO、用户目录、责任检索和规则配置入口：当前只按本地 session、受信 header、只读目录/检索和本地规则文件治理验收，不按完整企业级 IAM、多租户隔离、在线规则发布或审批平台验收。

当前重点能力状态统一按下面口径理解，避免把阶段性能力误写成完整平台完成：

| 能力 | 当前状态 | 可依赖范围 | 不建议依赖为 |
| --- | --- | --- | --- |
| IM/飞书通知 | 部分可用 | 平台侧 `im_notify` / `feishu_bot` 合同、webhook 注册、worker、本地 mock/smoke、outbox receipt 观测可用于联调准入 | 真实 24 小时 IM 链路、生产群通知、完整订阅降噪和真实接收方幂等验收完成 |
| SSO/身份 | 部分可用 | 本地 session、受信 SSO header claims、写操作身份解析、审计增强、只读用户目录和责任检索 | 完整企业级 OIDC/LDAP/SSO、独立 IAM、多租户数据隔离、复杂组织权限平台 |
| 设备调度 | 部分可用 | 本地设备注册、状态同步、无人值守 runner、主备/轮转/补位、隔离和恢复探测 | 团队级设备预约、配额、审批、排班、维护窗口和跨团队设备平台 |
| 规则在线发布 | 不建议依赖 | 只读规则配置中心、候选编辑预览、校验、diff、回放、评审、基线审计和本地规则文件治理 | 在线保存、发布、审批、回滚和多级变更工作流 |

## 项目主要作用

这个项目的核心作用，是把 Android 稳定性测试里原本分散、依赖人工、难以复盘的工作，收口成一条可重复执行、可追溯分析、可持续巡检的主链路：

- 把设备、任务、执行、异常、证据、报告接到同一套 CLI 和本地 Web 入口里
- 把一次稳定性执行沉淀成可查询的 Run、Issue、Artifact、日报和周报
- 把版本、设备、场景之间的差异比较和回归判断标准化
- 把规则回放、`golden suite`、基线审计接进规则治理和准入评审流程
- 把值班视角需要的 runner 心跳、失败率、掉线率、隔离设备数前置到首页和 `/runner`

## 主要解决的问题

它主要解决的是 Android 稳定性工作里几类很常见的落地问题：

- 手工执行零散：任务靠临时 `adb` 命令和个人脚本完成，难复用、难交接
- 失败复盘困难：异常发生后证据不全，日志、附件和报告分散在不同位置
- 回归判断不稳定：版本之间的问题增减、性能波动和规则变化缺少统一比较口径
- 长稳值班成本高：无人值守任务失败、设备掉线、设备隔离往往要靠人盯
- 准入治理不闭环：规则变更、`golden suite` 验收、基线变化和审计记录缺少统一入口
- 新人理解成本高：如果没有一份主线清晰的入口说明，很容易把 CLI、Web、报告和准入能力割裂理解

## 当前推荐入口

```bash
# 查看 CLI 总入口
./.venv/bin/python -m stability.cli --help

# 启动本地 Web 门户
./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

## 当前主线能力

### V1 执行闭环

- 设备发现、任务定义、Run 创建与执行实例编排
- `cold_start_loop`、`Monkey` 等稳定性场景执行
- 异常识别、证据抓取、执行日志、`Markdown + HTML` 报告
- 失败分类重试、清理、TCP 设备单次重连恢复

### V2 分析闭环

- `Top Issue` 聚合、问题组详情和多维对比
- 版本 / 设备 / 场景维度的性能趋势比较与回归判断
- 分析快照、规则回放、规则治理与差异比较
- `golden suite` 样本验收、draft 提升、规则评审报告与基线审计

### V3 最小闭环

- 无人值守任务配置、定时巡检、失败隔离和自动恢复探测
- runner 心跳、单实例锁、最近 patrol 历史
- 自动日报、周报和首页摘要卡
- 本地 Web 门户：`/`、`/tasks`、`/performance`、`/issues`、`/runner`、`/goldens`、`/admission`、`/json-api`
- 准入单主对象：`AdmissionCase` 稳定合同、`case_trace` 证据链、准入详情页与 CLI 查询入口
- 最小协作、外部 outbox/worker/API 骨架、受信 header SSO 最小接入和只读用户/责任检索入口

## 快速开始

### 1. 准备环境

- Python `3.7+`
- 可用的 `adb`
- 至少一台开启 USB 调试的 Android 设备，或可连通的 TCP 设备

### 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 当前仓库的 `requirements.txt` 仅保留 CLI/Web 和稳定性主线需要的依赖。

### 3. 验证入口

```bash
adb devices
./.venv/bin/python -m stability.cli --help
./.venv/bin/python -m stability.cli serve-web --host 127.0.0.1 --port 8030
```

启动后可访问：

- `http://127.0.0.1:8030/`
- `http://127.0.0.1:8030/health`

## 常用命令

下面这些命令能覆盖当前大部分日常使用场景，具体参数请再追加 `--help`。

### 任务与执行

```bash
./.venv/bin/python -m stability.cli create-task --help
./.venv/bin/python -m stability.cli create-run --help
./.venv/bin/python -m stability.cli execute-run --help
./.venv/bin/python -m stability.cli list-tasks
./.venv/bin/python -m stability.cli show-task --help
./.venv/bin/python -m stability.cli list-runs
./.venv/bin/python -m stability.cli show-run --help
```

### 监控后端

当前执行链路已经支持通过统一的 `monitoring adapter` 切换不同监控后端：

- `adb_collector`：默认基础链路，提供 ADB 快照采样与本地持久化能力
- `solox`：接入 SoloX Python API，适合无 Root 的一站式 CPU / Memory / Network / Battery / FPS / GPU 采样
- `perfetto`：接入 Perfetto trace sidecar，适合更深入的系统级 tracing；默认会把 trace 文件挂到执行实例产物目录

后端选择入口：

- 全局默认配置：`config/monitoring.json`
- 单次执行覆盖：`--monitoring-backend adb_collector|solox|perfetto|auto|disabled`

```bash
# 用 SoloX 跑一次现有 Run
./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend solox

# 用 Perfetto 作为本次执行的 tracing sidecar
./.venv/bin/python -m stability.cli execute-run --run-id <run_id> --monitoring-backend perfetto
```

### 设备与查询

```bash
./.venv/bin/python -m stability.cli list-devices --sync
./.venv/bin/python -m stability.cli show-device --help
./.venv/bin/python -m stability.cli list-top-issues --help
./.venv/bin/python -m stability.cli show-issue-group --help
./.venv/bin/python -m stability.cli compare-issues --help
./.venv/bin/python -m stability.cli compare-performance-trends --help
./.venv/bin/python -m stability.cli judge-regression --help
```

### 无人值守与巡检

```bash
./.venv/bin/python -m stability.cli configure-unattended-task --help
./.venv/bin/python -m stability.cli list-unattended-tasks
./.venv/bin/python -m stability.cli patrol-unattended-tasks
./.venv/bin/python -m stability.cli run-unattended-patrol-runner --help
./.venv/bin/python -m stability.cli build-unattended-daily-report --help
./.venv/bin/python -m stability.cli build-unattended-weekly-report --help
```

### 规则治理与准入

```bash
./.venv/bin/python -m stability.cli replay-analysis-rules --help
./.venv/bin/python -m stability.cli verify-rule-replay-golden-samples --help
./.venv/bin/python -m stability.cli create-rule-review-report --help
./.venv/bin/python -m stability.cli list-admission-cases --help
./.venv/bin/python -m stability.cli show-admission-case --baseline-key <baseline_key>
./.venv/bin/python -m stability.cli show-rule-review-report-baseline --help
./.venv/bin/python -m stability.cli create-rule-review-report-baseline-audit --help
```

## Web 门户

`python -m stability.cli serve-web` 会启动一个无额外 Web 依赖的本地门户。它可以作为本机或团队内网共享入口使用，但当前仍以本地优先为主，不按完整在线平台、多租户隔离、完整企业级 IAM、团队级设备调度平台或在线规则发布平台验收。

当前主页面包括：

- `/`：首页摘要，聚合设备、任务、问题、runner、latest daily report、latest weekly report
- `/tasks`：任务与 Run 历史
- `/performance`：最近监控快照、backend 摘要与 trace/snapshot 下钻
- `/issues`：`Top Issue` 聚合与样本下钻
- `/runner`：patrol runner 状态、心跳、最近巡检、日/周报摘要
- `/goldens`：正式 `golden suite` 样本库与 diff 下钻
- `/admission`：规则准入基线、`AdmissionCase`、latest audit、comparison report 汇总
- `/json-api`：浏览器友好的 JSON API 导航页

同时提供一组只读 JSON 端点：

- `/api/home`
- `/api/tasks`
- `/api/performance`
- `/api/issues`
- `/api/runner`
- `/api/goldens`
- `/api/admission`
- `/api/admission/cases`
- `/api/admission/cases/<baseline_key>`
- `/api/integration/outbox`
- `/health`

共享产物优先使用本地报告、JSON、HTML/Markdown、分析快照、规则评审报告、准入对比和附件路径清单；如需接入 CI、IM、缺陷系统或提测平台，应按当前 outbox/webhook/API 合同做真实平台适配。

## 项目结构

```text
AndroidStabilityLab/
├── stability/                 # 当前主系统
│   ├── app/                   # 应用服务
│   ├── cli/                   # CLI 入口
│   ├── domain/                # 领域模型与值对象
│   ├── execution/             # 执行计划与状态机
│   ├── infrastructure/        # ADB / persistence / artifact 适配
│   ├── issue/                 # 异常检测
│   ├── repositories/          # 仓储实现
│   ├── scenario/              # Monkey / cold_start_loop 等执行器
│   └── web/                   # 本地 Web 门户
├── config/                    # 规则、数据库与运行配置
├── docs/                      # PRD、方案、开发计划
├── scripts/                   # smoke / 验收脚本
├── tests/                     # 单测与说明
├── runtime/                   # 报告、快照、runner 状态等运行产物
├── data/                      # 本地数据与数据库文件
└── README.md
```

## 测试与验证

单元测试：

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

常用 smoke 脚本：

```bash
bash scripts/verify_v1_acceptance.sh
bash scripts/verify_cli_query_smoke.sh
bash scripts/verify_web_portal_smoke.sh
bash scripts/verify_monkey_smoke.sh
bash scripts/verify_cold_start_loop_smoke.sh
bash scripts/verify_foreground_background_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash scripts/verify_web_tasks_foreground_background_smoke.sh --package-name com.example.app --device-id SERIAL
bash scripts/verify_install_uninstall_loop_smoke.sh --package-name com.example.app --apk-path /path/app.apk --device-id SERIAL
bash scripts/verify_web_tasks_install_uninstall_smoke.sh --package-name com.example.app --apk-path /path/app.apk --device-id SERIAL
bash scripts/verify_reboot_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash scripts/verify_web_tasks_reboot_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash scripts/verify_standby_wake_loop_smoke.sh --package-name com.example.app --device-id SERIAL
bash scripts/verify_web_tasks_standby_wake_smoke.sh --package-name com.example.app --device-id SERIAL
```

更完整的测试、真机 smoke 和成功判定标准见 [tests/README.md](tests/README.md)。

## 文档导航

- 产品需求：[docs/prd/Android Stability Lab产品需求文档.md](docs/prd/Android%20Stability%20Lab产品需求文档.md)
- 总开发计划：[docs/计划/Android Stability Lab开发计划.md](docs/计划/Android%20Stability%20Lab开发计划.md)
- `V3` 开发计划：[docs/计划/versions/Android Stability Lab V3开发计划.md](docs/计划/versions/Android%20Stability%20Lab%20V3开发计划.md)
- 项目文件说明：[docs/项目文件说明.md](docs/项目文件说明.md)

## 仓库说明

- 新增业务与文档默认以 `stability/`、CLI 和本地 Web 门户为准。
- `core/`、`database/`、`utils/` 等目录目前主要作为基础设施、存储和通用工具补充存在；新增稳定性业务默认沉淀到 `stability/`。
- 阅读代码或排查问题时，优先从 `stability/`、`tests/`、`docs/` 和 `scripts/` 开始更高效。

## 故障排查

### ADB 连接异常

```bash
adb devices
adb kill-server
adb start-server
```

### CLI / Web 启动异常

- 先确认虚拟环境已安装依赖
- 再确认数据库配置可用，默认持久化链路依赖 SQLAlchemy
- 如果只是在看命令帮助，`python -m stability.cli --help` 可先独立验证 CLI 装配是否正常

### runner / 报告产物位置

- 巡检相关运行文件默认落在 `runtime/unattended_runner/`
- 分析快照、评审报告、审计报告等也都在 `runtime/` 下分目录留档

## 许可证

本项目采用 [MIT License](LICENSE)。
