# Android Stability Lab 未完成功能验收清单

## 1. 文档目的

本文档用于对照以下两份核心文档，检查当前仓库距离“最终平台形态”还有哪些能力未完成：

- [产品需求文档](./prd/Android%20Stability%20Lab%E4%BA%A7%E5%93%81%E9%9C%80%E6%B1%82%E6%96%87%E6%A1%A3.md)
- [最终应该具备的功能](./prd/Android%20Stability%20Lab%E6%9C%80%E7%BB%88%E5%BA%94%E8%AF%A5%E5%85%B7%E5%A4%87%E7%9A%84%E5%8A%9F%E8%83%BD.md)

本文档不是架构设计文档，而是一份面向排期和验收的状态清单。

状态判断规则：

- `已完成`：主链能力已经具备，能稳定进入日常使用。
- `部分完成`：已有最小闭环或基础实现，但距离最终文档定义的目标形态还有明显缺口。
- `未完成`：当前仓库中尚未看到可直接使用的正式能力。

为避免“阶段性能力”被误读成“完整平台完成”，对外同步时还应使用下面的能力状态口径：

- `已可用`：可以在当前本地优先边界内作为日常能力使用，且有可复核的页面、CLI、API、报告或运行记录。
- `部分可用`：平台侧入口、合同或最小闭环已经具备，但真实外部系统、团队级治理、长时稳定性或审批发布流程仍未完成。
- `不建议依赖`：当前只有查看、预览、辅助治理或本地文件管理能力，不应作为生产级在线平台能力承诺。

优先级说明：

- `P0`：直接影响平台是否能进入团队流程或成为正式能力。
- `P1`：重要能力，建议在主链稳定后尽快补齐。
- `P2`：有价值，但不应抢占主链资源。

## 1.1 P0 边界收口规则

当前 `P0` 收口遵循三个原则：

- 先本地优先：默认按本地部署、本地执行、本地 Web/JSON/报告/产物共享验收；团队内网共享可以作为本地优先能力的延伸，但不能自动写成完整在线平台。
- 先真实闭环：凡依赖真实设备、真实 webhook、真实外部系统、真实接收方或长时 worker 的能力，必须有真实验收记录后才算完成；本地 mock、单元测试、smoke 或 2 小时试运行只能作为准入条件。
- 先边界收口：新增能力必须进入 `stability/` 主线、CLI/Web 入口和可复核验收记录；基础设施补充目录不能被误写成新的业务主线能力。

以下能力必须完成真实验收后才允许从“部分完成/平台侧入口已完成”改为“已完成”：

- `IM / 飞书`：本地 mock/smoke 通过、真实 2 小时试运行通过、真实 endpoint 24 小时长时联调通过，并能回看 receipt、失败分级、dead-letter replay、签名/幂等和噪声治理记录。
- `CI / 缺陷系统 / 提测平台`：真实外部系统收到并消费平台 payload，回写、状态同步或回调结果可在 outbox、平台页面/API 或验收记录中复核。
- 本地长稳产品化：真实设备至少完成一轮长稳任务，任务配置、Run/轮次、设备选择/补位、执行结果、性能摘要、失败摘要和产物路径能串到 `/tasks`、`/runner`、`/performance` 和日报/周报。
- 设备池治理：断连、失败、重试、隔离、恢复探测和补位必须在轮次记录、runner 历史、巡检摘要或日报/周报中可复核；否则只能写成本地调度辅助能力已具备基础。
- 高级异常识别与性能风险：只有文本启发式、默认阈值或未标定样本时，仍按初步识别/规则式风险验收；要写成生产级诊断，必须完成真实样本标定、多证据确认和关键证据结构化解析。
- 身份、规则和准入治理：当前本地 session、受信 SSO header、只读用户目录、责任检索、候选规则预览和结构化准入报告，都不能等同于完整企业级 SSO/IAM、多租户隔离、在线规则发布、正式审批流或对外报告分发。

重点能力当前状态：

| 能力 | 当前状态 | 可依赖范围 | 仍不能写成 |
| --- | --- | --- | --- |
| IM/飞书 | 部分可用 | 平台侧通知合同、webhook/worker、本地 mock/smoke、receipt/outbox 运维观测和真实 2 小时试运行准入 | 真实 IM endpoint 24 小时长时链路已完成、生产通知治理已完成 |
| SSO/身份 | 部分可用 | 本地 session、受信 header SSO claims、写操作身份边界、审计字段、只读用户目录和责任检索 | 完整企业级 IAM、OIDC/LDAP/SSO、多租户隔离、组织权限平台 |
| 设备调度 | 部分可用 | 本地无人值守调度、主备/轮转/补位、隔离、恢复探测和 runner/日报周报复核 | 团队级设备池、预约、配额、审批、排班或维护窗口平台 |
| 规则在线发布 | 不建议依赖 | 只读规则配置中心、候选编辑预览、规则校验/diff/回放/评审、基线审计 | 在线保存、发布、审批、灰度、回滚的完整规则发布平台 |

## 2. 总体结论

对照当前代码，`Android Stability Lab` 已经完成了大部分主链基础能力：

- 设备、任务、Run、异常检测、证据抓取、报告
- 问题聚合、回归分析、性能趋势、初步归因
- `AdmissionCase / Quality Gate` 最小闭环
- 无人值守、巡检、日报周报、runner 状态页
- 本地 Web 主入口、最小协作、最小集成 outbox

但如果按“最终平台形态”验收，仍有几类关键能力没有收口：

1. Web 已进入团队共享入口边界，正式开放 API、最小回调安全边界和受信 header SSO 最小接入形态已部分落地；这仍不是完整企业级 SSO，多用户鉴权和更复杂团队治理仍未完成。
2. 外部系统集成已经完成 `CI + IM + 缺陷系统 + 提测平台` 四条平台侧正式入口和本地可运营 outbox 面，当前重点转向“先本地 mock/smoke，再真实 2 小时试运行，再真实 24 小时联调”的外部平台适配、长时 worker 联调和订阅治理。本地 smoke 只能证明平台侧出站合同和 worker 可用；2 小时试运行只能作为进入 24 小时联调的准入，不能写成真实链路已完成。
3. 首批稳定性任务模板族已经扩展，`custom` 模板也已进入正式业务遍历接入主链；本轮应按“本地长稳产品化最小闭环”验收，可指导用户按包名、任务名、长稳模板、运行策略、设备策略和监控策略创建无人值守长稳任务，并把真实设备至少一轮执行结果串到 `/tasks`、`/runner`、`/performance` 和日报/周报，但仍不是完整团队级长稳平台。
4. `uiautomator2`、自定义 adb 脚本、外部自动化脚本回调已具备最小正式能力，但更复杂业务路径和更深产品化仍未完成。
5. 高级异常识别已补入 `freeze / black_screen / system_server crash / watchdog` 一等文本启发式识别、结构化 evidence 字段、命中证据片段保留、截图/SurfaceFlinger/input events/dropbox/Perfetto trace 等扩展证据回灌，以及 OOM、内存上涨、卡顿/帧耗时恶化三类性能风险项；性能风险主链已支持 `PerformanceRiskThresholdConfig` 配置对象注入、scoped override 和本地 `config/performance_risk_thresholds.json` 加载，风险项 detail 可输出阈值来源、命中 scope 与阈值值。这些能力已从“文本启发式”推进到“最小多证据确认”，但仍不是基于图像内容识别、SurfaceFlinger 结构化解析、Perfetto 自动解析和真实样本标定后的生产级智能诊断。
6. 团队协作治理和组织级身份/权限已从纯本地化推进到“本地 session + 受信 SSO claims 写操作边界 + 最小只读用户目录/责任检索”的形态，但查看者默认仍看到同一份平台数据，身份主要用于约束写操作、审计追踪和责任查询，不等于完整 IAM 或组织权限平台。
7. 设备集群化治理目前应按“本地设备池治理 + 无人值守调度辅助”验收：已有设备注册、状态同步、主备设备、轮转、空闲设备补位、隔离和恢复探测，设备断连、任务失败、重试、隔离和恢复探测需要能在轮次、runner 历史或日报/周报中复核；但这还不是面向多个团队的设备预约、配额、审批或排班平台。

## 3. 验收矩阵

| 功能项 | 已完成 | 部分完成 | 未完成 | 建议优先级 | 说明 |
| --- | --- | --- | --- | --- | --- |
| 设备发现与注册 | ✅ |  |  | P2 | 已有设备对象、状态同步与仓储能力。 |
| 在线/离线/占用/隔离状态管理 | ✅ |  |  | P2 | 已支持 `online / offline / reserved / running / quarantined` 等状态与巡检统计。 |
| 设备分组与标签 |  | ✅ |  | P2 | 模型和持久化已支持 `group_name / tags`，但平台化治理与使用面仍较弱。 |
| 设备集群化治理与团队调度 |  | ✅ |  | P1 | 已有设备注册、状态同步、主备设备、轮转、候补/空闲池补位、隔离和恢复探测；当前更准确地说是本地无人值守调度辅助，不是完整团队级设备池、预约、配额、审批、维护窗口或排班平台。 |
| 创建任务 / 创建 Run / 执行 Run | ✅ |  |  | P2 | CLI 与 Web 主链都已具备。 |
| 定时任务、循环任务、无人值守 | ✅ |  |  | P2 | 已有 `configure-unattended-task`、runner、日报周报；本轮最小闭环要求真实设备至少一轮执行结果可回看任务、Run/轮次、runner 巡检和报告汇总。 |
| 批量执行与失败重试 | ✅ |  |  | P2 | 执行主链已支持受控并发、分类重试、失败清理。 |
| `Monkey` 模板 | ✅ |  |  | P2 | 已接入执行骨架和真实 smoke。 |
| 冷启动循环模板 | ✅ |  |  | P2 | 已接入执行骨架和真实 smoke。 |
| 前后台切换模板 | ✅ |  |  | P1 | 已补执行器、CLI/Web 模板入口和最小回归测试。 |
| 安装卸载循环模板 | ✅ |  |  | P1 | 已补执行器、CLI/Web 模板入口和最小回归测试；当前依赖 `task_params.apk_path`。 |
| 重启循环模板 | ✅ |  |  | P1 | 已补执行器、CLI/Web 模板入口和最小回归测试。 |
| 待机唤醒循环模板 | ✅ |  |  | P1 | 已补执行器、CLI/Web 模板入口和最小回归测试。 |
| 长稳运行模板化能力 |  | ✅ |  | P1 | 已具备最小长稳模板族画像和配置建议，可基于 `monkey / cold_start_loop / foreground_background_loop / install_uninstall_loop / reboot_loop / standby_wake_loop / custom` 组合无人值守长稳任务，并已有轮转、补位、隔离恢复和 `long_run_summary`；本轮按本地长稳产品化最小闭环验收，用户应能按包名、任务名、长稳模板、运行策略、设备策略、监控策略创建任务，并把结果串到 `/tasks`、`/runner`、`/performance`、日报/周报；但当前仍不是完整团队级长稳平台或设备排班平台。 |
| ANR / Java crash / native crash 识别 | ✅ |  |  | P2 | 当前检测主链已覆盖。 |
| reboot / process exit / device_offline / startup_timeout 识别 | ✅ |  |  | P2 | 当前检测主链已覆盖。 |
| freeze / 黑屏初步识别 |  | ✅ |  | P1 | 已新增 `freeze / black_screen` IssueType，并从 note/highlights/stdout/stderr/logcat/summary/metadata 等文本中按关键词识别 freeze、黑屏、画面无刷新、输入无响应、surface black 等信号；issue 证据采集已按类型追加 screenshot、SurfaceFlinger、input events 和 Perfetto trace，并把 artifact 来源回灌到 `evidence_signals / matched_sources / confirmation_level`，可形成 `multi_evidence` 级别。本轮已补 SurfaceFlinger / Perfetto 最小结构化 parser，输出 `structured_evidence` 和 `structured_artifact_evidence`。仍缺截图内容识别、输入事件时间线自动判读和真实样本标定。 |
| system_server crash / watchdog 识别 |  | ✅ |  | P1 | 已新增 `system_server_crash / watchdog` 一等 IssueType 文本启发式识别，并可输出结构化 evidence；issue 证据采集已把 dropbox、logcat、traces、tombstone、Perfetto trace 等来源回灌为多证据确认。本轮已补 dropbox / Perfetto 最小结构化 parser，可提取 watchdog、system_server crash、system_app_crash、ANR 等 tag 与上下文片段。仍缺完整 dropbox/watchdog trace 字段解析、真实样本标定和系统级根因归类。 |
| OOM 风险识别 |  | ✅ |  | P1 | `performance_trend_service` 已输出 `performance_oom_risk` 风险项，按 `memory_pss` peak/P95 阈值启发式识别；主链已支持注入 `PerformanceRiskThresholdConfig`、按设备/包名/场景等 scope 覆盖，并可从本地 `config/performance_risk_thresholds.json` 加载默认阈值和 scoped override；真实样本标定和 Web 治理入口仍待补齐。 |
| 内存持续上涨识别 |  | ✅ |  | P1 | `performance_trend_service` 已输出 `performance_memory_growth` 风险项，按右侧内存首尾滑动窗口增长阈值识别；主链已支持 scoped override、阈值来源输出和本地规则文件加载，但仍缺真实样本标定、页面化阈值治理和误报校准。 |
| 卡顿 / 帧耗时恶化识别 |  | ✅ |  | P1 | `performance_trend_service` 已输出 `performance_frame_jank_regression` 风险项，优先按 `frame_time_ms` P95 恶化、缺失时按 FPS 平均值下降识别；主链已支持配置对象注入、scoped override 和本地阈值配置文件，展示、准入链路治理入口、Perfetto 自动解析与真实阈值标定仍可继续增强。 |
| `logcat / bugreport / traces / tombstone` 自动抓取 | ✅ |  |  | P2 | 主链已具备最佳努力抓取。 |
| `dropbox / meminfo / SurfaceFlinger / perfetto` 扩展证据 |  | ✅ |  | P1 | 多项已接入，且 freeze/black_screen/watchdog/system_server crash 已能把关键 artifact 来源回灌到 issue evidence；本轮已补 SurfaceFlinger / dropbox / Perfetto 最小结构化解析，并把 parser 摘要写入 artifact 与 issue metadata。仍缺 meminfo 深度解析、Perfetto trace 正式解码、真实样本集和更完整自动判读。 |
| 自动截屏 |  |  | ✅ | P2 | 最终能力文档要求具备，当前仓库未见正式实现。 |
| 问题列表 / 问题指纹聚合 / Top Issue | ✅ |  |  | P2 | V2 分析主链已具备。 |
| 按版本 / 设备 / 场景聚合 | ✅ |  |  | P2 | 当前分析查询与回归服务已支持。 |
| 版本 A/B 对比与回归分析 | ✅ |  |  | P2 | `comparison / regression / snapshot` 已形成主链。 |
| 自动回归结论 | ✅ |  |  | P2 | 当前已具备回归判断服务。 |
| 问题趋势图 |  | ✅ |  | P2 | 已有趋势和摘要能力，但图表化、平台化呈现仍有限。 |
| 初步归因建议 |  | ✅ |  | P1 | 已有规则式 `attribution_service`，可基于 issue title、summary、process、artifact path、metadata / evidence 等样本信号给出方向、命中依据、置信度和规则版本，具备最小 evidence-aware 解释；但这仍是规则式初步归因建议，不是 AI 根因诊断，也不能替代人工根因判断。 |
| 任务报告 / 异常明细 / 证据路径清单 | ✅ |  |  | P2 | 执行报告与路径引用已具备。 |
| 版本测试报告 / 准入报告 |  | ✅ |  | P1 | 已落地正式结构化准入报告口径：`AdmissionCase`、质量门禁摘要、`/api/admission`、`/api/admission/cases`、准入中心和基线详情页可查看报告 payload、状态摘要、证据链、latest audit、comparison report 与版本索引；共享仍以本地部署页面、JSON/HTML/Markdown 报告和产物导出为主。当前不是完整对外 PDF、邮件分发或多级审批流。 |
| 日报 / 周报 / 自动汇总报告 | ✅ |  |  | P2 | runner 已支持 latest daily/weekly report。 |
| `Quality Gate` 自动结论 | ✅ |  |  | P2 | 质量门禁主链已具备。 |
| `AdmissionCase` 统一对象与证据链 | ✅ |  |  | P2 | `AdmissionCase` 已是一等对象，具备 `case_trace`、生命周期与回写合同。 |
| 人工覆盖 / 放行 / 驳回留痕 | ✅ |  |  | P2 | 已具备最小闭环与审计字段。 |
| 更正式的门禁规则配置入口 |  | ✅ |  | P1 | 已从纯 CLI 规则治理推进到“本地规则治理最小闭环”：支持候选变更保存、审批/拒绝、发布版本记录、回滚和本地 actor 权限绑定；Web/API 可暴露治理台账摘要。当前仍是本地文件治理口径，规则发布会直接写目标 JSON 文件，不是 Git PR/代码评审式发布流，也尚未开放完整 Web 写操作后台。 |
| 团队统一协作平台 |  | ✅ |  | P0 | 当前已具备本地协作留痕和受信 header SSO 写操作边界，但还不是完整在线团队平台。 |
| Issue 认领 / 评论 / 状态流转 | ✅ |  |  | P2 | 最小协作闭环已具备。 |
| `AdmissionCase` 认领 / 评论 / 状态流转 | ✅ |  |  | P2 | 最小协作闭环已具备。 |
| 统一用户目录 |  | ✅ |  | P1 | 已新增 `CollaborationUserProfile`、`list_user_profiles / get_user_profile / sync_user_profile_from_sso` 和 `/api/users` 只读入口，可聚合本地 actor、外部身份、email、display name、organization、teams、role、permissions、last_seen；但目录仍由本地 actor 与 `identities.json` 派生，没有独立 IAM/团队管理存储。 |
| 跨系统责任同步 |  | ✅ |  | P1 | 已新增 `/api/responsibility` 只读责任检索视图，汇总 actor/profile、外部身份、issue assignee、AdmissionCase assignee/final_reviewer、defect team_key、release owner_team；当前只是审计/检索视图，不改变责任写入或真正自动同步业务流。 |
| 批量操作 |  |  | ✅ | P2 | V3 计划已明确仍未完成。 |
| 更复杂的多级权限治理 |  | ✅ |  | P1 | 已有本地 permission matrix，并可基于受信 SSO claims 做组织边界校验；新增用户 profile 会暴露 role/permissions 供审计和检索，但权限行为仍走现有 permission matrix，仍未到完整组织权限体系。 |
| 可签发 / 可过期 / 可吊销的本地 session | ✅ |  |  | P2 | 本地正式边界已具备。 |
| 正式在线身份体系 / SSO / 组织边界 |  | ✅ |  | P0 | 正式在线身份边界的最小接入形态已部分落地：支持受信 SSO header claims 解析、外部身份稳定绑定、组织边界校验、SSO session 签发和审计增强；但仍依赖可信反向代理/网关注入并清洗 header，不是完整企业级 OIDC/LDAP/SSO 产品。 |
| Web 首页 / 任务大厅 / 问题中心 / 准入中心 | ✅ |  |  | P2 | 页面主入口已经具备。 |
| Web 成为团队统一主入口 | ✅ |  |  | P0 | 已补团队共享入口模式、`/platform`、`/api/platform`、`/ready`、request id、基础安全响应边界和 `identity_capabilities`；正式在线身份边界已有最小受信 header 接入，但完整多用户鉴权仍属后续项。 |
| 正式开放 API | ✅ |  |  | P0 | 已补 `/api/manifest`、`/api/openapi.json`、平台/ready 边界说明和共享入口对接口径。 |
| 回调安全 / 签名校验 / 补偿边界 | ✅ |  |  | P0 | 已补非本地 webhook 的 `https + signing_secret` 约束、回调合同、idempotency key、签名/失败策略边界。 |
| `integration_outbox` + worker + replay | ✅ |  |  | P2 | 本地可运营面已具备；P0 真实链路运营已补 IM/飞书长时联调 runbook，验收路径调整为先本地 mock/smoke 验证 worker、合同、receipt、dead-letter replay 和观测面，再进入真实飞书 2 小时试运行，最后进入真实 IM endpoint 24 小时联调。 |
| CI 最小回写链路 | ✅ |  |  | P2 | 当前已完成一条真实链路。 |
| IM 通知 |  | ✅ |  | P1 | 平台侧已补 `im_notify` / `feishu_bot` delivery channel、IM/飞书 webhook 注册、worker、Web 运维入口和 `asl.im_notify.v1`/飞书机器人消息体合同；本地 mock/smoke 可验证平台侧出站链路，飞书 2 小时试运行用于准入真实长时联调，但真实 IM endpoint 24 小时长时 worker 联调、接收方验签/幂等、receipt 反查、dead-letter replay、真实限流和噪声治理仍待验收，因此不能按真实链路已完成结项。 |
| 缺陷系统对接 | ✅ |  |  | P1 | 已支持从问题侧创建缺陷请求、回填外部缺陷链接与状态同步，并通过 `defect_sync` delivery channel、Webhook、Worker 和 `asl.defect_sync.v1` 合同打通最小正式链路。 |
| 提测平台对接 | ✅ |  |  | P1 | 已支持接收提测上下文、创建任务与 Run、可选立即执行、同步 AdmissionCase 准入结果，并通过 `release_submission` delivery channel、Webhook、Worker 和 `asl.release_submission.v1` 合同回写提测平台。 |
| `uiautomator2` 接入 | ✅ |  |  | P1 | `custom` 模板已支持 `automation_mode=uiautomator2`，并把步骤时间线、失败摘要和附件路径接进主执行链。 |
| 自定义 adb 脚本接入 | ✅ |  |  | P1 | `custom` 模板已支持 `automation_mode=adb_script`，可把 adb 步骤执行结果沉淀为统一时间线。 |
| 外部自动化脚本回调 | ✅ |  |  | P1 | `custom` 模板已支持 `automation_mode=external_script`，通过 context/output 文件合同接回步骤与摘要。 |
| 真实业务路径与监控串联 |  | ✅ |  | P1 | 业务遍历结果已能进入统一 Run/报告主链，但更复杂路径库、页面化编排和深度监控联动仍可继续加强。 |

## 4. 优先级建议

### 4.1 建议先做的 `P0`

1. 已完成：Web 已补团队共享入口模式、平台说明页、平台/ready API、request id 与基础安全响应边界。
2. 已完成：已补正式 API manifest / OpenAPI 风格描述，以及回调安全、签名校验和外放边界。
3. 部分完成：正式在线身份边界已具备最小受信 header SSO 接入，写操作可优先解析 `X-ASL-SSO-Provider / X-ASL-External-Subject / X-ASL-Org` 等 claims，审计可记录 provider、external subject、organization、team、request id；下一步如继续建设，应单列完整企业级 OIDC/LDAP/SSO、反向代理部署基线和组织权限治理主题。

### 4.2 建议紧接着做的 `P1`

1. 已完成：首批模板已补齐前后台切换、安装卸载循环、重启循环、待机唤醒循环。
2. 已完成：`custom` 模板已打通 `uiautomator2`、`adb_script`、`external_script` 三类业务遍历接入。
3. 部分完成：长稳运行模板化能力已具备最小模板族画像和配置建议，可把现有模板按长稳场景组合进无人值守轮转、补位、隔离恢复和日报/周报链路；本轮应重点补齐“本地长稳产品化最小闭环”的验收记录，包括按包名/任务名/模板/运行策略/设备策略/监控策略建任务、真实设备至少一轮执行、结果串到 `/tasks`、`/runner`、`/performance` 和日报/周报。下一步仍需补更清晰长稳配置入口、推荐参数沉淀、专项长稳验证样本和更正式产品化配置面。
4. 已完成：提测平台外部系统集成已具备最小正式链路。
5. 部分完成：高级异常识别已补入黑屏/freeze/system_server crash/watchdog 一等文本启发式识别、结构化 evidence、命中片段、扩展证据引用和 artifact 来源回灌；本轮已补 SurfaceFlinger、dropbox、Perfetto 的最小结构化解析，能把 parser 摘要回灌到 artifact 和 issue metadata。OOM、内存上涨、卡顿恶化三类性能风险项已支持配置对象注入、按设备/包名/场景等 scoped override、本地阈值文件加载，并能输出阈值来源、命中 scope 和阈值值。下一步应补真实样本标定、截图内容识别、Perfetto 正式解码、输入事件时间线判读和 Web 治理入口。
6. 部分完成：统一用户目录和跨系统责任同步已具备最小只读/审计形态，可用于责任检索、SSO profile 稳定绑定和平台 API 查询；下一步仍需补独立用户/团队管理、真正跨系统责任写回或自动同步、更正式权限治理。
7. 部分完成：设备集群化治理已具备本地设备池状态、主备设备、轮转、补位、隔离和恢复探测，能支撑无人值守任务降低值守成本；本轮只按本地长稳任务的设备策略和异常记录验收，不按团队调度平台验收。下一步如要进入团队调度，应补设备预约/借用、团队配额、维护窗口、冲突处理、责任人视图和通知联动。
8. 部分完成：更正式的门禁规则配置入口已从只读配置中心和编辑预览推进到本地治理最小闭环：候选保存、审批/拒绝、版本发布、回滚和权限绑定已经具备。下一步如要按完整规则治理产品验收，应补 Git/PR 式发布流、Web 写操作身份绑定、发布前强制 replay/review gate 和更强审计，而不是把本轮能力写成完整在线规则编辑器。

### 4.3 可后置处理的 `P2`

1. 自动截屏。
2. 更完整的问题趋势图和平台化可视化。
3. 设备分组/标签的更完整产品化治理。
4. 团队级设备调度平台，包括预约、配额、排班、冲突处理和设备维护窗口。

## 5. 当前建议的验收口径

当以下条目全部满足时，可以认为 `Android Stability Lab` 更接近“最终平台形态”：

1. 首批模板族已扩展到 `monkey / cold_start_loop / foreground_background_loop / install_uninstall_loop / reboot_loop / standby_wake_loop / custom`；长稳运行本轮按本地长稳产品化最小闭环阶段性验收，要求能按包名、任务名、长稳模板、运行策略、设备策略和监控策略创建任务，并至少用真实设备完成一轮执行；不应写成完整团队级长稳平台。
2. Web/API 已具备共享入口、manifest、openapi、回调合同边界、受信 header SSO 最小接入形态，以及 `/api/users` 与 `/api/responsibility` 两个只读审计/检索入口；当前应按“正式在线身份边界和最小目录/责任视图已部分落地”验收，而不是按完整企业级 SSO、IAM 或跨系统自动同步验收。
3. 已完成 `CI + IM + 缺陷系统 + 提测平台` 四类外部链路的平台侧正式入口和本地 outbox 运维面；下一步重点转向真实平台适配、长时 worker 联调和订阅治理，其中 P0 先按 `docs/运维/IM通知真实链路长时联调Runbook.md` 对 IM/飞书通知链路执行“本地 mock/smoke 通过 -> 真实飞书 2 小时试运行 -> 真实 endpoint 跑满 24 小时”的三段式验收，再把同一运营口径推广到 CI、缺陷和提测平台。本地 smoke 通过只能作为进入真实试运行的准入条件，2 小时试运行通过只能作为进入 24 小时联调的准入条件，均不作为真实链路完成证明。
4. `uiautomator2` 或同等级业务遍历能力已进入正式产品主链，后续重点转向更复杂路径库和监控联动深度。
5. 本地部署仍可用；完全没有 SSO header 时，本地 session / `X-ASL-Actor` 路径保持可用。查看者默认看到同一份平台数据，身份主要约束写操作、审计和责任检索，不应写成“不同组织/不同用户看到不同数据”的多租户平台。
6. 高级异常识别与更强归因能力不再停留在计划层；当前验收口径应限定为规则式/文本启发式初步识别、结构化 evidence、SurfaceFlinger/dropbox/Perfetto 最小 parser 和最小 evidence-aware 初步归因解释，性能阈值可按配置对象注入和 scoped override 验收，但后续仍需真实样本标定、正式 trace 解码、多证据确认、外部阈值治理入口和更高置信度归因，不能按 AI 根因诊断验收。
7. 设备池治理可按本地无人值守能力阶段性验收：设备状态、主备/轮转、补位、隔离、恢复探测和巡检摘要可用；设备断连、任务失败、重试、隔离和恢复探测必须有记录，可在轮次记录、runner 历史、巡检摘要或日报/周报中复核；团队排班、预约审批、配额治理和跨团队设备归属仍应视为后续缺口。
8. 门禁规则配置入口可按“本地规则治理最小闭环”验收：查看当前规则/默认规则/生效规则、候选规则预览/校验/diff、候选保存、审批/拒绝、发布版本记录、回滚和权限绑定。规则源文件仍保留在本地仓库或本地部署环境中管理，跨团队共享仍以导出规则快照、评审报告、JSON/HTML/Markdown 产物为主；当前不应验收为 Git PR/代码评审式规则发布平台或完整 Web 规则编辑后台。
9. 版本测试报告 / 准入报告可按“结构化 report payload + Web/API 摘要 + 本地报告/审计/对比产物跳转”阶段性验收；当前不应写成已具备完整对外 PDF、邮件自动分发、正式签核审批流或跨组织报告发布平台。
10. 本地长稳闭环验收必须确认结果链路能串到 `/tasks`、`/runner`、`/performance`、日报/周报：`/tasks` 用于任务与 Run 回看，`/runner` 用于 patrol/心跳/异常轮次回看，`/performance` 用于性能趋势或风险摘要，日报/周报用于跨轮汇总。若只有命令行输出或临时日志，不应判定为闭环完成。

## 6. 备注

- 本清单基于当前仓库代码、需求文档和开发计划整理。
- 少量“部分完成/未完成”的判断带有“根据当前代码推断”的性质；如果后续新增模块或外部私有仓库承接了部分能力，需要同步修正文档。
- 本文档建议在每一轮 `V3` 重点能力落地后同步更新，避免需求和代码再次漂移。
