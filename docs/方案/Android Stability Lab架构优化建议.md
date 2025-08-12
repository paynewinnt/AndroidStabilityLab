# Android Stability Lab 架构优化建议

## 1. 文档目标

本文档用于沉淀当前代码库的架构优化建议，并按优先级给出推进顺序、问题原因、必要性和建议 owner 范围。

本文档不是新的产品需求，也不是推倒重写方案。它的目标是：

- 收口当前已经膨胀的入口层和服务层
- 统一 CLI / Web / API 的业务口径
- 降低后续新增模板、监控、准入、集成能力时的维护成本
- 明确哪些优化是必须尽快做，哪些可以排期渐进推进

## 2. 当前整体判断

当前代码已经形成比较清晰的主分层：

- `domain/`：领域对象
- `app/`：业务服务
- `infrastructure/`：ADB、监控、持久化、外部系统适配
- `repositories/`：仓储实现
- `scenario/`：执行模板
- `cli/` 和 `web/`：用户入口层

这个方向是对的。当前主要问题不是“架构缺失”，而是：

- 入口层和服务层继续膨胀
- 兼容适配层还没有完全收口
- Web / CLI 仍有重复编排逻辑
- ADB、时间、错误、配置、runtime 数据这些横切能力还不够统一
- 测试文件和页面文件仍有继续长大的趋势

## 3. 优先级定义

- `P0`：不做会持续拖累主线，直接影响用户使用、排障或后续功能扩展
- `P1`：建议进入近期迭代，可以显著降低维护成本和风险
- `P2`：可以排期渐进优化，主要提升工程质量、扩展性和长期稳定性

## 4. P0 优化项

### 4.1 收口 ADB 命令执行层

当前状态：

已完成第一轮收口。当前已新增统一的基础设施级命令执行入口 `stability/infrastructure/command_runner.py`，并让 artifact 采集、scenario 执行、run cleanup、ADB collector 和 Perfetto 辅助命令复用同一套 `CommandResult / CommandRunner / SubprocessCommandRunner` 语义。

问题原因：

当前 `scenario/`、`artifact/`、`monitoring/`、`device_adapter` 都会直接或间接调用 ADB / subprocess。不同模块各自处理 timeout、日志、错误分类、TCP 重连和设备状态，容易导致同一个设备问题在不同入口表现不一致。

建议方案：

- 建立唯一的 `AdbClient` 或 `HostCommandRunner`
- 统一 ADB 命令执行、timeout、stdout/stderr 记录、错误分类
- 统一 TCP 设备重连、`offline`、`unauthorized`、`no route to host` 等状态识别
- 让 scenario、monitoring、artifact、device adapter 都只依赖这个统一执行层

必要性：

非做不可。ADB 是平台稳定性的底层依赖，分散调用会直接放大设备连接和排障问题。

建议 owner 文件范围：

- `stability/infrastructure/device_adapter.py`
- `stability/infrastructure/adb/`
- `stability/scenario/`
- `stability/artifact/`
- `stability/infrastructure/monitoring_*adapter.py`

### 4.2 将 `infrastructure/adb` 正式产品化

当前状态：

已完成。ADB collector 已归位到 `stability/infrastructure/adb/`，正式模块 import 已同步改为 `stability.infrastructure.adb`，监控默认 profile 和 metadata 也已使用 `adb / adb_collector` 口径。历史配置名仅作为归一化别名保留，不再作为主线命名。

问题原因：

文档已经把项目定位为新的 `Android Stability Lab`，ADB collector 必须以正式基础设施模块存在。如果基础路径和命名仍呈现兼容层语义，会让代码口径和项目定位冲突，也会让后续开发误判这部分是否还能继续扩展。

建议方案：

- 将 `stability/infrastructure/adb/` 作为正式 ADB collector 位置
- 把 `ADBCollector` 定义为正式 ADB adapter
- 同步更新 imports、测试、文档和监控 backend metadata
- 对历史配置名只保留归一化别名，不再在主线代码里扩散

必要性：

非做不可。它是架构命名和依赖边界的问题，不处理会持续污染新功能判断。

建议 owner 文件范围：

- `stability/infrastructure/adb/`
- `stability/infrastructure/device_adapter.py`
- `stability/infrastructure/monitoring_adb_adapter.py`
- `stability/infrastructure/monitoring_factory.py`
- `stability/scenario/cold_start_loop.py`
- `stability/scenario/monkey.py`
- `stability/scenario/custom_automation.py`
- `stability/scenario/device_cycle.py`
- `stability/scenario/tcp_recovery.py`

### 4.3 建立 Scenario Registry，统一模板能力

当前状态：

已完成第一轮落地。当前已新增 `stability/scenario/registry.py`，统一声明模板 ID、中文名、使用说明、参数 schema、支持指标、默认指标、风险等级、是否需要设备、是否需要 APK、是否会改变设备状态。Web 创建任务表单、参数说明、指标卡片、模板下拉框、CLI `create-task --template-type` choices/help 和 `TaskService.describe_task()` 已开始从 registry 读取。

问题原因：

当前模板已经覆盖 `cold_start_loop / monkey / foreground_background_loop / install_uninstall_loop / reboot_loop / standby_wake_loop / custom` 等能力。Web 已经开始按模板动态展示参数，但模板说明、参数 schema、指标能力、危险操作说明仍容易分散在 Web、CLI、scenario 和文档中。

建议方案：

- 建立 `ScenarioRegistry`
- 每个模板统一声明：
  - 模板 ID
  - 中文名
  - 使用场景
  - 参数 schema
  - 默认值
  - 支持指标
  - 是否需要 APK
  - 是否需要设备
  - 是否会重启、安装、卸载或执行自定义 ADB
  - 风险等级
- Web 表单、CLI help、任务校验、文档说明都从同一份 registry 生成或读取

必要性：

非做不可。模板会继续增加，如果没有统一 registry，每新增一个模板都会产生多处改动和口径漂移。

建议 owner 文件范围：

- `stability/scenario/`
- `stability/bootstrap.py`
- `stability/web/pages_task_forms.py`
- `stability/cli/parser_tasks.py`
- `stability/app/task_service.py`
- `docs/Android Stability Lab平台使用说明.md`

### 4.4 建立统一错误模型和错误码

当前状态：

已完成第一轮落地。当前已新增 `stability/domain/errors.py`，统一提供 `AppError / AppErrorCode / normalize_app_error`，并把 Web JSON 响应稳定为 `error_code / message / hint / details / request_id / app_error` 结构。CLI 主入口已能把 `AppError` 和常见 `ValueError / PermissionError / LookupError` 归一化为同一错误 contract。`ScenarioRegistry` 的模板参数和指标校验已经接入 `TaskService`，因此 Web/API/CLI 创建任务都会先经过同一套模板参数校验。

问题原因：

当前 Web、CLI、service 层很多错误以异常字符串或局部 message 返回。用户看到错误后，往往不知道是参数错误、设备错误、权限错误、环境错误、执行失败还是外部系统失败。

建议方案：

- 定义统一 `AppError`
- 字段建议：
  - `code`
  - `message`
  - `hint`
  - `details`
  - `request_id`
  - `audit_event_id`
- Web/API/CLI 都使用同一套错误码
- 常见错误应覆盖：
  - 设备不可达
  - ADB 未授权
  - 任务参数非法
  - session 无效
  - permission denied
  - monitoring backend 不可用
  - outbox delivery 失败

必要性：

非做不可。平台面向使用方后，失败排查能力就是核心产品体验。

建议 owner 文件范围：

- `stability/domain/`
- `stability/app/`
- `stability/web/responses.py`
- `stability/cli/handlers/`
- `tests/`

后续补强：

- 继续把设备不可达、ADB 未授权、monitoring backend 不可用、outbox delivery 失败等错误从字符串迁移到明确 `AppErrorCode`
- 在 OpenAPI / API manifest 中补充错误响应 schema
- Web 页面错误态继续从“页面渲染失败”升级为面向用户的处理建议和排障入口

### 4.5 统一时间与序列化出口

当前状态：

已完成第一轮落地。当前 `stability/time_utils.py` 已成为统一时间出口，新增 `utcnow() / now_beijing_string() / serialize_datetime() / serialize_datetime_or_original()`。领域层 `stability/domain/value_objects.py`、执行状态机、执行 hook、任务服务、Run 执行服务、监控工具、Web payload 生成时间、规则治理时间、golden draft/promotion 时间已开始统一走该出口。SQLAlchemy 默认时间也已从 `datetime.utcnow` 切到统一 `utcnow()`，消除了主代码路径里的 `datetime.utcnow()` deprecation warning。

问题原因：

代码中仍存在 `datetime.now()`、`datetime.utcnow()`、`utcnow()`、`isoformat()` 等混用。时间字段已经进入 Web、报告、准入、outbox、审计和验收记录，如果格式不统一，会影响展示、排序、对账和排障。

建议方案：

- 所有业务时间通过 `stability/time_utils.py` 或 `stability/domain/value_objects.py` 生成
- 所有对外展示统一为北京时间 `+08:00`
- 用户可见格式统一为类似 `2026-04-25 03:45:53.900919`
- 内部如需保留 timezone-aware datetime，应在序列化出口统一格式化

必要性：

非做不可。时间是审计、报告和 outbox 投递的基础字段，不能多套格式长期并存。

建议 owner 文件范围：

- `stability/time_utils.py`
- `stability/domain/value_objects.py`
- `stability/app/`
- `stability/web/`
- `stability/cli/`
- `tests/`

后续补强：

- 继续把服务层零散 `isoformat()` 迁移到 `serialize_datetime()` 或明确的持久化序列化函数
- 明确区分“内部持久化时间”和“用户可见时间”，避免审计字段在不同场景下二次转换
- 在 Web/API/CLI contract 文档中固定所有用户可见时间格式

### 4.6 建立 runtime 数据生命周期管理

当前状态：

已完成第一轮 CLI 与服务层落地。当前新增 `RuntimeLifecycleService`，统一识别 `tasks / analysis / admission / collaboration / integration / runner / apks` 等 runtime 分类，并提供：

- `runtime-doctor`：检查 runtime 根目录、分类覆盖、文件数量、目录数量、总大小和基础异常
- `export-runtime`：按分类导出 zip，内含 `manifest.json`，适合把本地运行结果打包给别人看
- `cleanup-runtime`：默认 dry-run，只列出超过保留天数的候选；必须显式传 `--apply` 才会删除

第一轮刻意没有实现自动 restore，也没有默认删除 `latest / webhooks.json / sessions.json / actors.json` 等敏感或关键运行状态文件。

问题原因：

当前 `runtime/` 下已经承载 admission、outbox、collaboration、runner、分析报告、运行产物等状态。项目又明确是本地部署、本地数据自看自用为主，因此 runtime 数据管理本身就是生产运维能力。

建议方案：

- 增加 runtime 管理能力：
  - `doctor`
  - `cleanup`
  - `export`
  - `backup`
  - `restore`
- 明确哪些数据可清理、哪些必须保留、哪些适合导出共享
- Web 增加 runtime 数据概览与导出入口

必要性：

非做不可。否则用户长期运行后会不知道数据在哪里、哪些能删、如何把结果给别人看。

建议 owner 文件范围：

- `runtime/`
- `stability/cli/handlers/`
- `stability/web/`
- `stability/app/`
- `docs/Android Stability Lab平台使用说明.md`

### 4.7 增加 `doctor` 总诊断入口

问题原因：

当前平台依赖 Python、ADB、设备授权、Web 端口、runtime 权限、监控 backend、飞书 webhook 等多类环境条件。用户遇到问题时，很难判断是设备、配置、端口、依赖还是平台本身失败。

建议方案：

- 提供 `python -m stability.cli doctor`
- Web 增加诊断页
- 诊断项至少覆盖：
  - Python 依赖
  - ADB 是否可用
  - ADB devices 状态
  - TCP 设备可达性
  - runtime 读写权限
  - config JSON 是否有效
  - Web 端口占用
  - SoloX 是否可用
  - Perfetto 是否可用
  - outbox webhook 配置
  - 飞书 webhook 连通性

必要性：

非做不可。项目的使用门槛主要在环境和设备链路，不在代码本身。

建议 owner 文件范围：

- `stability/cli/`
- `stability/web/`
- `stability/infrastructure/device_adapter.py`
- `stability/infrastructure/monitoring_*`
- `stability/app/integration_outbox*`

当前状态：

已完成第一轮 CLI、Web 与服务层落地。当前新增 `DoctorService`，统一输出 `DoctorReport / DoctorCheck`，把环境、设备链路、runtime、监控 backend 和 outbox webhook 的诊断结果收口到同一份结构化报告，并提供：

- `doctor`：总诊断入口，默认检查 Python 版本与核心依赖、ADB 是否可用、ADB devices 状态、TCP 设备可达性、runtime 读写权限、config JSON、Web 端口、SoloX/Perfetto 可用性、outbox webhook 配置、飞书 webhook 配置
- `doctor --device-id <serial> --package-name <package>`：单设备深度诊断，覆盖目标设备授权、`adb shell`、可选包名安装状态、设备端 `perfetto` 命令、`/data/local/tmp` 写入权限、无线 ADB TCP 可达性
- `/doctor`：Web 诊断页，面向用户展示总诊断和单设备深度诊断入口
- `/api/doctor`：诊断 JSON API，供脚本、外部页面或自动化检查读取

第一轮刻意没有默认发送真实飞书消息。飞书连通性默认只检查配置完整性；CLI 必须显式传 `--check-webhooks`，Web 必须显式访问 `/doctor?check_webhooks=1` 才会发送诊断 ping，避免打开页面就产生 IM 噪声。

第一轮也没有把 `doctor` 变成采样验证器。当前 `doctor --device-id` 验证的是设备与环境条件是否满足；后续如果要验证 SoloX/Perfetto 的真实采样质量，应继续补 `doctor --device-id <serial> --backend perfetto/solox` 这类 backend 级真实采样探针。

已同步处理两个用户侧体验问题：USB serial 设备会按普通 ADB 设备完成深度诊断，无线检查会明确显示“USB serial，ADB 已可用，无需 TCP 探测”；Web 诊断详情已改为单卡片内独立展开，详情内容在卡片内滚动，避免展开一个诊断项后撑高整行卡片。

## 5. P1 优化项

### 5.1 抽 application facade / use_cases 层

当前状态：

已完成三条纵切面落地。新增 `stability/application/` 作为 CLI / Web 共享 use-case 层，当前已覆盖：

- 创建任务
- 创建 Run
- 执行 Run
- 设备池查询
- 设备标记更新
- ADB 设备刷新
- TCP 设备连接
- 无线调试配对并连接
- integration outbox 单轮投递
- integration outbox worker / daemon 调度
- dead-letter preview / replay
- CI admission decision 查询与回传
- IM / Feishu 通知 worker
- defect sync worker
- release sync worker
- IM / Feishu 2h/24h 验收摘要 payload

CLI handler 和 Web action 现在只负责解析输入、处理入口特有逻辑和渲染输出；任务主链的参数校验、服务调用和统一返回 payload 已收口到 `stability/application/task_lifecycle.py`。设备池聚合、设备标记和设备连接动作已收口到 `stability/application/device_management.py`。integration outbox 的 `deliver / worker / replay dead-letter / CI sync` 编排已收口到 `stability/application/integration_outbox.py`，并兼容当前服务 API 与旧 registry replay fallback。IM / Feishu / defect / release 专用 worker 已收口到 `stability/application/integration_worker_channels.py`；IM / Feishu 验收摘要已收口到 `stability/application/integration_reporting.py`。

剩余未迁移：

- integration outbox 页面只读 payload 聚合
- webhook 注册类 action
- release submission 创建与 admission 同步 action

问题原因：

CLI handler、Web payload/action 和服务层之间仍存在重复装配逻辑。入口层不仅负责解析和渲染，也在拼 bundle、组装参数、处理业务流程。长期看会导致 CLI 和 Web 两套行为漂移。

建议方案：

- 新增 `stability/application/` 或 `stability/app/use_cases/`
- 每个用户动作对应一个明确 use case
- CLI/Web 只负责：
  - 输入解析
  - 调用 use case
  - 渲染输出
- use case 负责：
  - 参数校验
  - 调用领域服务
  - 返回统一结果对象

必要性：

高。不是马上阻塞运行，但继续加 Web/CLI 功能时会持续放大重复逻辑。

建议 owner 文件范围：

- `stability/cli/handlers/`
- `stability/web/application_actions_*`
- `stability/web/application_payload_*`
- `stability/app/`

### 5.2 按 feature package 重组 Web

问题原因：

当前 Web 已经从超大文件拆成多个 mixin，但 `WebPortalApplication` 仍是隐形大类。文件变小了，不代表依赖方向已经清晰。继续加页面后，mixin 横向依赖会越来越难维护。

建议方案：

按页面域拆成 feature package：

- `stability/web/features/tasks/`
- `stability/web/features/devices/`
- `stability/web/features/admission/`
- `stability/web/features/integration/`
- `stability/web/features/runner/`
- `stability/web/features/performance/`

每个包内固定结构：

- `payload.py`
- `page.py`
- `actions.py`
- `routes.py`

当前落地状态：

- 已新增 `stability/web/features/`，并按 `tasks / devices / admission / integration / runner / performance` 建立固定 `payload.py / page.py / actions.py / routes.py` 文件结构
- `WebPortalApplication` 的关键 mixin 导入已切到 feature 包入口
- `tasks / devices / admission / integration / runner / performance` 的 GET / POST 分发已优先经过 feature route dispatcher
- 现阶段仍保留原有兼容 mixin 文件，避免一次性重写整个 router；后续新增页面和动作应优先进入对应 feature 包

必要性：

高。当前 Web 仍是主要用户入口，不继续收敛会影响后续迭代速度。

建议 owner 文件范围：

- `stability/web/application.py`
- `stability/web/routes.py`
- `stability/web/pages_*`
- `stability/web/application_payload_*`
- `stability/web/application_actions_*`

### 5.3 拆服务层大文件，优先 device 和 admission

当前状态：

已完成第一轮服务层大文件拆分，优先收口 `DeviceService` 和 `AdmissionCaseService`：

- `stability/app/device_service.py` 已从约 800 行降到 536 行，继续保留设备同步、连接、标记、调度、隔离恢复等 public service API
- 新增 `stability/app/device_service_mapping.py`，承接 descriptor 到 `Device` 的映射、连接状态/可用状态推导、missing offline 标记
- 新增 `stability/app/device_service_pool.py`，承接设备画像、设备池聚合、调度候选评估
- `stability/app/admission_case_service.py` 已从约 795 行降到 406 行，继续保留 AdmissionCase 聚合编排、持久化和 outbox contract 发布
- 新增 `stability/app/admission_case_contracts.py`，承接 `error_code / case_trace / source_refs / ci_contract`
- 新增 `stability/app/admission_case_lifecycle.py`，承接状态归一化、状态流转校验、生命周期事件和角色审计记录
- 新增 `stability/app/admission_case_aggregation.py`，承接 execution/top issue/regression/scenario coverage/filter 聚合

当前保留策略：

- public API 不变，外部仍通过 `DeviceService` 和 `AdmissionCaseService` 使用
- 拆分边界先按 helper module 收口，不额外引入复杂继承或 use-case 对象
- `snapshot_service.py`、`rule_governance_service.py`、`performance_trend_service.py` 当前均低于 800 行，暂不在本轮继续拆

问题原因：

部分服务文件接近或超过 800 行。文件行数本身不是问题，问题是 query、command、store、serialization、workflow 混在一起，导致 Web/CLI 高频入口改动容易牵连大范围测试。

建议方案：

优先拆：

- `device_service.py`
- `admission_case_service.py`
- `snapshot_service.py`
- `rule_governance_service.py`
- `performance_trend_service.py`

拆分边界：

- query / read model
- command / write action
- serialization
- persistence/store
- workflow/state transition

必要性：

高。服务层是主系统核心，继续膨胀会让后续业务闭环难以维护。

建议 owner 文件范围：

- `stability/app/device_service.py`
- `stability/app/admission_case_service.py`
- `stability/app/snapshot_service.py`
- `stability/app/rule_governance_service.py`
- `stability/app/performance_trend_service.py`

### 5.4 统一 AdmissionCase 对外 contract

问题原因：

AdmissionCase、QualityGate、RuleReviewReport、GoldenSuite、Regression 都已存在，但外部入口仍可能按不同对象展示或查询准入结果。长期看会让“准入结论到底以谁为准”变得不清晰。

建议方案：

- 对外只暴露 `AdmissionCase` 作为准入主对象
- `QualityGate / RuleReviewReport / GoldenSuite / Regression / PerformanceRisk` 都作为 evidence block
- CLI/Web/API 使用同一 JSON contract
- 外部系统回写、IM 通知、CI 门禁都基于 AdmissionCase

落地状态：

- 已落地第一轮：服务层持久化、CI outbox、Web/API 和 CLI `list-admission-cases` / `show-admission-case` 均以 `AdmissionCase` 为准入主对象。
- 服务层已新增 `export_admission_case_payload` / `list_admission_case_payloads`，统一输出 `admission_case.v1` / `admission_case_list.v1` JSON-ready contract。
- CLI case 输出已直接调用服务层 AdmissionCase payload API；fallback 才使用同一个 app 层 serializer，不再维护 CLI 私有字段拼装。
- Web/API 已优先调用服务层 AdmissionCase payload API；`QualityGate / RuleReviewReport / GoldenSuite / Regression` 在 API 中收进 `evidence` / `legacy_detail`，不再作为并列的最终准入对象。
- `show-admission-report` 继续保留为导出视角，但语义上是基于 `AdmissionCase` contract 生成的 formal report，不作为新的准入主对象。
- 仍需继续收口：`/admission` HTML 列表页为了兼容旧卡片展示仍会展开部分 summary 字段；后续可继续把页面展示也完全改成围绕 `evidence_blocks` 渲染。

必要性：

高。准入是 V3 主线能力，contract 不稳定会直接影响集成和用户理解。

建议 owner 文件范围：

- `stability/domain/admission_case_models.py`
- `stability/app/admission_case_service.py`
- `stability/app/quality_gate_service.py`
- `stability/app/rule_review_report_service.py`
- `stability/web/pages_admission_detail.py`
- `stability/cli/handlers/admission.py`

### 5.5 集中配置读取到 Config Provider

状态：

已完成第一轮落地。当前新增 `stability/app/config_provider.py`，集中产出 `monitoring / outbox / web / device / thresholds / runtime paths` 六类配置，并明确读取优先级为：

1. 显式 overrides / CLI 参数
2. 环境变量
3. `config/platform.json`、`config/monitoring.json`、`config/performance.json`、`config/performance_risk_thresholds.json`
4. 代码默认值

已接入的关键入口：

- `bootstrap`：统一下发 monitoring backend、performance risk thresholds、outbox 配置、runtime 根目录和各服务 root_dir。
- `serve-web`：host、port、portal mode、public base url、deployment label、启动时设备同步优先读取 `ConfigProvider`，CLI 参数仍可覆盖。
- `doctor / runtime-doctor / export-runtime / cleanup-runtime`：runtime root、config dir、web probe、outbox root 使用同一 provider 默认值。
- Web 任务动作：APK 管理目录和按 backend 临时构造 monitoring adapter 已改为读取 `ConfigProvider`。

第一轮没有强行替换数据库连接配置读取，也没有把所有历史 service 构造默认值删除；这些默认值继续作为兼容兜底存在。后续如果要支持多环境配置文件，应在 `config/platform.json` 中继续扩展，而不是让各入口重新引入独立默认值。

问题原因：

当前配置来源包括 `config/*.json`、环境变量、CLI 参数、默认值和 Web 表单。配置读取分散后，很容易出现一个入口生效、另一个入口不生效。

建议方案：

- 新增统一 `ConfigProvider`
- 覆盖：
  - monitoring
  - outbox
  - web
  - device
  - thresholds
  - runtime paths
- 明确配置优先级：
  - CLI 参数
  - 环境变量
  - config 文件
  - 默认值

必要性：

高。配置漂移会直接导致用户无法复现问题。

建议 owner 文件范围：

- `config/`
- `stability/infrastructure/monitoring_config.py`
- `stability/cli/`
- `stability/web/`
- `stability/bootstrap.py`

### 5.6 Web 表单 schema 与 CLI 参数同源

状态：

已完成第一轮落地。当前 `ScenarioRegistry` 新增 `get_template_form_schema()` / `list_template_form_schemas()`，对外输出 `scenario_template_schema.v1`，把模板参数、默认指标、支持指标、风险信息统一成 Web 和 CLI 都能读取的结构。

已接入的关键入口：

- Web 创建任务/长稳任务：默认勾选指标改为读取当前模板 `default_metrics`，指标卡片按模板 schema 标记默认适用范围，切换模板时会按 schema 重新勾选默认指标。
- Web 参数表单：继续从 `ScenarioParamField / ScenarioParamSection` 生成，并开始消费字段默认值。
- Web 模板风险提示：创建任务表单展示 `risk_level / requires_apk / changes_device_state / risk_note`。
- CLI：新增 `show-task-template-schema --template-type <template>`，用于直接查看 Web/CLI 共用的模板 contract。
- CLI `create-task --metric` help 已从 `METRIC_REGISTRY` 生成，避免指标说明继续硬编码。

第一轮刻意没有做动态 argparse 参数生成。原因是 `argparse` 需要先知道 `--template-type` 才能生成模板专属参数，做成两阶段解析会扩大改动面。当前 CLI 仍保留 `--task-params JSON`，并通过 schema 查询命令和服务层校验保证同源。

问题原因：

Web 已经在减少 JSON 手填，但 CLI 参数、Web 表单、模板参数说明仍可能漂移。特别是模板参数、指标、设备选择这类高频字段，应该从统一 schema 生成。

建议方案：

- 以模板 schema 为源头
- 自动生成或复用：
  - Web 表单控件
  - CLI help
  - 默认值
  - 参数校验
  - 文档说明

必要性：

中高。不是当前运行阻塞项，但能显著降低后续模板扩展成本。

建议 owner 文件范围：

- `stability/scenario/`
- `stability/web/pages_task_forms.py`
- `stability/cli/parser_tasks.py`
- `docs/Android Stability Lab平台使用说明.md`

### 5.7 危险操作权限和确认机制

问题原因：

部分模板会重启设备、安装/卸载应用、执行自定义 ADB 脚本。这些动作会改变设备状态，不应和普通冷启动、monkey 任务使用同样的执行确认。

建议方案：

- 模板 registry 增加 `risk_level`
- Web 执行前展示风险确认
- CLI 对高风险模板要求显式参数，例如 `--confirm-risk reboot`
- 审计事件记录风险确认来源

必要性：

中高。对个人本地使用不是强阻塞，但对多人共享设备或值班场景很重要。

建议 owner 文件范围：

- `stability/scenario/`
- `stability/web/pages_task_forms.py`
- `stability/cli/parser_tasks.py`
- `stability/app/task_service.py`
- `stability/app/run_execution_service.py`

## 6. P2 优化项

### 6.1 测试按 feature 拆分

问题原因：

`tests/test_web_portal.py`、`tests/test_run_execution_service.py`、`tests/test_integration_outbox_service.py` 等文件仍然较大。测试过大后，失败定位慢，改动影响范围也不清楚。

建议方案：

按 feature 拆分：

- `tests/web/test_tasks.py`
- `tests/web/test_devices.py`
- `tests/web/test_admission.py`
- `tests/web/test_integration.py`
- `tests/app/test_run_execution_retry.py`
- `tests/app/test_run_execution_monitoring.py`

必要性：

中。不会直接阻塞功能，但会影响后续迭代效率。

建议 owner 文件范围：

- `tests/test_web_portal.py`
- `tests/test_run_execution_service.py`
- `tests/test_integration_outbox_service.py`
- `tests/helpers/`

### 6.2 outbox 真实链路验收自动化

问题原因：

飞书 IM 和 webhook 联调已有 runbook 和验收记录，但长期看不能只靠人工观察日志。真实链路需要可重复验收。

建议方案：

- 增加 `verify-im-webhook` 或 `integration acceptance run`
- 自动输出：
  - 验签通过率
  - receipt 数量
  - dead-letter 数量
  - 重试次数
  - 噪声反馈
  - webhook 响应分布

必要性：

中。外部链路稳定后再推进，但建议尽早固化。

建议 owner 文件范围：

- `stability/app/integration_outbox*`
- `stability/cli/handlers/integration_*`
- `stability/web/application_payload_*integration*`
- `docs/运维/`

### 6.3 数据库兼容层最终收口

问题原因：

根目录 `database/` 与 `stability/infrastructure/persistence/` 仍存在耦合。长期看，新项目主线应统一到 `stability/` 内部，根目录兼容层越薄越好。

建议方案：

- 明确 `database/` 是否只是兼容层
- 新业务统一走 `stability/infrastructure/persistence/`
- 如果保留兼容层，文档中明确它不是新业务扩展点
- 如果不再需要，分阶段迁移并移除

必要性：

中。当前不是最大风险，但会影响架构清晰度。

建议 owner 文件范围：

- `database/`
- `stability/infrastructure/persistence/`
- `stability/repositories/`
- `docs/项目文件说明.md`

### 6.4 Web 正式平台化前的边界评估

问题原因：

当前 Web 定位是本地运维控制台。它已经具备最小写能力、身份解析和审计，但还不是正式团队在线平台。若未来要外放，必须补齐认证、授权、限流、审计查询和接口安全。

建议方案：

- 保持当前 Web 本地优先定位
- 如需团队外放，先做平台化评估：
  - 用户目录
  - 组织边界
  - 权限继承
  - 审计查询
  - CSRF / CORS / rate limit
  - 正式 API contract

必要性：

中。只有在团队外放场景出现时才必须推进。

建议 owner 文件范围：

- `stability/web/`
- `stability/app/collaboration*`
- `stability/domain/collaboration_models.py`
- `docs/方案/Android Stability Lab开发方案.md`

## 7. 建议执行顺序

### 第一阶段：先稳住底座

1. 收口 ADB 命令执行层
2. 将 `infrastructure/adb` 正式产品化
3. 建立统一时间与序列化出口
4. 建立统一错误模型和错误码
5. 增加 `doctor` 总诊断入口

阶段目标：

- 用户遇到设备、环境、执行失败时能快速定位
- 代码里不再出现多个 ADB 执行口径
- 时间、错误、诊断具备统一出口

### 第二阶段：收口入口和模板

1. 建立 `ScenarioRegistry`
2. Web 表单 schema 与 CLI 参数同源
3. 增加危险操作权限和确认机制
4. 抽 application facade / use_cases 层

阶段目标：

- 新增模板不再需要多处手工同步
- CLI/Web 行为一致
- 用户不再大量手填 JSON
- 高风险操作有明确确认和审计

### 第三阶段：压服务层和 Web 复杂度

1. 按 feature package 重组 Web
2. 拆 `device_service.py`
3. 拆 `admission_case_service.py`
4. 统一 AdmissionCase 对外 contract
5. 拆其他服务层大文件

阶段目标：

- Web 不再依赖横向 mixin 大聚合
- 准入对象对外口径稳定
- 高频服务更容易测试和扩展

### 第四阶段：完善运维和长期治理

1. 建立 runtime 数据生命周期管理
2. outbox 真实链路验收自动化
3. 测试按 feature 拆分
4. 数据库兼容层最终收口
5. Web 正式平台化前的边界评估

阶段目标：

- 本地运行数据可清理、可导出、可备份
- 外部链路可重复验收
- 测试失败更容易定位
- 平台化前的安全边界清晰

## 8. 当前最值得优先落地的五件事

1. `infrastructure/adb` 正式产品化并收口成统一 ADB adapter
2. 建立 `ScenarioRegistry`，统一模板说明、参数 schema、指标能力和风险等级
3. 建立统一 `AppError` 错误模型，让 Web / CLI / API 错误口径一致
4. 建立 `doctor` 诊断命令和 Web 诊断页
5. 把 runtime 数据管理做成可导出、可清理、可备份的正式能力

## 9. 非目标

以下事项暂不建议作为近期主线：

- 推倒当前 stdlib Web，直接改成大型前后端平台
- 为了“平台感”提前引入复杂任务队列
- 在 AdmissionCase contract 未进一步稳定前，同时铺开多条外部系统双向集成
- 只为了文件行数拆文件，而不处理依赖方向和职责边界

## 10. 验收口径

后续每个优化项完成时，至少应满足：

- 相关文件职责边界更清晰
- CLI/Web 行为没有漂移
- 有对应单元测试或 smoke 验证
- 文档同步说明用户该怎么用
- 如涉及用户可见行为，Web 和 CLI 的错误提示都可理解
