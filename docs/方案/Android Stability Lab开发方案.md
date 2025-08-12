# Android Stability Lab 开发方案

## 1. 文档目标

本文档用于定义 `Android Stability Lab` 的技术方案，统一架构、技术栈、模块划分、数据模型方向、存储策略和实施方案。

本文档聚焦“怎么做”，不再展开产品版本需求本身。

## 2. 子方案文档

- `V1` 最终开发方案：[`Android Stability Lab V1开发方案.md`](./Android%20Stability%20Lab%20V1%E5%BC%80%E5%8F%91%E6%96%B9%E6%A1%88.md)
- 性能采样子系统方案：[`性能采样子系统方案.md`](./%E6%80%A7%E8%83%BD%E9%87%87%E6%A0%B7%E5%AD%90%E7%B3%BB%E7%BB%9F%E6%96%B9%E6%A1%88.md)

后续所有细分技术方案，都应作为本文件的子方案文档沉淀在 `docs/方案/` 目录下。

## 3. 总体方案结论

`Android Stability Lab` 的推荐方案不是：

- 纯桌面单体工具
- 纯服务端重执行平台

推荐方案为：

**本地执行代理 + 分析/准入中枢 + 逐步平台化的 Web 与集成层**

这是当前项目演进成本、执行效率和平台可扩展性之间最平衡的路线。

当前代码阶段判断：

- `V1` 执行主链已经可用：任务、Run、实例执行、设备管理、无人值守巡检已具备最小闭环
- `V2` 分析主链已经可用：`top issues / comparison / performance trend / regression / snapshot / attribution` 已形成主系统
- `V3` 已经不是纯规划状态：当前已有 Web 主入口、runner 状态页、Golden Suite、准入下钻、质量门禁领域模型、最小协作动作和本地 integration outbox
- 当前 Web 入口的定位必须明确为“本地运维控制台”，适合值班、排查和本地演示，不等同于可直接对团队外放的正式生产平台
- 下一阶段技术重点不应回到“继续堆只读页面”，而应放在 `可写协作闭环 + 对外事件/API + 鉴权/审计边界 + 外部系统集成`
- 当前协作闭环已经不只覆盖 Issue：`AdmissionCase` 也已具备最小认领、评论、状态流转与协作时间线
- 当前身份边界已经不只停留在 `actor_id`：服务端会稳定解析并审计 `identity_id / session_id / auth_mechanism / session_source / audit_event_id / permission_check_id`
- 当前已进入“本地正式边界”阶段：支持本地 session 签发、过期、吊销和 token 生命周期治理，但仍不是面向团队在线平台的统一登录体系

## 4. 技术栈建议

### 4.1 执行代理层

- 语言：`Python`
- 责任：ADB 控制、设备发现、场景执行、高频采样、异常初检、日志抓取

选择原因：

- 当前项目已有 Python 基础
- ADB、脚本控制、日志解析生态成熟
- 适合快速实现本地执行代理

### 4.2 中央平台后端

- 当前已落地形态：`Python` 服务层 + `stdlib HTTP portal`
- 当前责任：问题聚合、回归分析、报告管理、准入评估、巡检状态、Issue/AdmissionCase 最小协作动作、本地事件出口
- 后续正式平台建议：在现有领域服务稳定后，再补 `API / 鉴权 / 授权 / 审计 / 回调安全`

说明：

- 现阶段不建议为了“平台感”提前推倒重做
- 也不应把当前 `ThreadingHTTPServer + GET/POST portal` 误判为最终平台后端
- 推荐做法是继续复用现有 `stability/` 服务层，把正式 API 层作为下一层能力逐步加上去
- 当前 portal 已经具备最小写能力，写能力边界以“本地 actor 注册表 + 本地签发 session + permission check + 服务端审计”来保证
- 这足以支持本地值班和开发阶段验证，也符合“本地部署、自看自用、必要时导出数据共享”的主形态；若要对团队外放，仍必须补更正式的用户目录、接口安全和组织边界

### 4.3 异步任务与调度

- 当前已落地：本地/进程内任务编排 + 巡检 runner + 文件型快照/报告/审计存储
- 后续建议：当 IM、回调、补偿、异步通知和跨节点调度成为真实需求后，再引入独立任务队列

当前结论：

- 还不需要为了阶段感强行引入 `Redis + Celery`
- 但已经需要抽象稳定的事件出口和补偿边界，当前最小实现以 `integration_outbox` 为主

### 4.4 数据存储

- 当前已落地：结构化数据按仓储能力分别落在数据库或运行目录；快照、报告、基线、审计、协作留痕、outbox 以文件持久化为主
- 后续建议：当团队协作、权限、审计、外部集成明显增多后，再评估把 `quality gate / collaboration / outbox` 等对象迁入统一持久化模型
- 附件存储：仍以本地文件系统和运行目录为主，平台化后再评估 `MinIO / S3`

### 4.5 前端形态

- 当前主入口：`python -m stability.cli` 和 `python -m stability.cli serve-web`
- 当前 Web：依赖极少、可本地启动的运维控制台
- 后续正式团队入口：如确实需要多人在线协作、统一登录和外部回写，再评估独立前端与正式 API 组合

结论：

- 现在应先补业务闭环，而不是先补前后端壳子
- 是否引入 `React + TypeScript + Vite`，应由正式平台化需求驱动，而不是由当前 portal 形态倒推

## 5. 架构分层

### 5.1 本地执行代理

职责：

- 设备接入
- ADB 控制
- 模板执行
- 高频采样
- 异常初检
- 证据本地抓取
- 本地报告生成
- 实时性能监控与图表数据供给

特点：

- 靠近设备
- 低延迟
- 适合处理高频执行和大附件抓取

### 5.2 分析与准入中枢

职责：

- 问题聚合
- Top Issue
- 回归分析
- 性能趋势对比
- 分析快照与报告
- 准入规则与质量门禁
- 基线、审计和可追溯结论

特点：

- 是当前 `stability/` 主系统的核心
- 既服务 CLI，也服务 Web portal
- 不承担高频设备执行，但负责把执行结果转化为可复用结论

### 5.3 Web 与协作层

职责：

- 提供统一查看入口
- 提供最小可写协作动作，如认领、评论、状态流转、人工覆盖
- 展示 runner / issue / golden / admission 的可追溯下钻视图

当前约束：

- 当前实现是本地运维控制台，不是正式团队平台
- 更适合本地部署、自看自用和导出报告/JSON/产物后共享，不应默认直接绑定到团队生产网络
- 后续如需团队外放，必须补上认证、授权、审计、接口安全和限流边界

### 5.4 事件与集成层

职责：

- 对外沉淀稳定事件，如问题认领、状态变更、门禁覆盖、runner 异常
- 为 IM、缺陷系统、提测平台、CI/CD 提供统一对接出口

当前形态：

- 以 `integration_outbox` 和本地 webhook 配置为最小起点
- 当前已覆盖的问题/准入事件包括：问题认领、问题评论、问题状态流转、`AdmissionCase` 认领、`AdmissionCase` 评论、`AdmissionCase` 状态流转、人工覆盖
- 尚未形成正式开放 API、回调签名校验和完整失败补偿体系

### 5.4.1 本地会话与审计边界说明

当前本地正式边界设计如下：

- 读操作仍允许本地快速切换 actor，用于值班和排查
- 写操作只接受服务端解析出的有效 session 或受信 actor，不信任表单里的 `actor_id / identity_id / session_id`
- 本地 session 已支持签发、过期、吊销和 token 生命周期治理
- 服务端会把 `identity_id / session_id / auth_mechanism / session_source / identity_boundary / audit_event_id / permission_check_id` 一起落入审计源
- permission check 不再只靠角色文案，而是走显式的本地 permission matrix

这层能力的定位必须说清楚：

- 它首先服务于本地控制台、值班排查、开发验证
- 默认不是“不同人看不同数据”的在线多租户平台，而是本地部署、本机看本机数据
- 需要共享时，更推荐导出报告、JSON 和运行产物给别人看
- 它避免了继续让 Web 直接信任用户可填的 `actor_id`
- 但它还没有正式用户目录、组织隔离和更复杂的权限继承能力

### 5.5 数据与附件流

策略如下：

- 元数据优先上传
- 关键附件按需上传
- 超大附件延迟上传或仅保留本地
- 中央平台优先保存索引、摘要和报告快照

## 6. 模块划分建议

建议按以下核心模块重构：

### 6.1 设备模块

- `device_manager`
- 负责设备发现、状态同步、分组标签、占用状态

### 6.2 任务模块

- `task_scheduler`
- 负责任务创建、分发、执行实例和状态流转

### 6.3 场景模块

- `scenario_runner`
- 负责模板执行、参数管理和场景步骤编排

### 6.4 异常模块

- `issue_detector`
- 负责异常识别、issue 生成、规则匹配

### 6.5 证据模块

- `artifact_collector`
- 负责日志抓取、附件命名、归档和清理

### 6.6 报告模块

- `report_service`
- 负责任务报告、分析快照、准入报告

### 6.7 分析模块

- `analysis_service`
- 负责问题聚合、Top Issue、回归分析、初步归因

## 7. 数据模型方向

### 7.1 V1 核心数据对象

- `device_inventory`
- `scenario_definition`
- `test_task`
- `task_execution`
- `issue_event`
- `issue_artifact`

复用现有采样对象：

- `monitoring_session`
- `system_performance`
- `app_performance`
- `network_stats`
- `fps_data`
- `power_consumption`

说明：

- 这些现有性能采样对象不应被废弃
- `V1` 之后它们应继续作为任务执行、报告生成和问题分析的底层数据来源

### 7.2 V2 增量数据对象

- `issue_fingerprint`
- `regression_baseline`
- `scenario_step_execution`
- `comparison_snapshot`

### 7.3 V3 增量数据对象

- `collaboration_role`
- `collaboration_actor`
- `issue_collaboration_record`
- `issue_comment`
- `quality_gate_override`
- `quality_gate_rule`
- `quality_gate_result`
- `integration_outbox_event`
- `webhook_subscription`
- `notification_event`

## 8. 规则治理方案

以下规则必须逐步平台化管理：

- 异常识别规则
- 问题指纹规则
- 回归阈值规则
- 准入门禁规则
- 附件抓取分级规则
- 数据保留规则

治理要求：

- 可配置
- 可版本化
- 可审计
- 可回溯到结论

## 9. 存储与保留策略

### 9.1 数据分层

- 原始采样数据
- 事件数据
- 聚合数据
- 报告快照
- 附件数据

### 9.2 保留建议

- 原始采样：短周期保留
- 事件数据：中长期保留
- 聚合数据：长期保留
- 报告快照：长期保留
- 大附件：按策略压缩、清理或归档

### 9.3 证据治理要求

- 统一命名规则
- 统一目录结构
- 失败抓取可降级
- 支持冷热分层
- 支持本地保留与按需上传

## 10. 非功能方案

### 10.1 并发与稳定性

- 支持多设备并发执行
- 单设备异常不得拖垮整体执行
- 任务、采样、抓取、报告生成应尽量解耦

### 10.2 平台自监控

平台自监控第一版由 `PlatformHealthService` 承接，采用 runtime JSON 快照持续沉淀，不再只依赖 doctor 的即时诊断。当前已覆盖以下指标，并在 Web 首页、`/runner`、`/api/platform-health` 和 CLI `platform-health` 暴露：

- 调度器心跳和 stale 状态
- 设备在线率
- 设备可调度率
- 任务失败率
- ADB 失败率
- 抓取失败率
- 报告生成失败率
- outbox backlog、重试和 dead-letter

后续仍需补 24h 趋势图、SLA 阈值配置、告警订阅和健康日报。

### 10.3 安全与权限

- 报告和附件访问遵循最小必要授权原则
- 敏感信息应支持脱敏
- 人工覆盖准入结论必须保留审计记录

## 11. 当前工程实施方案

### 11.1 优先沉淀

- 设备发现、状态同步和设备池治理能力
- 任务、Run、执行实例和报告主链
- ADB、SoloX、Perfetto 三类监控后端
- Issue、Artifact、Analysis、AdmissionCase、QualityGate 等核心领域对象
- CLI、Web、JSON API 和 outbox/worker 入口

### 11.2 优先强化

- 将设备治理、任务执行、异常检测、证据抓取和报告生成保持为独立服务
- 将性能采样能力做成可替换、可观测、可复用的子系统
- 将身份、权限、审计、回调签名和 outbox receipt 统一纳入平台边界
- 将真实设备 smoke、长稳轮次和外部链路验收沉淀成可复核记录

### 11.3 不建议扩展

- 把稳定性任务平台退化成单纯监控看板
- 在页面层堆叠业务规则，绕过服务层和领域对象
- 在未完成真实验收前，把本地 smoke 能力描述成生产可用外部链路

## 12. 性能采样子系统方案

性能采样是稳定性平台的基础能力，当前需要继续保持可插拔、可降级、可追溯。

结论如下：

- 不做整项目重写
- 不把采样逻辑绑定到单一入口
- 通过统一 monitoring adapter 支持 `adb_collector / solox / perfetto`
- 采样结果必须能进入 Run、报告、性能页、准入风险和 artifact 证据链

详见子方案文档：

- [`性能采样子系统方案.md`](./%E6%80%A7%E8%83%BD%E9%87%87%E6%A0%B7%E5%AD%90%E7%B3%BB%E7%BB%9F%E6%96%B9%E6%A1%88.md)

## 13. 实施建议

当前阶段最合理的实施顺序是：

1. 先在现有项目中完成 `V1` 本地执行代理化改造
2. 再逐步引入中心分析能力
3. 最后引入 Web、准入、协作和外部系统集成

核心判断：

- `V1` 先解决“能稳定执行和自动取证”
- `V2` 再解决“能分析和判断回归”
- `V3` 最后解决“能进入团队生产流程”
