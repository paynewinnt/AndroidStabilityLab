# Android Stability Lab V1 开发方案

## 1. 文档目标

本文档定义 `Android Stability Lab V1` 的技术实施方案。`V1` 的目标是打通稳定性任务执行闭环，让平台能够完成设备发现、任务创建、Run 创建、场景执行、异常识别、证据抓取、报告生成和结果查询。

## 2. 方案结论

`V1` 推荐方案：

**领域模块化内核 + 任务执行主线 + CLI/Web 双入口**

核心原则：

- 任务、设备、执行、异常、证据、报告全部沉淀为服务层和领域对象。
- CLI 与 Web 只作为入口，不承载核心业务规则。
- 执行链路必须可测试、可回放、可生成报告。
- 监控采样作为稳定性执行的基础能力，通过统一 adapter 接入。

## 3. V1 范围

### 3.1 必须具备

- 设备发现与状态同步。
- 创建任务。
- 创建 Run。
- 执行 Run。
- 支持 `monkey` 与 `cold_start_loop` 等首批模板。
- 执行中采集基础监控快照。
- 自动识别 crash、ANR、native crash、reboot、process exit、device offline、startup timeout。
- 自动抓取 logcat、bugreport、traces、tombstone 等证据。
- 生成 Markdown / HTML 报告。
- 支持 run 历史查询和详情查看。

### 3.2 不纳入 V1

- 完整团队协作流。
- 完整版本准入中心。
- 完整在线规则发布平台。
- 企业级 IAM / SSO。
- 团队级设备预约、配额和排班。

这些能力进入 V2/V3 或后续生产化阶段。

## 4. 架构分层

### 4.1 CLI/Web 入口层

职责：

- 接收用户输入。
- 调用应用服务。
- 输出 JSON、文本或 HTML 页面。

入口：

- `python -m stability.cli`
- `python -m stability.cli serve-web`

### 4.2 应用服务层

职责：

- 设备注册和同步。
- 任务定义。
- Run 创建。
- 执行编排。
- 报告生成。
- 历史查询。

主要模块：

- `stability/app/device_service.py`
- `stability/app/task_service.py`
- `stability/app/run_execution_service.py`
- `stability/app/report_service.py`
- `stability/app/run_history_service.py`

### 4.3 领域层

职责：

- 定义稳定领域对象和状态。
- 限制状态转换。
- 给 CLI、Web、服务层提供统一语义。

主要对象：

- `Device`
- `TaskDefinition`
- `TaskRun`
- `ExecutionInstance`
- `IssueRecord`
- `ArtifactRecord`

### 4.4 执行层

职责：

- 将 Run 展开为执行计划。
- 管理实例状态。
- 调用场景执行器。
- 处理重试和清理。

主要模块：

- `stability/execution/plan.py`
- `stability/execution/state_machine.py`
- `stability/scenario/`

### 4.5 基础设施层

职责：

- ADB 调用。
- 监控 adapter。
- 数据库连接。
- 文件与 artifact 路径规划。

主要模块：

- `stability/infrastructure/device_adapter.py`
- `stability/infrastructure/monitoring_*`
- `stability/infrastructure/persistence/`
- `stability/infrastructure/artifact_paths.py`

## 5. 执行流程

标准流程：

1. 用户创建任务，定义包名、模板、采样配置和目标设备策略。
2. 用户基于任务创建 Run。
3. 执行服务把 Run 展开为一个或多个执行实例。
4. 场景执行器在目标设备上执行操作。
5. 监控 adapter 采集性能快照或 trace。
6. issue detector 根据执行结果和日志识别问题。
7. artifact collector 抓取证据。
8. report service 生成报告。
9. run history service 提供查询和回看。

## 6. 异常与证据策略

异常识别至少覆盖：

- Java crash
- Native crash
- ANR
- Reboot
- Process exit
- Device offline
- Startup timeout

证据抓取至少覆盖：

- `logcat`
- `bugreport`
- `traces`
- `tombstone`
- 执行日志
- 监控 snapshot

证据抓取采用最佳努力策略：抓取失败需要记录错误，但不能导致整个执行结果丢失。

## 7. 数据与报告

V1 数据需要支持：

- 任务定义可查询。
- Run 可查询。
- 执行实例可查询。
- Issue 可追溯到实例和设备。
- Artifact 可追溯到 issue 和实例。
- 报告可打开、可导出、可作为后续分析输入。

报告至少输出：

- 任务信息。
- Run 信息。
- 设备信息。
- 执行结果。
- 异常摘要。
- 证据路径。
- 监控摘要。

## 8. 验收标准

V1 达到可验收状态时，应满足：

- CLI 可创建任务、创建 Run、执行 Run。
- Web 可查看任务、Run、设备和报告。
- 至少一个真实设备 smoke 可跑通。
- 异常链路可生成 issue 和 artifact。
- 报告中能看到执行结果、异常摘要和证据路径。
- 单元测试和 smoke 脚本可复核主链能力。

## 9. 后续衔接

V1 输出的任务、Run、Issue、Artifact、报告和监控数据，将作为后续能力的基础：

- V2 基于这些数据做 Top Issue、对比、回归和初步归因。
- V3 基于这些数据做 AdmissionCase、QualityGate、协作、准入和外部系统集成。
