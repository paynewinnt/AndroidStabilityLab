# Android Stability Lab 最终功能验收矩阵

## 1. 文档目标

本文档用于回答两个问题：

- `Android Stability Lab` 最终应该具备哪些能力。
- 当前代码已经完成到什么程度，下一步应该优先补什么。

本文档不再把项目描述为早期“性能采集工具”，而是按当前主线重新定义为：

**本地优先的 Android 稳定性自动化测试、问题分析、证据抓取、报告输出与版本准入平台。**

## 2. 核心闭环

最终产品闭环是：

**设备管理 -> 任务编排 -> 执行采样 -> 异常识别 -> 证据抓取 -> 问题聚合 -> 回归分析 -> 报告输出 -> 质量门禁/准入 -> 集成通知**

当前代码已经覆盖这条闭环的大部分主路径。后续重点不是重新定义方向，而是把“已有能力”升级为“可验收、可运营、可持续运行”的平台能力。

## 3. 验收状态定义

| 状态 | 含义 |
| --- | --- |
| 已完成 | 已有领域服务、入口、测试或 smoke，能支撑当前本地部署主线使用 |
| 部分完成 | 主体能力存在，但缺少治理、自动化验收、生产边界或体验闭环 |
| 未完成 | 当前代码未形成明确实现，或只停留在文档/规划层 |

## 4. P0 必须能力验收矩阵

| 功能 | 已完成 | 部分完成 | 未完成 | 验收方式 | 对应入口 | 对应测试 |
| --- | --- | --- | --- | --- | --- | --- |
| 设备池管理 | 设备发现、刷新、TCP 连接、设备池分组、Group/Team/Tag 标记、在线/不可调度状态展示已具备；核心实现在 `stability/app/device_service.py`、`stability/infrastructure/device_adapter.py` | 设备占用、隔离、故障记录已有服务能力，但电量/温度/ROM 信息还没有稳定进入设备发现链路；CLI 查询能力强，设备标记、connect、pair-connect 等写入口主要在 Web/API | 多机规模化调度容量目标、完整调度锁、占用释放和异常设备自动恢复 SLA 未定义 | Web 上刷新 ADB 设备、连接 TCP 设备、编辑设备标记；CLI 查询设备和设备池；断连/重连后状态应更新；执行失败后故障记录应能影响可调度状态 | Web：`/device-pools`、`/api/device-pools`、`/api/device-pools/actions/update-profile|refresh|connect|pair-connect`；CLI：`list-devices`、`show-device`、`list-device-pools`、`inspect-device-pool`；服务：`DeviceService` | `tests/test_device_service.py`、`tests/test_web_portal_device_pools.py`、`tests/test_cli_device_task_run_commands.py`、`tests/test_doctor_service.py` |
| 稳定性任务编排 | 创建任务、创建 Run、执行 Run、设备选择、目标应用、采样间隔、指标选择、重试、并发、monitoring backend 选择已具备；Web 已支持表单化创建 | 定时/循环任务主要通过 unattended/runner 实现，更像本地轮询器，还不是完整平台调度队列；高风险模板确认需要继续加强 | 暂无统一的任务容量、调度队列和 SLA 验收目标 | 创建任务 -> 创建 Run -> 执行 Run，验证实例、报告、采样、状态落盘；失败重试只对可恢复错误生效 | Web：`/tasks`、`/long-run-templates`、`/tasks/task/<task_id>`、`/runs/<run_id>`、`/api/tasks/actions/create`、`/api/runs/actions/create|execute`；CLI：`create-task`、`create-run`、`execute-run`、`show-task-template-schema`；服务：`TaskService`、`ExecutionService`、`RunExecutionService` | `tests/test_task_service.py`、`tests/test_run_execution_service.py`、`tests/test_run_history_service.py`、`tests/test_scenario_registry.py`、`tests/test_cli_execution_commands.py`、`tests/test_cli_device_task_run_commands.py`、`tests/test_web_portal.py` |
| 模板任务 | `cold_start_loop`、`monkey`、`foreground_background_loop`、`install_uninstall_loop`、`reboot_loop`、`standby_wake_loop`、`custom` 已进入 `ScenarioRegistry`，包含中文名、参数、指标、风险等级 | Web/CLI 已开始读取 registry，但还需要继续减少手写分支，确保表单、CLI help、文档完全同源 | 模板级自动验收矩阵还不完整 | 每个模板至少能创建任务、创建 Run、执行最小 smoke；高风险模板必须提示风险 | Web：`/tasks`；CLI：任务命令；服务：`stability/scenario/registry.py`、`stability/scenario/*` | `tests/test_scenario_registry.py`、`tests/test_cold_start_loop_runner.py`、`tests/test_monkey_runner.py`、`tests/test_device_cycle_runner.py`、`tests/test_custom_automation_runner.py` |
| 异常自动识别 | ANR、Java exception/crash-like、native crash、reboot、process exit、freeze/black screen、system_server、watchdog 等已有规则识别；执行链路可把识别结果沉淀为 issue | 当前主要基于场景输出、metadata 和文本匹配，不是持续 logcat/dropbox/tombstone 流式检测；OOM、内存上涨、卡顿恶化更多在趋势风险层，不是执行期 issue 自动识别 | 暂无独立“对某日志/证据执行异常识别”的 Web/API/CLI 入口，也缺真实异常样本库 golden 验收 | 构造异常样本或执行失败实例，验证 issue 类型、严重级别、fingerprint、Top Issue 聚合结果 | Web：`/issues`、`/api/issues`、Run 详情；CLI：`list-top-issues`、`show-issue-group`；服务：`AnalysisService`、`issue/detectors.py` | `tests/test_issue_detector.py`、`tests/test_analysis_service.py`、`tests/test_attribution_service.py`、`tests/test_run_execution_service.py`、`tests/test_rule_config.py` |
| 日志与证据自动抓取 | `logcat`、`bugreport`、`traces`、`tombstone`、`dropbox`、`meminfo`、`SurfaceFlinger`、截图、input events、Perfetto trace 附件已有 artifact collector 支撑；标准运行目录已形成 | 抓取均为 best-effort，受权限和设备在线状态影响；bugreport 当前偏文本 shell 方式；缺少独立补采/重采入口 | 证据级 retention policy、压缩、冷热分层、必抓/选抓策略尚未成为独立领域能力 | 执行失败或异常实例后，验证 report、log、artifact 路径存在且可在 Web/JSON 中跳转；断网/无权限时应记录抓取失败原因 | Web：Run 详情、`/artifacts/run/<run_id>`、`/api/artifacts/run/<run_id>`、`/performance`；CLI：通过 `execute-run` 触发；服务：`ArtifactCollector`、`ArtifactPathPlanner` | `tests/test_artifact_collector.py`、`tests/test_artifact_evidence_parsers.py`、`tests/test_run_execution_service.py`、`tests/test_web_portal_read_only.py` |
| 任务报告 | 单次任务/实例报告、HTML/Markdown/JSON 路径、Run 详情、执行摘要、异常明细和证据路径已具备 | 版本测试报告、设备维度对比报告模板分散在多个服务；报告生成耗时、失败率、报告大小等非功能验收未定义 | 面向评审的一键导出报告包和独立 PDF/HTML 准入报告入口还可增强 | 执行 Run 后，验证 instance summary、report_path、html_report_path、monitoring snapshot、issue 和 artifact 字段 | Web：Run 详情、`/tasks`；CLI：run 查询命令；服务：`ReportService`、`RunHistoryService`、`RuleReviewReportService`、`AdmissionReportBuilder` | `tests/test_run_history_service.py`、`tests/test_run_execution_service.py`、`tests/test_rule_review_report_service.py`、`tests/test_web_portal.py` |

## 5. P1 强相关能力验收矩阵

| 功能 | 已完成 | 部分完成 | 未完成 | 验收方式 | 对应入口 | 对应测试 |
| --- | --- | --- | --- | --- | --- | --- |
| 问题聚合 | Top Issue、fingerprint、按 task/run/device/package/template/version 过滤已具备；核心在 `AnalysisService` | 看板/UI、人工合并、拆分、误聚合修正、跨版本 issue lineage 治理仍未产品化 | `IssueFingerprintGovernanceService` 尚未建立 | 同类 crash/ANR 应聚合到同一 fingerprint；不同场景/包名应可区分；支持 drill-down samples | Web：`/issues`、`/api/issues`；CLI：`list-top-issues`、`show-issue-group`；服务：`AnalysisService` | `tests/test_analysis_service.py`、`tests/test_cli_analysis_commands.py`、`tests/test_web_portal_read_only.py` |
| Top Issue 看板 | Web 问题中心、首页摘要、API 查询已具备 | 噪声过滤、人工压制、优先级治理还需要加强 | Top Issue 运营动作闭环未完整产品化 | 首页和问题中心能展示 Top Issue；过滤条件应影响排序和结果 | Web：`/issues`、首页；API：`/api/issues`；CLI：analysis 查询 | `tests/test_web_portal.py`、`tests/test_web_portal_read_only.py`、`tests/test_analysis_service.py` |
| 回归分析 | comparison、regression、performance trend、snapshot 已具备；支持版本/设备/场景维度对比 | CLI 分析能力强于 Web；Web 主要提供看板/详情，缺少 compare/regression 的一等交互式操作入口；回归阈值、显著性口径、人工确认、按设备组差异化判断仍需加强 | 持续趋势图和回归运营看板仍可增强 | 构造左右版本/设备/场景数据，验证 regression result、risk level 和差异明细 | Web：问题中心、准入中心、性能页、Golden Diff；CLI：`compare-issues`、`compare-performance-trends`、`judge-regression`、analysis snapshot、rule replay/golden/rule review 系列 | `tests/test_comparison_service.py`、`tests/test_regression_service.py`、`tests/test_performance_trend_service.py`、`tests/test_cli_analysis_commands.py`、`tests/test_rule_*` |
| 场景编排增强 | 多模板已接入，参数表单和动态指标已具备；自定义自动化支持 adb/uiautomator2/external script | 模板参数 schema 还需进一步驱动 Web/CLI/文档完全同源 | 编排 DAG、跨模板复杂流程尚未实现 | 每个模板可通过 Web/CLI 完成 task/run/execute；custom 可执行脚本并落审计/结果 | Web：`/tasks`；CLI：任务命令；服务：`ScenarioRegistry`、scenario runners | `tests/test_scenario_registry.py`、`tests/test_custom_automation_runner.py`、`tests/test_cli_device_task_run_commands.py` |
| 业务遍历与自动化接入 | `custom` 模板支持 `uiautomator2`、adb script、external script；能和监控链路串联并输出步骤 timeline/截图产物 | uiautomator2 依赖和真实业务路径样例需要更完整的用户级文档与 smoke；Web 上还不是独立的“自动化脚本管理/回调管理”能力 | 业务路径库、步骤复用、失败归一化、录制/回放能力未实现 | 用 custom 模板跑一条 adb script 或 external script，验证步骤 timeline、结果和 artifact | Web：`/tasks`；CLI：任务命令；服务：`CustomAutomationRunner` | `tests/test_custom_automation_runner.py`、`tests/test_scenario_registry.py`、`tests/test_run_execution_service.py` |

## 6. P2 高级能力验收矩阵

| 功能 | 已完成 | 部分完成 | 未完成 | 验收方式 | 对应入口 | 对应测试 |
| --- | --- | --- | --- | --- | --- | --- |
| 初步归因 | Attribution service、规则治理、性能风险辅助已有基础；问题中心和准入详情可间接展示归因/风险信息 | 主线程阻塞、binder、IO、CPU、内存、温控等归因规则需要更多真实样本和置信度校准；缺少专门 CLI/API，如 `attribute-issue` 或归因规则调试入口 | AI/深度归因不是当前目标 | 给定 Top Issue，输出归因方向、证据摘要、置信度和建议动作 | Web：`/issues`、`/api/issues`；CLI：通过 issue group/准入报告间接查看；服务：`AttributionService` | `tests/test_attribution_service.py`、`tests/test_rule_governance_service.py`、`tests/test_web_portal.py` |
| 7x24 无人值守 | unattended task、patrol runner、日报、周报、runner 状态页、runner 心跳已具备 | 真实 7x24 长时运行、设备自动恢复、补跑策略、通知链路更多依赖 smoke/runbook，不是稳定自动化测试闭环 | 多机集中调度、分布式执行代理和强 SLA 尚未定义 | 配置 unattended task，运行 patrol，生成 daily/weekly report，验证 runner 状态 | Web：`/runner`、`/runner/unattended/<task_id>`、`/api/runner`、`/api/unattended/actions/configure|run-round|patrol`；CLI：unattended 命令；服务：`UnattendedService`、`UnattendedRunnerService` | `tests/test_unattended_service.py`、`tests/test_unattended_runner_service.py`、`tests/test_cli_unattended_commands.py`、`tests/test_web_portal.py` |
| 质量门禁 | QualityGate、AdmissionCase、人工 override、准入报告、风险项、性能风险、覆盖不足已具备 | 硬门禁/软风险、场景阈值、设备组阈值、人工确认规则还需配置化；CLI 暂缺质量门禁 override 命令，Web 写入口也偏少 | 组织级准入策略库未完成 | 构造 report/baseline/audit，生成 AdmissionCase 和 QualityGate，验证自动结论、人工覆盖、最终结论 | Web：`/admission`、`/admission/baseline/<key>`、`/api/admission/actions/override|assign|comment|transition`；CLI：`list-admission-cases`、`show-admission-case`、`show-admission-report`、release/CI sync 命令；服务：`AdmissionCaseService`、`QualityGateService` | `tests/test_admission_case_service.py`、`tests/test_quality_gate_service.py`、`tests/test_release_submission_service.py`、`tests/test_cli_admission_rule_replay_commands.py`、`tests/test_cli_ci_integration_commands.py` |
| 团队协作与平台集成 | 本地 session、identity、认领、评论、状态流转、outbox、webhook、CI/IM/defect/release sync 基础已具备 | 当前仍偏本地部署和本地运维控制台；正式团队平台还需用户目录、组织边界、权限继承、接口安全 | 多租户、SSO、正式开放 API 平台未实现 | 写操作必须解析 session/identity；触发 outbox 后可投递、重试、dead-letter、receipt 可查 | Web：协作表单、`/integration`；CLI：integration/outbox/webhook 命令；服务：`CollaborationService`、`IntegrationOutboxService` | `tests/test_collaboration_service.py`、`tests/test_integration_outbox_service.py`、`tests/test_cli_ci_integration_commands.py`、`tests/test_cli_web_integration_commands.py` |

## 7. 横切能力验收矩阵

| 功能 | 已完成 | 部分完成 | 未完成 | 验收方式 | 对应入口 | 对应测试 |
| --- | --- | --- | --- | --- | --- | --- |
| 统一错误模型 | `AppError`、错误码、normalize 入口已有 | 仍需检查所有 Web/CLI/service 边界是否完全使用统一错误模型 | 错误码文档和用户排障手册可继续补 | 参数错误、权限错误、not found、内部异常都应返回稳定 code/message/hint/details | Web/API/CLI 错误响应；`stability/domain/errors.py` | `tests/test_app_errors.py`、`tests/test_app_error_boundaries.py` |
| 统一时间格式 | `time_utils` 和北京时间展示已具备 | 仍需持续清理散落的 `datetime.now()` / `utcnow()` / `isoformat()` 直出 | 时间字段 contract 文档可继续补 | Web、CLI、报告、runtime 导出中的用户可见时间统一为北京时间格式 | Web/CLI/报告；`stability/time_utils.py` | `tests/test_time_utils.py` |
| 配置中心 | `ConfigProvider` 已覆盖 runtime、monitoring、outbox、web、device、thresholds | 仍需确保所有入口都通过 provider，不再各自读 env/config | 配置 schema 和示例文件可继续补 | CLI 参数 > env > config > default 的优先级可测试 | CLI/Web/bootstrap；`stability/app/config_provider.py` | `tests/test_config_provider.py` |
| 诊断中心 | Doctor 已覆盖 Python、ADB、设备、TCP、runtime、config、端口、monitoring、outbox/webhook | 持续化自监控已拆到 `PlatformHealthService`，Doctor 继续保留即时诊断定位 | 错误码到用户排障手册的映射可继续补 | 运行 doctor，验证每个 check 有 status、summary、details | Web：`/doctor`；CLI：`doctor`；服务：`DoctorService` | `tests/test_doctor_service.py` |
| Runtime 生命周期 | runtime doctor/export/cleanup 已具备，支持分类和保护文件 | backup/restore、证据级 retention、导出包用户说明仍需加强 | 正式冷热分层未实现 | dry-run cleanup 不删文件；apply cleanup 不删 protected；export 生成 zip 和 manifest | CLI：runtime 命令；Web：诊断/接口入口；服务：`RuntimeLifecycleService` | `tests/test_runtime_lifecycle_service.py`、`tests/test_cli_runtime_commands.py` |
| 平台自监控 | `PlatformHealthService` 已持续落盘 runner 心跳、设备在线/可调度率、任务/实例/ADB 失败率、证据/报告失败率和 outbox backlog/dead-letter | 当前是 runtime JSON 快照和最近历史，尚未形成完整 24h 趋势图、阈值告警和报告推送 | 独立健康中心页面、SLA 阈值配置、告警订阅未实现 | 连续访问 Web 或执行 CLI 后，`runtime/platform_health/snapshots.json` 有快照；首页/runner/API 能看到平台健康状态和失败率 | Web：`/`、`/runner`、`/api/platform-health`；CLI：`platform-health`；服务：`PlatformHealthService` | `tests/test_platform_health_service.py`、`tests/test_web_portal_read_only.py` |
| 证据治理 | artifact 抓取和 runtime export/cleanup 已具备 | 缺少按证据类型的 retention、压缩、大小上限、必抓/选抓策略 | `EvidenceRetentionPolicy` 未实现 | 长期运行后证据不会无限膨胀；导出清单可解释每个证据来源 | 建议服务：`EvidenceGovernanceService`；Web：Run 详情/诊断页 | 当前缺专门测试 |
| 非功能目标 | 文档已识别需要定义 | 代码已有基础诊断和测试，但没有容量/SLA 验收指标 | 并发设备数、任务数、报告时延、查询时延、连续运行时长目标未落地 | 用 smoke/benchmark 验证设备数、任务数、响应时间、连续运行时长 | 建议补 `scripts/` smoke 和 docs 验收表 | 当前缺专门测试 |

## 8. 本地执行代理与平台边界

| 能力 | 建议归属 | 当前状态 | 下一步 |
| --- | --- | --- | --- |
| ADB 控制、设备刷新、TCP 连接 | 本地执行代理 | 已在 `infrastructure/adb`、`device_adapter`、scenario runner 中实现 | 继续统一到 `CommandRunner` / ADB adapter，减少直接 subprocess 分支 |
| 高频性能采样 | 本地执行代理 | `adb_collector`、SoloX、Perfetto adapter 已有 | 补真实 backend 长稳验收和采样完整性报告 |
| 日志与证据抓取 | 本地执行代理 | artifact collector 已有 | 补证据治理策略 |
| Issue 聚合、回归分析 | 分析中枢 | 已有 analysis/comparison/regression/snapshot | 补人工合并/拆分和跨版本延续治理 |
| 报告、准入、质量门禁 | 分析与准入中枢 | AdmissionCase/QualityGate/Report 已有 | 规则配置化，按场景/设备组/版本类型区分阈值 |
| 协作、通知、集成 | Web 与集成层 | 本地 session、outbox、webhook、CI/IM 链路已有 | 如果要团队外放，再补正式用户目录、SSO、API 安全和组织边界 |

## 9. 当前最优先补齐项

| 优先级 | 事项 | 原因 | 建议 owner |
| --- | --- | --- | --- |
| P0 | 平台自监控趋势与告警 | 第一版已能落盘快照，但还不能按 24h/SLA 自动告警和生成健康报告 | `stability/app/platform_health_service.py`、`stability/web/`、`stability/cli/handlers/runtime_lifecycle.py` |
| P0 | 证据治理 | 长期运行后 artifact 会成为成本和排障风险，需要 retention/压缩/导出策略 | `stability/artifact/`、`stability/app/runtime_lifecycle_service.py` |
| P1 | Issue 指纹治理 | Top Issue 已有，但缺人工修正和跨版本延续，容易产生噪音 | `stability/app/analysis_service.py`、`stability/domain/analysis_models.py` |
| P1 | QualityGate 规则配置化 | 当前门禁已有，但不同场景/设备组阈值还不够清晰 | `stability/app/quality_gate_service.py`、`config/` |
| P1 | Web feature package 收口 | 当前 Web 文件已拆小，但 mixin 聚合仍会继续膨胀 | `stability/web/` |
| P2 | 非功能目标和 smoke | 最终平台需要容量和时延指标，否则无法判断“可用” | `docs/`、`scripts/`、`tests/` |

## 10. 最终判断

当前项目已经具备稳定性平台核心闭环的主体能力：

**设备管理 -> 任务执行 -> 异常发现 -> 证据抓取 -> 问题聚合 -> 报告输出 -> 准入判断**

下一阶段不应继续按“是否有页面/是否有命令”推进，而应按验收矩阵推进：

- 每个能力是否有明确入口
- 每个能力是否有服务层对象
- 每个能力是否有测试或 smoke
- 每个能力是否能解释失败原因
- 每个能力是否能长期运行和治理数据

只有做到这些，`Android Stability Lab` 才能从“功能已经不少”进一步变成“可持续使用的平台”。
